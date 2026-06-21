import { ref } from 'vue'

const show = ref(false)
const title = ref('')
const message = ref('')
const danger = ref(true)
let _resolve: ((value: boolean) => void) | null = null

export function useConfirm() {
  function confirm(t: string, msg: string, isDanger = true): Promise<boolean> {
    title.value = t
    message.value = msg
    danger.value = isDanger
    show.value = true
    return new Promise((resolve) => {
      _resolve = resolve
    })
  }

  function onConfirm() {
    show.value = false
    _resolve?.(true)
  }

  function onCancel() {
    show.value = false
    _resolve?.(false)
  }

  return { show, title, message, danger, confirm, onConfirm, onCancel }
}
