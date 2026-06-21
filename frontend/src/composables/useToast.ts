import { ElMessage } from 'element-plus'

export function useToast() {
  function show(message: string, type: 'success' | 'error' | 'warn' | 'info' = 'info', summary?: string) {
    ElMessage({
      type: type === 'warn' ? 'warning' : type,
      message: summary ? `${summary}: ${message}` : message,
      duration: 5000,
      showClose: true,
    })
  }

  return {
    show,
    success: (msg: string) => show(msg, 'success'),
    error: (msg: string) => show(msg, 'error'),
    warning: (msg: string) => show(msg, 'warn'),
    info: (msg: string) => show(msg, 'info'),
  }
}
