"""System routes."""
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


@bp.route("/api/system/ntp")
@safe_api
@require_auth
def ntp_status():
    return jsonify(system.get_ntp_status())


@bp.route("/api/system/ntp", methods=["POST"])
@safe_api
@require_auth
@validate_json(["enable"])
def ntp_toggle(data):
    return jsonify(system.toggle_ntp(data["enable"]))


@bp.route("/api/system/ulimits")
@safe_api
@require_auth
def ulimits():
    return jsonify(system.get_ulimits())


@bp.route("/api/system/ulimits", methods=["POST"])
@safe_api
@require_auth
@validate_json(["content"])
def save_ulimits(data):
    return jsonify(system.save_ulimits(data["content"]))


@bp.route("/api/system/modules")
@safe_api
@require_auth
def modules():
    return jsonify({"modules": system.get_kernel_modules()})


@bp.route("/api/system/modules/manage", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "action"])
def manage_module(data):
    return jsonify(system.manage_kernel_module(data["name"], data["action"]))


@bp.route("/api/system/swap/disable", methods=["POST"])
@safe_api
@require_auth
def swap_disable():
    return jsonify(system.disable_swap())


@bp.route("/api/system/users")
@safe_api
@require_auth
def users():
    return jsonify({"users": system.get_users()})


@bp.route("/api/system/users/add", methods=["POST"])
@safe_api
@require_auth
@validate_json(["username", "password"])
def user_add(data):
    return jsonify(system.add_user(data["username"], data["password"], data.get("groups", ""), data.get("shell", "/bin/bash")))


@bp.route("/api/system/users/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["username"])
def user_delete(data):
    return jsonify(system.delete_user(data["username"]))


@bp.route("/api/system/users/password", methods=["POST"])
@safe_api
@require_auth
@validate_json(["username", "password"])
def user_password(data):
    return jsonify(system.change_password(data["username"], data["password"]))


@bp.route("/api/system/logs")
@safe_api
@require_auth
def journal_logs():
    try:
        lines = int(request.args.get("lines", "100"))
        lines = max(10, min(lines, 1000))
    except (ValueError, TypeError):
        lines = 100
    unit = request.args.get("unit", "")
    priority = request.args.get("priority", "")
    return jsonify({"logs": system.get_journal_logs(lines, unit, priority)})


@bp.route("/api/system/service-optimize")
@safe_api
@require_auth
def service_optimize_status():
    return jsonify({"services": system.get_service_optimization()})


@bp.route("/api/system/service-optimize", methods=["POST"])
@safe_api
@require_auth
def service_optimize_run():
    return jsonify({"results": system.optimize_services()})


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


# ── Boot & Kernel Tuning ──

@bp.route("/api/system/grub-config")
@safe_api
@require_auth
def grub_config():
    """获取当前 GRUB 配置和可用内核列表。"""
    return jsonify(system.get_grub_config())


@bp.route("/api/system/grub-default", methods=["POST"])
@safe_api
@require_auth
@validate_json(["value"])
def grub_default(data):
    """设置默认启动内核。"""
    out, code = system.set_grub_default(data["value"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/system/grub-cmdline", methods=["POST"])
@safe_api
@require_auth
@validate_json(["params"])
def grub_cmdline(data):
    """设置 GRUB 内核引导参数。"""
    out, code = system.set_grub_cmdline(data["params"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/system/grub-cmdline-presets")
@safe_api
@require_auth
def grub_cmdline_presets():
    """获取引导参数预设列表。"""
    return jsonify({"presets": system.BOOT_PARAM_PRESETS})


@bp.route("/api/system/cpu-governor")
@safe_api
@require_auth
def cpu_governor():
    return jsonify(system.get_cpu_governor())


@bp.route("/api/system/cpu-governor", methods=["POST"])
@safe_api
@require_auth
@validate_json(["governor"])
def cpu_governor_set(data):
    ok, msg = system.set_cpu_governor(data["governor"])
    return jsonify({"success": ok, "message": msg})


@bp.route("/api/system/io-scheduler")
@safe_api
@require_auth
def io_scheduler():
    return jsonify(system.get_io_scheduler())


@bp.route("/api/system/io-scheduler", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device", "scheduler"])
def io_scheduler_set(data):
    ok, msg = system.set_io_scheduler(data["device"], data["scheduler"])
    return jsonify({"success": ok, "message": msg})
