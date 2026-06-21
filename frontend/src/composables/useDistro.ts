import { ref } from 'vue'
import type { DistroInfo } from '@/types/api'
import { systemApi } from '@/api/system'

const distro = ref<DistroInfo>({
  id: '', like: '', pkg_manager: '', version: '',
  pretty_name: '', is_kylin: false, kylin_edition: '',
})

export function useDistro() {
  async function loadDistro() {
    try {
      distro.value = await systemApi.getDistroCached()
    } catch {}
  }

  return { distro, loadDistro }
}
