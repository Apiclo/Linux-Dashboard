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

  function escHtml(s: string) {
    return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  }

  return { state, start, stop, clear, outputHtml }
}
