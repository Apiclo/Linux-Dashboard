import { ref, computed } from 'vue'
import { streamTask as apiStreamTask } from '@/api/request'

export interface TaskState {
  taskId: string | null
  running: boolean
  done: boolean
  exitCode: number | null
  output: string
  maxLines: number
}

export interface BatchParsedResult {
  total: number
  success: number
  failed: number
  failedPackages: string[]
  summary: string
}

export function useSseTask(maxLines = 5000) {
  const state = ref<TaskState>({
    taskId: null,
    running: false,
    done: false,
    exitCode: null,
    output: '',
    maxLines,
  })

  let currentStream: { close: () => void } | null = null

  function start(taskId: string) {
    stop()
    state.value = {
      taskId,
      running: true,
      done: false,
      exitCode: null,
      output: '',
      maxLines,
    }

    currentStream = apiStreamTask(taskId, {
      onOutput(line) {
        const lines = state.value.output.split('\n')
        if (lines.length > maxLines) {
          state.value.output = lines.slice(-maxLines).join('\n')
        }
        state.value.output += line + '\n'
      },
      onDone(code) {
        state.value.running = false
        state.value.done = true
        state.value.exitCode = code
        state.value.output += code === 0 ? '\n✓ 完成\n' : `\n✗ 失败 (${code})\n`
        currentStream = null
      },
      onError(msg) {
        state.value.running = false
        state.value.output += `\n✗ ${msg}\n`
        currentStream = null
      },
    })
  }

  function stop() {
    currentStream?.close()
    currentStream = null
    state.value.running = false
  }

  function clear() {
    state.value.output = ''
    state.value.done = false
    state.value.exitCode = null
  }

  const outputHtml = computed(() => {
    return state.value.output
      .split('\n')
      .map((l) => {
        if (/error|fail|无法|失败|ERROR/i.test(l)) return `<div class="err-line">${escHtml(l)}</div>`
        if (/warn|警告|WARN/i.test(l)) return `<div class="warn-line">${escHtml(l)}</div>`
        if (/✓|成功|complete|OK/i.test(l)) return `<div class="ok-line">${escHtml(l)}</div>`
        return escHtml(l)
      })
      .join('\n')
  })

  /** Parse batch operation output into structured results */
  const parsedResults = computed<BatchParsedResult | null>(() => {
    const out = state.value.output
    if (!out || !state.value.done) return null

    const lines = out.split('\n')
    let success = 0
    let failed = 0
    const failedPackages: string[] = []

    // Match patterns like:
    //   pkgname: 安装成功 / 卸载成功 / installed / removed
    //   pkgname: 安装失败 / 卸载失败 / failed
    //   [SUCCESS] pkgname ...
    //   [FAILED] pkgname ...
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue

      // Chinese patterns
      const successMatch = trimmed.match(/^(.+?)[：:]\s*(安装成功|卸载成功|成功|✓)/)
      const failMatch = trimmed.match(/^(.+?)[：:]\s*(安装失败|卸载失败|失败|✗|error)/i)
      // English patterns
      const engSuccess = trimmed.match(/^\[?(SUCCESS|OK)\]?\s+(.+)/i)
      const engFail = trimmed.match(/^\[?(FAIL|FAILED|ERROR)\]?\s+(.+)/i)
      // Generic patterns from batch commands
      const resultLine = trimmed.match(/^(.+?)\s+(成功|失败|OK|FAILED|installed|removed|error)$/i)

      if (successMatch) {
        success++
      } else if (failMatch) {
        failed++
        failedPackages.push(failMatch[1].trim())
      } else if (engSuccess) {
        success++
      } else if (engFail) {
        failed++
        failedPackages.push(engFail[2].trim())
      } else if (resultLine) {
        if (/成功|OK|installed|removed/i.test(resultLine[2])) {
          success++
        } else {
          failed++
          failedPackages.push(resultLine[1].trim())
        }
      }
    }

    const total = success + failed
    if (total === 0) return null

    return {
      total,
      success,
      failed,
      failedPackages,
      summary: `${success}/${total} 成功` + (failed > 0 ? `，${failed} 失败` : ''),
    }
  })

  function escHtml(s: string) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }

  return { state, start, stop, clear, outputHtml, parsedResults }
}
