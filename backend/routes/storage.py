"""Storage routes: LVM, Btrfs, XFS, ext4, ZFS, SMART."""
from flask import Blueprint, jsonify, request
from utils.helpers import safe_api, validate_json, require_auth, run_cmd, safe_quote
from core import storage

bp = Blueprint("storage", __name__)


@bp.route("/api/storage/lvm")
@safe_api
@require_auth
def lvm_status():
    return jsonify(storage.get_lvm_status())


@bp.route("/api/storage/lvm/pv", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device"])
def pv_create(data):
    out, code = storage.create_pv(data["device"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/lvm/vg", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "devices"])
def vg_create(data):
    out, code = storage.create_vg(data["name"], data["devices"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/lvm/vg/extend", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "devices"])
def vg_extend(data):
    out, code = storage.extend_vg(data["name"], data["devices"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/lvm/lv", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "vg", "size"])
def lv_create(data):
    out, code = storage.create_lv(data["name"], data["vg"], data["size"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/lvm/lv/resize", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path", "size"])
def lv_resize(data):
    out, code = storage.resize_lv(data["path"], data["size"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/lvm/lv/remove", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path"])
def lv_remove(data):
    out, code = storage.remove_lv(data["path"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/btrfs")
@safe_api
@require_auth
def btrfs_status():
    return jsonify(storage.get_btrfs_status())


@bp.route("/api/storage/btrfs/subvolume", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path"])
def subvolume_create(data):
    out, code = storage.btrfs_subvolume_create(data["path"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/btrfs/subvolume/delete", methods=["POST"])
@safe_api
@require_auth
@validate_json(["path"])
def subvolume_delete(data):
    out, code = storage.btrfs_subvolume_delete(data["path"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/btrfs/snapshot", methods=["POST"])
@safe_api
@require_auth
@validate_json(["source", "dest"])
def snapshot_create(data):
    out, code = storage.btrfs_subvolume_snapshot(data["source"], data["dest"], data.get("readonly", True))
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/btrfs/scrub", methods=["POST"])
@safe_api
@require_auth
@validate_json(["mount"])
def scrub(data):
    out, code = storage.btrfs_scrub(data["mount"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/fsck", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device"])
def fsck_run(data):
    out, code = storage.fsck(data["device"], data.get("fstype", "auto"), data.get("fix", False))
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/resize", methods=["POST"])
@safe_api
@require_auth
@validate_json(["mount"])
def fs_resize(data):
    out, code = storage.resize_filesystem(data["mount"], data.get("size", ""))
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/fs-info")
@safe_api
@require_auth
def fs_info():
    mount = request.args.get("mount", "/").strip()
    if not mount:
        mount = "/"
    return jsonify(storage.get_filesystem_info(mount))


@bp.route("/api/storage/smart")
@safe_api
@require_auth
def smart_status():
    device = request.args.get("device", "").strip()
    if not device:
        return jsonify({"error": "device required"}), 400
    return jsonify(storage.get_smart_status(device))


@bp.route("/api/storage/zfs")
@safe_api
@require_auth
def zfs_status():
    return jsonify(storage.get_zfs_status())


@bp.route("/api/storage/devices")
@safe_api
@require_auth
def devices_detailed():
    return jsonify({"devices": storage.get_block_devices_detailed()})


# ── LVM thin + snapshot + management ──

@bp.route("/api/storage/lvm/thin-pool", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "vg", "size"])
def thin_pool(data):
    out, code = storage.create_thin_pool(data["name"], data["vg"], data["size"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/lvm/thin-lv", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name", "vg", "pool", "size"])
def thin_lv(data):
    out, code = storage.create_thin_lv(data["name"], data["vg"], data["pool"], data["size"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/lvm/snapshot", methods=["POST"])
@safe_api
@require_auth
@validate_json(["lv_path", "snap_name"])
def lv_snapshot(data):
    out, code = storage.create_lv_snapshot(data["lv_path"], data["snap_name"], data.get("size", "5G"))
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/lvm/vg/remove", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def vg_remove(data):
    out, code = storage.remove_vg(data["name"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/lvm/pv/remove", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device"])
def pv_remove(data):
    out, code = storage.remove_pv(data["device"])
    return jsonify({"success": code == 0, "message": out})


# ── LUKS ──

@bp.route("/api/storage/luks")
@safe_api
@require_auth
def luks_status():
    return jsonify(storage.get_luks_status())


@bp.route("/api/storage/luks/open", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device", "name"])
def luks_open(data):
    out, code = storage.luks_open(data["device"], data["name"], data.get("password", ""))
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/luks/close", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def luks_close(data):
    out, code = storage.luks_close(data["name"])
    return jsonify({"success": code == 0, "message": out})


# ── ZFS datasets ──

@bp.route("/api/storage/zfs/datasets")
@safe_api
@require_auth
def zfs_datasets():
    pool = request.args.get("pool", "").strip()
    return jsonify({"datasets": storage.zfs_list_datasets(pool)})


@bp.route("/api/storage/zfs/dataset/create", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def zfs_create(data):
    out, code = storage.zfs_create_dataset(data["name"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/zfs/dataset/destroy", methods=["POST"])
@safe_api
@require_auth
@validate_json(["name"])
def zfs_destroy(data):
    out, code = storage.zfs_destroy_dataset(data["name"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/zfs/snapshot", methods=["POST"])
@safe_api
@require_auth
@validate_json(["dataset", "snap_name"])
def zfs_snap(data):
    out, code = storage.zfs_snapshot(data["dataset"], data["snap_name"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/zfs/rollback", methods=["POST"])
@safe_api
@require_auth
@validate_json(["dataset", "snap_name"])
def zfs_roll(data):
    out, code = storage.zfs_rollback(data["dataset"], data["snap_name"])
    return jsonify({"success": code == 0, "message": out})


# ── Btrfs send/receive ──

@bp.route("/api/storage/btrfs/send", methods=["POST"])
@safe_api
@require_auth
@validate_json(["snapshot", "output"])
def btrfs_send(data):
    out, code = storage.btrfs_send(data["snapshot"], data["output"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/btrfs/receive", methods=["POST"])
@safe_api
@require_auth
@validate_json(["input", "target"])
def btrfs_receive(data):
    out, code = storage.btrfs_receive(data["input"], data["target"])
    return jsonify({"success": code == 0, "message": out})


# ── 磁盘性能 ──

@bp.route("/api/storage/benchmark", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device"])
def benchmark(data):
    out, code = storage.disk_benchmark(
        data["device"],
        data.get("test_type", "read"),
        data.get("size", "1G"),
        confirm_destructive=data.get("confirm_destructive", False),
    )
    return jsonify({"success": code == 0, "message": out})


# ── SMART 摘要 ──

@bp.route("/api/storage/smart-all")
@safe_api
@require_auth
def smart_all():
    return jsonify(storage.get_smart_all())


# ── 格式化分区 ──

@bp.route("/api/storage/format", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device", "fstype"])
def format_partition(data):
    out, code = storage.format_partition(
        data["device"], data["fstype"], data.get("label", "")
    )
    return jsonify({"success": code == 0, "message": out})


# ── Btrfs 碎片整理 / 设备统计 ──

@bp.route("/api/storage/btrfs/defrag", methods=["POST"])
@safe_api
@require_auth
@validate_json(["mount"])
def btrfs_defrag(data):
    out, code = storage.btrfs_defrag(data["mount"])
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/btrfs/device-stats")
@safe_api
@require_auth
def btrfs_device_stats():
    mount = request.args.get("mount", "/").strip()
    return jsonify(storage.btrfs_device_stats(mount))


# ── SMART 自检 ──

@bp.route("/api/storage/smart/test", methods=["POST"])
@safe_api
@require_auth
@validate_json(["device"])
def smart_test_start(data):
    out, code = storage.smart_self_test(data["device"], data.get("test_type", "short"))
    return jsonify({"success": code == 0, "message": out})


@bp.route("/api/storage/smart/progress")
@safe_api
@require_auth
def smart_test_progress():
    device = request.args.get("device", "").strip()
    if not device:
        return jsonify({"error": "device required"}), 400
    return jsonify(storage.smart_test_progress(device))


@bp.route("/api/storage/smart/test-log")
@safe_api
@require_auth
def smart_test_log():
    device = request.args.get("device", "").strip()
    if not device:
        return jsonify({"error": "device required"}), 400
    return jsonify(storage.smart_self_test_log(device))


# ── 性能历史 ──

@bp.route("/api/storage/benchmark/history")
@safe_api
@require_auth
def benchmark_history():
    return jsonify({"history": storage.get_benchmark_history()})


# ── IO 监控 ──

@bp.route("/api/storage/io-stats")
@safe_api
@require_auth
def io_stats():
    return jsonify(storage.get_io_stats())
