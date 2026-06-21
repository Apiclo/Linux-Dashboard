"""GPU detection and installation package."""
# ── _common ──
from ._common import (
    OFFLINE_PKG_DIR,
    OFFLINE_GENERATE_DIR,
    _version_cache,
    _PKG_RE,
    _CUDA_FALLBACK_VERSIONS,
    _cached,
    NVIDIA_SMI_REALTIME_SCRIPT,
    INITRAMFS_CMDS,
)

# ── detect ──
from .detect import (
    detect_gpus,
    get_nvidia_smi_info,
    get_nvidia_driver_detail,
    check_nouveau,
    blacklist_nouveau,
    check_secure_boot,
    get_running_kernel,
    get_kernel_headers_path,
    get_display_manager,
    get_loaded_modules,
    _update_initramfs,
    _update_initramfs_cmd,
    get_detect_data,
    get_distro_info,
    get_nvidia_smi_realtime,
    start_nvidia_monitor,
    stop_nvidia_monitor,
)

# ── cuda ──
from .cuda import (
    CUDA_REPO_CONFIG,
    resolve_distro_family,
    _get_nvidia_repo_url,
    _fetch_web_versions,
    _try_fetch_url,
    _fetch_keyring_name,
    _fetch_cuda_versions_from_pm,
    fetch_cuda_versions,
    get_cuda_info,
    _build_cuda_fmt,
    _check_epel,
    setup_cuda_repo,
    install_cuda_packages,
    install_cuda_toolkit,
)

# ── nvidia ──
from .nvidia import (
    get_nvidia_repo_versions,
    _get_nvidia_repo_versions_impl,
    install_nvidia_repo,
    validate_runfile,
    get_runfile_info,
    install_nvidia_runfile,
    uninstall_nvidia,
    check_compatibility,
    list_available_nvidia_packages,
)

# ── offline ──
from .offline import (
    generate_offline_package,
    _extract_version,
    _get_distro_install_block,
    _get_initramfs_cmd,
    _make_install_script,
    parse_offline_package,
    list_offline_packages,
    list_generated_packages,
    delete_offline_package,
    install_offline_package,
)

# ── amd_intel ──
from .amd_intel import (
    ROCM_REPO_CONFIG,
    install_rocm_driver,
    install_amd_driver,
    install_intel_driver,
    _resolve_rocm_family,
    _get_rocm_distro_params,
)
