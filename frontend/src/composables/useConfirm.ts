import { ref } from 'vue'

interface ConfirmRequest {
  title: string
  message: string
  isDanger: boolean
  resolve: (value: boolean) => void
}

const show = ref(false)
const title = ref('')
const message = ref('')
const danger = ref(true)
const _queue: ConfirmRequest[] = []

function _showNext() {
  if (_queue.length === 0) {
    show.value = false
    return
  }
  const req = _queue[0]
  title.value = req.title
  message.value = req.message
  danger.value = req.isDanger
  show.value = true
}

export function useConfirm() {
  function confirm(t: string, msg: string, isDanger = true): Promise<boolean> {
    return new Promise((resolve) => {
      _queue.push({ title: t, message: msg, isDanger, resolve })
      if (_queue.length === 1) _showNext()
    })
  }

  function onConfirm() {
    const req = _queue.shift()
    req?.resolve(true)
    _showNext()
  }

  function onCancel() {
    const req = _queue.shift()
    req?.resolve(false)
    _showNext()
  }

  function close() {
    // Resolve all pending dialogs as cancelled
    while (_queue.length > 0) {
      _queue.shift()!.resolve(false)
    }
    show.value = false
  }

  return { show, title, message, danger, confirm, onConfirm, onCancel, close }
}
