"""System routes — core settings, sysctl, optimisation, MAC."""
from flask import Blueprint, jsonify, request
from utils.helpers import safe_api, validate_json, require_auth
from core import system

bp = Blueprint("system", __name__)


@bp.route("/api/system/info")
@safe_api
@require_auth
def info():
    return jsonify(system.get_system_info())


@bp.route("/api/system/distro")
@safe_api
@require_auth
def distro():
    from core.distro import detect_distro
    return jsonify(detect_distro())


@bp.route("/api/system/timezones")
@safe_api
@require_auth
def timezones():
    return jsonify(system.get_timezone_list())


@bp.route("/api/system/locales")
@safe_api
@require_auth
def locales():
    return jsonify(system.get_locale_list())


@bp.route("/api/system/hostname", methods=["POST"])
@safe_api
@require_auth
@validate_json(["hostname"])
def set_hostname(data):
    out, code = system.set_hostname(data["hostname"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/system/timezone", methods=["POST"])
@safe_api
@require_auth
@validate_json(["timezone"])
def set_timezone(data):
    out, code = system.set_timezone(data["timezone"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/system/locale", methods=["POST"])
@safe_api
@require_auth
@validate_json(["locale"])
def set_locale(data):
    out, code = system.set_locale(data["locale"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/sysctl")
@safe_api
@require_auth
def sysctl():
    q = request.args.get("q", "").strip()
    return jsonify(system.get_sysctl_params(q))


@bp.route("/api/sysctl/set", methods=["POST"])
@safe_api
@require_auth
@validate_json(["key", "value"])
def sysctl_set(data):
    out, code = system.set_sysctl_param(data["key"], data["value"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/hosts")
@safe_api
@require_auth
def hosts():
    return jsonify({"content": system.get_hosts()})


@bp.route("/api/hosts/save", methods=["POST"])
@safe_api
@require_auth
@validate_json(["content"])
def hosts_save(data):
    return jsonify({"success": system.save_hosts(data["content"])})


@bp.route("/api/system/ssh")
@safe_api
@require_auth
def ssh_config():
    return jsonify(system.get_ssh_config())


@bp.route("/api/system/ssh", methods=["POST"])
@safe_api
@require_auth
@validate_json(["config"])
def ssh_save(data):
    return jsonify(system.save_ssh_config(data["config"]))


@bp.route("/api/system/swap")
@safe_api
@require_auth
def swap_info():
    return jsonify(system.get_swap_info())


@bp.route("/api/system/swap/create", methods=["POST"])
@safe_api
@require_auth
@validate_json(["size"])
def swap_create(data):
    return jsonify(system.create_swap(data["size"]))


@bp.route("/api/system/swap/disable", methods=["POST"])
@safe_api
@require_auth
def swap_disable():
    return jsonify(system.disable_swap())


@bp.route("/api/system/update", methods=["POST"])
@safe_api
@require_auth
def system_update():
    from utils.tasks import start_task
    cmd = (
        'if command -v apt-get >/dev/null 2>&1; then '
        'sudo apt-get update -y && sudo apt-get upgrade -y; '
        'elif command -v yum >/dev/null 2>&1; then '
        'sudo yum update -y; '
        'elif command -v dnf >/dev/null 2>&1; then '
        'sudo dnf update -y; '
        'elif command -v pacman >/dev/null 2>&1; then '
        'sudo pacman -Syu --noconfirm; '
        'else echo "No supported package manager found"; exit 1; fi'
    )
    task_id = start_task(cmd, "sys_update")
    return jsonify({"task_id": task_id, "success": True})


# ── 服务优化 ──

@bp.route("/api/system/service-optimize")
@safe_api
@require_auth
def service_optimize_status():
    return jsonify({"services": system.get_service_optimization()})


@bp.route("/api/system/service-optimize", methods=["POST"])
@safe_api
@require_auth
def service_optimize_run():
    data = request.get_json(silent=True) or {}
    svc_names = data.get("svc_names", None)
    return jsonify({"results": system.optimize_services(svc_names)})


# ── 快速内核参数 ──

@bp.route("/api/system/quick-params")
@safe_api
@require_auth
def quick_params():
    return jsonify({"params": system.get_quick_kernel_params()})


@bp.route("/api/system/quick-params", methods=["POST"])
@safe_api
@require_auth
@validate_json(["params"])
def apply_quick_params(data):
    return jsonify({"results": system.apply_quick_kernel_params(data["params"])})


# ── 系统优化方案（场景化） ──

@bp.route("/api/system/optimization-profiles")
@safe_api
@require_auth
def optimization_profiles():
    """返回可用的优化方案列表（不含具体数据，只含 label/desc）。"""
    profiles = {}
    for key, cfg in system.OPTIMIZATION_PROFILES.items():
        profiles[key] = {"label": cfg["label"], "desc": cfg["desc"]}
    return jsonify({"profiles": profiles})


@bp.route("/api/system/optimization-preview")
@safe_api
@require_auth
def optimization_preview():
    """预览某个优化方案的变更内容。"""
    profile = request.args.get("profile", "").strip()
    if not profile:
        return jsonify({"success": False, "message": "Missing profile parameter"}), 400
    return jsonify(system.get_optimization_preview(profile))


@bp.route("/api/system/optimization-apply", methods=["POST"])
@safe_api
@require_auth
@validate_json(["profile"])
def optimization_apply(data):
    """应用某个优化方案（可指定仅应用部分项）。"""
    return jsonify(system.apply_optimization_profile(
        data["profile"],
        sysctl_keys=data.get("sysctl_keys"),
        svc_names=data.get("svc_names"),
    ))


# ── Sysctl 持久化 ──

@bp.route("/api/sysctl/persist", methods=["POST"])
@safe_api
@require_auth
@validate_json(["key", "value"])
def sysctl_persist(data):
    out, code = system.persist_sysctl(data["key"], data["value"])
    return jsonify({"success": code == 0, "message": out})


# ── SELinux / AppArmor ──

@bp.route("/api/system/mac")
@safe_api
@require_auth
def mac_status():
    return jsonify(system.get_mac_status())


@bp.route("/api/system/selinux", methods=["POST"])
@safe_api
@require_auth
@validate_json(["mode"])
def selinux_set(data):
    ok, msg = system.set_selinux_mode(data["mode"])
    return jsonify({"success": ok, "message": msg})


# ── 诊断报告 ──

@bp.route("/api/system/diagnostic")
@safe_api
@require_auth
def diagnostic_report():
    """生成 Markdown 格式的系统诊断报告。"""
    return jsonify({"success": True, "report": system.generate_diagnostic_report()})


@bp.route("/api/system/features")
@safe_api
@require_auth
def system_features():
    return jsonify(system.check_available_features())


@bp.route("/api/system/thermal")
@safe_api
@require_auth
def thermal():
    return jsonify(system.get_thermal())


@bp.route("/api/system/notifications")
@safe_api
@require_auth
def notifications():
    return jsonify(system.get_notifications())


@bp.route("/api/system/cpu-freq")
@safe_api
@require_auth
def cpu_freq():
    return jsonify(system.get_cpu_freq_details())


# ── 内核参数配置文件 ──

@bp.route("/api/system/kernel-profiles")
@safe_api
@require_auth
def kernel_profiles_list():
    return jsonify({"profiles": system.list_kernel_profiles()})


@bp.route("/api/system/kernel-profiles/save", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def kernel_profiles_save(data):
    return jsonify(system.save_kernel_profile(data["name"], data.get("params")))


@bp.route("/api/system/kernel-profiles/load")
@safe_api
@require_auth
def kernel_profiles_load():
    name = request.args.get("name", "").strip()
    if not name: return jsonify({"error": "name required"}), 400
    return jsonify(system.load_kernel_profile(name))


@bp.route("/api/system/kernel-profiles/apply", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def kernel_profiles_apply(data):
    return jsonify(system.apply_kernel_profile(data["name"]))


@bp.route("/api/system/kernel-profiles/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def kernel_profiles_delete(data):
    return jsonify(system.delete_kernel_profile(data["name"]))


@bp.route("/api/system/kernel-profiles/compare")
@safe_api
@require_auth
def kernel_profiles_compare():
    name = request.args.get("name", "").strip()
    if not name: return jsonify({"error": "name required"}), 400
    return jsonify(system.compare_kernel_profile(name))
