<template>
  <div class="xterm-wrapper">
    <div class="xterm-toolbar">
      <div class="flex items-center gap-2">
        <span class="text-xs" style="color: var(--text-2)">{{ wsStatus }}</span>
        <el-tag v-if="connected" type="success" size="small">已连接</el-tag>
        <el-tag v-else-if="connecting" type="warning" size="small">连接中</el-tag>
        <el-tag v-else type="info" size="small">未连接</el-tag>
      </div>
      <div class="flex gap-2">
        <el-button size="small" plain @click="doConnect" :disabled="connecting || connected">连接</el-button>
        <el-button size="small" type="danger" plain @click="doDisconnect" :disabled="!connected">断开</el-button>
        <el-button size="small" plain @click="terminal?.clear()">清屏</el-button>
        <el-button size="small" plain @click="doCopy">复制</el-button>
      </div>
    </div>
    <div ref="terminalEl" class="xterm-container"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import { useToast } from '@/composables/useToast'
import '@xterm/xterm/css/xterm.css'

const props = withDefaults(defineProps<{
  wsUrl?: string
  root?: string
  shell?: string
}>(), {
  wsUrl: '/ws/chroot',
  root: '/mnt',
  shell: '/bin/bash',
})

const emit = defineEmits<{
  connected: []
  disconnected: []
}>()

const toast = useToast()
const terminalEl = ref<HTMLDivElement>()
const connected = ref(false)
const connecting = ref(false)

let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
let ws: WebSocket | null = null

const wsStatus = ref('就绪')

function initTerminal() {
  if (!terminalEl.value) return
  terminal = new Terminal({
    cursorBlink: true,
    cursorStyle: 'bar',
    fontSize: 14,
    fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
    theme: {
      background: '#0d1117',
      foreground: '#e6edf3',
      cursor: '#58a6ff',
      selectionBackground: '#388bfd44',
      black: '#484f58',
      red: '#f85149',
      green: '#3fb950',
      yellow: '#d29922',
      blue: '#58a6ff',
      magenta: '#bc8cff',
      cyan: '#39c5cf',
      white: '#e6edf3',
    },
    allowProposedApi: true,
    scrollback: 5000,
  })

  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.loadAddon(new WebLinksAddon())

  terminal.open(terminalEl.value)
  fitAddon.fit()

  terminal.onResize(() => {
    // Could send SIGWINCH via WebSocket if implemented
  })

  const handleResize = () => {
    fitAddon?.fit()
  }
  window.addEventListener('resize', handleResize)

  terminalEl.value._cleanup = () => {
    window.removeEventListener('resize', handleResize)
  }
}

function doConnect() {
  if (connected.value || connecting.value) return

  connecting.value = true
  wsStatus.value = '正在连接...'

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${proto}//${location.host}${props.wsUrl}`

  ws = new WebSocket(url)

  ws.onopen = () => {
    connected.value = true
    connecting.value = false
    wsStatus.value = '已连接'
    if (!terminal) initTerminal()

    // 发送初始化消息
    ws!.send(JSON.stringify({
      root: props.root,
      shell: props.shell,
    }))

    emit('connected')
  }

  ws.onmessage = (e) => {
    if (terminal) {
      terminal.write(e.data)
    }
  }

  ws.onerror = () => {
    wsStatus.value = '连接错误'
    connecting.value = false
    toast.error('WebSocket 连接失败')
  }

  ws.onclose = () => {
    connected.value = false
    connecting.value = false
    wsStatus.value = '已断开'
    ws = null
    emit('disconnected')
  }

  // 键盘输入 -> WebSocket
  if (terminal) {
    terminal.onData((data) => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(data)
      }
    })
  } else {
    // terminal not yet created, will bind after init
    const checkInterval = setInterval(() => {
      if (terminal) {
        terminal.onData((data) => {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send(data)
          }
        })
        clearInterval(checkInterval)
      }
    }, 100)
  }
}

function doDisconnect() {
  if (ws?.readyState === WebSocket.OPEN) {
    ws.send('__CLOSE__')
    setTimeout(() => ws?.close(), 500)
  }
}

function doCopy() {
  const text = terminal?.getSelection()
  if (text) {
    navigator.clipboard.writeText(text)
    toast.success('已复制')
  }
}

onMounted(() => {
  nextTick(initTerminal)
})

onBeforeUnmount(() => {
  if (ws) {
    ws.close()
    ws = null
  }
  terminal?.dispose()
  if (terminalEl.value?._cleanup) {
    terminalEl.value._cleanup()
  }
})
</script>

<style scoped>
.xterm-wrapper {
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border);
  background: #0d1117;
}
.xterm-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-2);
  border-bottom: 1px solid var(--border);
}
.xterm-container {
  width: 100%;
  height: 420px;
}
.xterm-container :deep(.xterm) {
  height: 100%;
  padding: 8px;
}
</style>
