"""Storage operations: LVM, Btrfs, XFS, ext4, ZFS, SMART."""
import os
import re
from typing import Dict, List, Tuple
from utils.helpers import run_cmd, safe_quote


# ═══════════════════ LVM ═══════════════════

def get_lvm_status() -> Dict:
    """获取 LVM 状态：PV、VG、LV。"""
    result = {"installed": False, "pvs": [], "vgs": [], "lvs": []}
    _, code = run_cmd("which lvm 2>/dev/null")
    if code != 0:
        return result
    result["installed"] = True

    # PVs
    out, _ = run_cmd("sudo pvs --noheadings --units g -o pv_name,pv_size,pv_free,pv_vg 2>/dev/null")
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            result["pvs"].append({"name": parts[0], "size": parts[1], "free": parts[2], "vg": parts[3]})

    # VGs
    out, _ = run_cmd("sudo vgs --noheadings --units g -o vg_name,vg_size,vg_free,pv_count,lv_count 2>/dev/null")
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            result["vgs"].append({"name": parts[0], "size": parts[1], "free": parts[2], "pv_count": parts[3], "lv_count": parts[4]})

    # LVs
    out, _ = run_cmd("sudo lvs --noheadings --units g -o lv_name,vg_name,lv_size,pool_lv,data_percent,lv_attr 2>/dev/null")
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            result["lvs"].append({
                "name": parts[0], "vg": parts[1], "size": parts[2],
                "pool": parts[3] if len(parts) > 3 else "",
                "data_percent": parts[4] if len(parts) > 4 else "",
                "attr": parts[-1] if len(parts) > 5 else "",
            })
    return result


def create_pv(device: str) -> Tuple[str, int]:
    if not re.match(r'^/dev/[a-zA-Z0-9_/]+$', device):
        return "Invalid device path", -1
    return run_cmd(f"sudo pvcreate {safe_quote(device)} 2>&1", timeout=30)


def create_vg(name: str, devices: List[str]) -> Tuple[str, int]:
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
        return "Invalid VG name", -1
    devs = " ".join(safe_quote(d) for d in devices)
    return run_cmd(f"sudo vgcreate {safe_quote(name)} {devs} 2>&1", timeout=30)


def extend_vg(name: str, devices: List[str]) -> Tuple[str, int]:
    devs = " ".join(safe_quote(d) for d in devices)
    return run_cmd(f"sudo vgextend {safe_quote(name)} {devs} 2>&1", timeout=30)


def create_lv(name: str, vg: str, size: str) -> Tuple[str, int]:
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', name):
        return "Invalid LV name", -1
    return run_cmd(f"sudo lvcreate -L {safe_quote(size)} -n {safe_quote(name)} {safe_quote(vg)} 2>&1", timeout=30)


def resize_lv(path: str, size: str) -> Tuple[str, int]:
    return run_cmd(f"sudo lvextend -L +{safe_quote(size)} {safe_quote(path)} 2>&1 && sudo resize2fs {safe_quote(path)} 2>&1 || true", timeout=60)


def remove_lv(path: str) -> Tuple[str, int]:
    return run_cmd(f"sudo lvremove -y {safe_quote(path)} 2>&1", timeout=30)


# ═══════════════════ Btrfs ═══════════════════

def get_btrfs_status() -> Dict:
    result = {"installed": False, "filesystems": []}
    _, code = run_cmd("which btrfs 2>/dev/null")
    if code != 0:
        return result
    result["installed"] = True

    out, _ = run_cmd("sudo btrfs filesystem show 2>/dev/null")
    # Parse output — each FS starts with "Label:" then lists devices
    current_fs = None
    for line in out.splitlines():
        if line.startswith("Label:"):
            if current_fs:
                result["filesystems"].append(current_fs)
            current_fs = {"label": line.split("Label:")[-1].strip().strip("'\"") or "(none)", "devices": [], "uuid": ""}
        elif "uuid:" in line:
            if current_fs:
                current_fs["uuid"] = line.split("uuid:")[-1].strip()
        elif line.strip().startswith("devid"):
            parts = line.split()
            for p in parts:
                if p.startswith("/dev/"):
                    if current_fs:
                        current_fs["devices"].append({"path": p, "size": parts[-1] if parts else ""})
    if current_fs:
        result["filesystems"].append(current_fs)

    # Subvolumes
    out2, _ = run_cmd("sudo btrfs subvolume list / 2>/dev/null | head -30")
    # Detect default subvolume ID
    default_out, _ = run_cmd("sudo btrfs subvolume get-default / 2>/dev/null")
    default_id = ""
    if default_out:
        m = re.search(r'ID\s+(\d+)', default_out)
        if m:
            default_id = m.group(1)
    result["subvolumes"] = []
    for line in out2.splitlines():
        parts = line.split()
        if len(parts) >= 9:
            sv_id = parts[1]
            result["subvolumes"].append({
                "id": sv_id, "gen": parts[3], "path": parts[-1],
                "is_default": sv_id == default_id,
            })

    return result


def btrfs_subvolume_create(path: str) -> Tuple[str, int]:
    return run_cmd(f"sudo btrfs subvolume create {safe_quote(path)} 2>&1", timeout=10)


def btrfs_subvolume_delete(path: str) -> Tuple[str, int]:
    return run_cmd(f"sudo btrfs subvolume delete {safe_quote(path)} 2>&1", timeout=10)


def btrfs_subvolume_snapshot(source: str, dest: str, readonly: bool = True) -> Tuple[str, int]:
    ro = "-r" if readonly else ""
    return run_cmd(f"sudo btrfs subvolume snapshot {ro} {safe_quote(source)} {safe_quote(dest)} 2>&1", timeout=30)


def btrfs_scrub(mount: str) -> Tuple[str, int]:
    return run_cmd(f"sudo btrfs scrub start -B {safe_quote(mount)} 2>&1", timeout=300)


def btrfs_balance(mount: str) -> Tuple[str, int]:
    return run_cmd(f"sudo btrfs balance start {safe_quote(mount)} 2>&1", timeout=300)


# ═══════════════════ 文件系统检查 / 修复 ═══════════════════

def get_block_devices_detailed() -> List[Dict]:
    """获取块设备详细信息（含 UUID, LABEL, 使用率）。"""
    out, _ = run_cmd("lsblk -J -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE,LABEL,UUID,MODEL,ROTA 2>/dev/null")
    import json
    try:
        data = json.loads(out)
        return data.get("blockdevices", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def fsck(device: str, fstype: str = "auto", fix: bool = False) -> Tuple[str, int]:
    """运行文件系统检查。fix=True 时自动修复。"""
    if not re.match(r'^/dev/[a-zA-Z0-9_/]+$', device):
        return "Invalid device path", -1
    opts = "-y" if fix else "-n"
    if fstype == "xfs":
        cmd = f"sudo xfs_repair {'-n' if not fix else ''} {safe_quote(device)} 2>&1"
    elif fstype == "btrfs":
        cmd = f"sudo btrfs check {safe_quote(device)} 2>&1"
    elif fstype == "zfs":
        return "ZFS uses 'zpool scrub', not fsck", -1
    else:
        cmd = f"sudo fsck {opts} -t {safe_quote(fstype)} {safe_quote(device)} 2>&1"
    return run_cmd(cmd, timeout=300)


def resize_filesystem(mount: str, size: str = "") -> Tuple[str, int]:
    """扩容文件系统（占用全部可用空间或指定大小）。"""
    # 自动检测 fstype
    fstype_out, _ = run_cmd(f"findmnt -n -o FSTYPE {safe_quote(mount)} 2>/dev/null")
    fstype = fstype_out.strip()
    if fstype == "ext4" or fstype == "ext3":
        cmd = f"sudo resize2fs {safe_quote(mount)}" + (f" {size}" if size else "")
    elif fstype == "xfs":
        cmd = f"sudo xfs_growfs {safe_quote(mount)}"
    elif fstype == "btrfs":
        cmd = f"sudo btrfs filesystem resize max {safe_quote(mount)}"
    else:
        return f"Unsupported filesystem for resize: {fstype}", -1
    return run_cmd(cmd, timeout=60)


def get_filesystem_info(mount: str) -> Dict:
    """获取文件系统详细信息。"""
    info: Dict = {}
    out, _ = run_cmd(f"findmnt -J {safe_quote(mount)} 2>/dev/null")
    import json
    try:
        data = json.loads(out)
        if data.get("filesystems"):
            fs = data["filesystems"][0]
            info = {"source": fs.get("source", ""), "fstype": fs.get("fstype", ""),
                    "mount": fs.get("target", ""), "size": fs.get("size", ""),
                    "used": fs.get("used", ""), "avail": fs.get("avail", ""),
                    "use_percent": fs.get("use%", "")}
    except (json.JSONDecodeError, IndexError, AttributeError):
        pass
    return info


# ═══════════════════ SMART ═══════════════════

def get_smart_status(device: str) -> Dict:
    """获取 SMART 健康状态。"""
    if not re.match(r'^/dev/[a-zA-Z0-9_]+$', device):
        return {"error": "Invalid device"}
    result = {"device": device, "health": "unknown", "attributes": []}
    out, code = run_cmd(f"sudo smartctl -H {safe_quote(device)} 2>&1", timeout=15)
    if code != 0:
        result["error"] = out.strip() or "smartctl failed"
        return result
    for line in out.splitlines():
        if "SMART overall-health" in line or "SMART Health Status" in line:
            result["health"] = "PASSED" if "PASSED" in line or "OK" in line else "FAILED"

    # 详细属性
    out2, _ = run_cmd(f"sudo smartctl -A {safe_quote(device)} 2>/dev/null")
    for line in out2.splitlines():
        m = re.match(r'\s*(\d+)\s+(\S+)\s+\S+\s+\d+\s+\d+\s+\d+\s+\S+\s+\S+\s+\S+\s+(\S+)', line)
        if m:
            result["attributes"].append({"id": m.group(1), "name": m.group(2), "raw": m.group(3)})
    return result


# ═══════════════════ ZFS (basic) ═══════════════════

def get_zfs_status() -> Dict:
    result = {"installed": False, "pools": []}
    _, code = run_cmd("which zpool 2>/dev/null")
    if code != 0:
        return result
    result["installed"] = True
    out, _ = run_cmd("sudo zpool list -H -o name,size,alloc,free,health 2>/dev/null")
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            result["pools"].append({"name": parts[0], "size": parts[1], "alloc": parts[2], "free": parts[3], "health": parts[4]})
    return result


def zfs_list_datasets(pool: str = "") -> List[Dict]:
    datasets = []
    cmd = f"sudo zfs list -H -o name,used,avail,refer,mountpoint 2>/dev/null"
    if pool:
        cmd = f"sudo zfs list -H -o name,used,avail,refer,mountpoint -r {safe_quote(pool)} 2>/dev/null"
    out, _ = run_cmd(cmd)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5:
            datasets.append({"name": parts[0], "used": parts[1], "avail": parts[2], "refer": parts[3], "mountpoint": parts[4]})
    return datasets


def zfs_create_dataset(name: str) -> Tuple[str, int]:
    return run_cmd(f"sudo zfs create {safe_quote(name)} 2>&1", timeout=10)


def zfs_destroy_dataset(name: str) -> Tuple[str, int]:
    return run_cmd(f"sudo zfs destroy {safe_quote(name)} 2>&1", timeout=10)


def zfs_snapshot(dataset: str, snap_name: str) -> Tuple[str, int]:
    return run_cmd(f"sudo zfs snapshot {safe_quote(dataset)}@{safe_quote(snap_name)} 2>&1", timeout=10)


def zfs_rollback(dataset: str, snap_name: str) -> Tuple[str, int]:
    return run_cmd(f"sudo zfs rollback {safe_quote(dataset)}@{safe_quote(snap_name)} 2>&1", timeout=10)


# ═══════════════════ LVM thin pool + snapshot ═══════════════════

def create_thin_pool(name: str, vg: str, size: str) -> Tuple[str, int]:
    return run_cmd(f"sudo lvcreate -L {safe_quote(size)} -T {safe_quote(vg)}/{safe_quote(name)} 2>&1", timeout=30)


def create_thin_lv(name: str, vg: str, pool: str, size: str) -> Tuple[str, int]:
    return run_cmd(f"sudo lvcreate -V {safe_quote(size)} -T {safe_quote(vg)}/{safe_quote(pool)} -n {safe_quote(name)} 2>&1", timeout=30)


def create_lv_snapshot(lv_path: str, snap_name: str, size: str = "5G") -> Tuple[str, int]:
    return run_cmd(f"sudo lvcreate -L {safe_quote(size)} -s -n {safe_quote(snap_name)} {safe_quote(lv_path)} 2>&1", timeout=30)


def remove_vg(name: str) -> Tuple[str, int]:
    return run_cmd(f"sudo vgremove -y {safe_quote(name)} 2>&1", timeout=30)


def remove_pv(device: str) -> Tuple[str, int]:
    return run_cmd(f"sudo pvremove -y {safe_quote(device)} 2>&1", timeout=30)


# ═══════════════════ LUKS ═══════════════════

def get_luks_status() -> Dict:
    result = {"installed": False, "devices": []}
    _, code = run_cmd("which cryptsetup 2>/dev/null")
    if code != 0:
        return result
    result["installed"] = True
    out, _ = run_cmd("lsblk -J -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT 2>/dev/null")
    try:
        import json
        data = json.loads(out)
        for dev in data.get("blockdevices", []):
            for child in dev.get("children", []):
                if child.get("fstype") == "crypto_LUKS":
                    result["devices"].append({
                        "name": child["name"], "size": child.get("size", ""),
                        "parent": dev["name"], "mountpoint": child.get("mountpoint", ""),
                    })
    except (json.JSONDecodeError, KeyError):
        pass
    return result


def luks_open(device: str, name: str, password: str = "") -> Tuple[str, int]:
    """Open a LUKS-encrypted device.

    When a password is provided, it is written to a temporary file with
    restricted permissions (0o600) and passed via --key-file to avoid
    exposing the passphrase in the process list.
    """
    qdev = safe_quote(f"/dev/{device}")
    if not password:
        return run_cmd(f"sudo cryptsetup open {qdev} {safe_quote(name)} 2>&1", timeout=15)

    import tempfile as _tmp
    key_fd = -1
    key_path = None
    try:
        key_fd, key_path = _tmp.mkstemp(prefix="luks_key_")
        os.write(key_fd, password.encode("utf-8"))
        os.close(key_fd)
        key_fd = -1
        os.chmod(key_path, 0o600)
        return run_cmd(
            f"sudo cryptsetup open {qdev} {safe_quote(name)} "
            f"--key-file {safe_quote(key_path)} 2>&1",
            timeout=15
        )
    finally:
        if key_fd >= 0:
            try:
                os.close(key_fd)
            except OSError:
                pass
        if key_path and os.path.exists(key_path):
            try:
                with open(key_path, "wb") as _f:
                    _f.write(b"\x00" * max(len(password), 64))
                os.remove(key_path)
            except OSError:
                pass


def luks_close(name: str) -> Tuple[str, int]:
    return run_cmd(f"sudo cryptsetup close {safe_quote(name)} 2>&1", timeout=10)


# ═══════════════════ Btrfs send/receive ═══════════════════

def btrfs_send(snapshot: str, output_file: str) -> Tuple[str, int]:
    return run_cmd(f"sudo btrfs send {safe_quote(snapshot)} 2>&1 | sudo tee {safe_quote(output_file)} > /dev/null", timeout=300)


def btrfs_receive(input_file: str, target_path: str) -> Tuple[str, int]:
    return run_cmd(f"sudo btrfs receive {safe_quote(target_path)} < {safe_quote(input_file)} 2>&1", timeout=300)


# ═══════════════════ 磁盘性能测试 ═══════════════════

# Destructive test types that will overwrite data on the target device
_DESTRUCTIVE_TEST_TYPES = {"write", "fio-randwrite"}

_DESTRUCTIVE_WARNING = (
    "⚠️  DESTRUCTIVE OPERATION: This test will OVERWRITE data on the target device. "
    "All data on the device will be permanently lost. "
    "Set 'confirm_destructive: true' in the request to proceed."
)


def disk_benchmark(device: str, test_type: str = "read", size: str = "1G",
                   confirm_destructive: bool = False) -> Tuple[str, int]:
    """Run a disk performance benchmark.

    Args:
        device: Block device path (e.g. /dev/sda or sda).
        test_type: One of 'read' (safe), 'write' (destructive),
                   'fio-randread' (safe), 'fio-randwrite' (destructive).
        size: Data size for fio tests (e.g. '1G', '500M').
        confirm_destructive: Must be True for write/fio-randwrite tests.
                             The caller (route layer) MUST obtain explicit user
                             confirmation before passing True.
    """
    if not re.match(r'^(/dev/)?[a-zA-Z0-9_/]+$', device):
        return "Invalid device path", -1
    dev = device if device.startswith("/dev/") else f"/dev/{device}"

    if test_type in _DESTRUCTIVE_TEST_TYPES and not confirm_destructive:
        return _DESTRUCTIVE_WARNING, -1

    if test_type == "read":
        return run_cmd(f"sudo hdparm -t {safe_quote(dev)} 2>&1", timeout=30)
    elif test_type == "write":
        return run_cmd(f"sudo dd if=/dev/zero of={safe_quote(dev)} bs=1M count=1024 oflag=direct 2>&1", timeout=60)
    elif test_type == "fio-randread":
        return run_cmd(
            f"sudo fio --name=randread --rw=randread --bs=4k --size={safe_quote(size)} --filename={safe_quote(dev)} "
            f"--direct=1 --ioengine=libaio --iodepth=32 --runtime=10 --time_based --group_reporting 2>&1",
            timeout=30
        )
    elif test_type == "fio-randwrite":
        return run_cmd(
            f"sudo fio --name=randwrite --rw=randwrite --bs=4k --size={safe_quote(size)} --filename={safe_quote(dev)} "
            f"--direct=1 --ioengine=libaio --iodepth=32 --runtime=10 --time_based --group_reporting 2>&1",
            timeout=30
        )
    return "Unknown test type (read/write/fio-randread/fio-randwrite)", -1


def get_smart_all() -> Dict:
    """获取所有磁盘的 SMART 摘要（含通电时间、重分配扇区，兼容 SATA/NVMe）。"""
    result = {"devices": []}
    out, _ = run_cmd("ls /dev/sd* /dev/nvme* /dev/vd* 2>/dev/null")
    for dev in out.splitlines():
        dev = dev.strip()
        if not dev:
            continue
        # Filter: exclude partitions but keep whole NVMe devices
        name = dev.split("/")[-1]
        is_nvme = name.startswith("nvme")
        is_partition = False
        if is_nvme:
            # nvme0n1 = disk, nvme0n1p1 = partition
            is_partition = "p" in name.replace("nvme", "").split("n", 1)[-1] if "n" in name else False
        else:
            # sda = disk, sda1 = partition
            is_partition = bool(re.search(r'\d$', name))
        if is_partition:
            continue

        is_nvme_drive = is_nvme

        # ── 健康状态 ──
        health, _ = run_cmd(f"sudo smartctl -H {safe_quote(dev)} 2>/dev/null")
        health_str = "unknown"
        if "PASSED" in health or "OK" in health:
            health_str = "PASSED"
        elif "FAIL" in health:
            health_str = "FAILED"

        # ── 属性数据 ──
        attr_out, _ = run_cmd(f"sudo smartctl -A {safe_quote(dev)} 2>/dev/null")
        temperature = ""
        power_on_hours = ""
        reallocated_sectors = ""

        if is_nvme_drive:
            # NVMe: key-value log format
            # Temperature: 40 Celsius
            # Power On Hours: 12,345
            # Media and Data Integrity Errors: 0
            for line in attr_out.splitlines():
                if "Temperature:" in line:
                    nums = re.findall(r'\d+', line)
                    temperature = nums[0] if nums else ""
                elif "Power On Hours:" in line:
                    nums = re.findall(r'\d[\d,]*', line)
                    power_on_hours = nums[0].replace(",", "") if nums else ""
                elif "Media and Data Integrity Errors:" in line:
                    nums = re.findall(r'\d[\d,]*', line)
                    reallocated_sectors = nums[0].replace(",", "") if nums else ""
        else:
            # SATA: table format with attribute IDs
            for line in attr_out.splitlines():
                if re.match(r'\s*9\s', line):
                    parts = line.split()
                    if len(parts) >= 10:
                        power_on_hours = parts[9].replace(",", "")
                elif re.match(r'\s*5\s', line):
                    parts = line.split()
                    if len(parts) >= 10:
                        reallocated_sectors = parts[9].replace(",", "")
            # Temperature from SATA smartctl output
            for line in attr_out.splitlines():
                if 'Temperature_Celsius' in line or 'Temperature' in line:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p in ('194', '190', '231') and i + 9 < len(parts):
                            temperature = parts[i + 9].replace(",", "")
                            break
                    if temperature:
                        break
            # Fallback temperature search
            if not temperature:
                for line in attr_out.splitlines():
                    m = re.search(r'Temperature.*?(\d{2,3})\s*C', line)
                    if m:
                        temperature = m.group(1)
                        break

        result["devices"].append({
            "device": dev,
            "health": health_str,
            "temperature": int(temperature) if str(temperature).isdigit() else temperature,
            "power_on_hours": int(power_on_hours) if str(power_on_hours).isdigit() else power_on_hours,
            "reallocated_sectors": int(reallocated_sectors) if str(reallocated_sectors).isdigit() else reallocated_sectors,
        })
    return result


# ═══════════════════ 格式化分区 ═══════════════════

def _is_mounted(device: str) -> Tuple[bool, str]:
    """Check if a device is currently mounted. Returns (is_mounted, mountpoint)."""
    out, _ = run_cmd(f"findmnt -n -o TARGET --source {safe_quote(device)} 2>/dev/null")
    mp = out.strip()
    return (bool(mp), mp)

def _is_part_of_lvm(device: str) -> bool:
    """Check if device is used as an LVM PV."""
    out, _ = run_cmd(f"sudo pvs --noheadings -o pv_name 2>/dev/null | grep -F '{device}'")
    return bool(out.strip())

def _is_part_of_raid(device: str) -> bool:
    """Check if device is part of a RAID array."""
    out, _ = run_cmd(f"sudo mdadm --examine {safe_quote(device)} 2>/dev/null | grep -c 'mdadm:'")
    return "No md superblock" not in out

def _is_whole_disk(device: str) -> bool:
    """Check if device is a whole disk (not a partition)."""
    name = device.split("/")[-1]
    # NVMe: nvme0n1 (disk) vs nvme0n1p1 (partition)
    if "nvme" in name:
        return "p" not in name.replace("nvme", "").split("n")[-1]
    # sd*: sda (disk) vs sda1 (partition)
    # Also handle mmcblk*, vd*, xvd*, etc.
    out, _ = run_cmd(f"lsblk -n -o TYPE {safe_quote(device)} 2>/dev/null")
    return out.strip() == "disk"

def format_partition(device: str, fstype: str, label: str = "") -> Tuple[str, int]:
    """安全地格式化分区为指定文件系统。

    自动执行安全校验:
    1. 设备路径合法性验证
    2. 设备存在性检查
    3. 拒绝格式化整盘（必须指定分区）
    4. 已挂载时自动卸载
    5. 检测 LVM/RAID 占用并警告

    Args:
        device: 块设备路径 (e.g. /dev/sdb1).
        fstype: 文件系统类型 (ext4, xfs, btrfs, ntfs, vfat, exfat).
        label: 可选卷标。
    """
    # 1. 路径验证
    if not re.match(r'^/dev/[a-zA-Z0-9_/]+$', device):
        return f"无效的设备路径: {device}", -1
    if not os.path.exists(device):
        return f"设备不存在: {device}", -1

    # 2. 拒绝整盘格式化
    if _is_whole_disk(device):
        return f"拒绝格式化整盘 {device}（请指定分区，如 {device}1）", -1

    # 3. LVM 检测
    if _is_part_of_lvm(device):
        return f"设备 {device} 属于 LVM 卷，请先执行 pvremove", -1

    # 4. RAID 检测
    if _is_part_of_raid(device):
        return f"设备 {device} 属于 RAID 阵列，请先停止阵列", -1

    # 5. 自动卸载
    mounted, mp = _is_mounted(device)
    if mounted:
        out, code = run_cmd(f"sudo umount {safe_quote(device)} 2>&1", timeout=15)
        if code != 0:
            return f"无法卸载 {device}（挂载于 {mp}）: {out.strip()}", -1

    # 6. 执行格式化
    fstype = fstype.strip().lower()
    label_opt = f"-L {safe_quote(label)}" if label else ""

    cmd_map = {
        "ext4": f"sudo mkfs.ext4 -F {label_opt} {safe_quote(device)} 2>&1",
        "xfs": f"sudo mkfs.xfs -f {label_opt} {safe_quote(device)} 2>&1",
        "btrfs": f"sudo mkfs.btrfs -f {label_opt} {safe_quote(device)} 2>&1",
        "ntfs": f"sudo mkfs.ntfs -Q {label_opt} {safe_quote(device)} 2>&1",
        "vfat": f"sudo mkfs.vfat -F32 {('-n ' + safe_quote(label)) if label else ''} {safe_quote(device)} 2>&1",
        "exfat": f"sudo mkfs.exfat {('-n ' + safe_quote(label)) if label else ''} {safe_quote(device)} 2>&1",
    }
    cmd = cmd_map.get(fstype)
    if not cmd:
        return f"不支持的文件系统类型: {fstype}", -1

    # 擦除现有签名（避免 mkfs 交互式确认）
    run_cmd(f"sudo wipefs -a {safe_quote(device)} 2>/dev/null", timeout=10)

    out, code = run_cmd(cmd, timeout=120)
    if code == 0:
        return f"✅ {device} 已成功格式化为 {fstype}" + (f" (卷标: {label})" if label else ""), 0
    return f"格式化失败: {out.strip()}", code


# ═══════════════════ Btrfs 碎片整理 / 设备统计 ═══════════════════

def btrfs_defrag(mount: str) -> Tuple[str, int]:
    """对指定 Btrfs 挂载点执行碎片整理。"""
    # Validate mount point exists
    if not os.path.ismount(mount):
        return f"不是有效的挂载点: {mount}", -1
    # Verify it's actually Btrfs
    fstype_out, _ = run_cmd(f"findmnt -n -o FSTYPE {safe_quote(mount)} 2>/dev/null")
    if "btrfs" not in fstype_out.strip().lower():
        return f"挂载点 {mount} 不是 Btrfs 文件系统 (实际: {fstype_out.strip()})", -1
    return run_cmd(f"sudo btrfs filesystem defragment -r {safe_quote(mount)} 2>&1", timeout=600)


def btrfs_device_stats(mount: str) -> Dict:
    """获取 Btrfs 设备统计信息。"""
    result: Dict = {"mount": mount, "devices": [], "error": ""}
    if not os.path.ismount(mount):
        result["error"] = f"不是有效的挂载点: {mount}"
        return result
    out, code = run_cmd(f"sudo btrfs device stats {safe_quote(mount)} 2>/dev/null")
    if code != 0:
        result["error"] = out.strip() or "无法获取设备统计"
        return result
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("["):
            parts = line.split("]", 1)
            if len(parts) == 2:
                result["devices"].append({
                    "device": parts[0].strip("[]"),
                    "stats": parts[1].strip(),
                })
    return result


# ═══════════════════ SMART 自检 ═══════════════════

SMART_TEST_TYPES = {
    "short": "short",
    "long": "long",
    "conveyance": "conveyance",
    "offline": "offline",
}

def smart_self_test(device: str, test_type: str = "short") -> Tuple[str, int]:
    """启动 SMART 自检。"""
    if not re.match(r'^/dev/[a-zA-Z0-9_]+$', device):
        return "Invalid device path", -1
    if test_type not in SMART_TEST_TYPES:
        return f"Invalid test type: {test_type} (use: {', '.join(SMART_TEST_TYPES)})", -1
    return run_cmd(f"sudo smartctl -t {safe_quote(test_type)} {safe_quote(device)} 2>&1", timeout=15)


def smart_test_progress(device: str) -> Dict:
    """获取 SMART 自检进度。"""
    if not re.match(r'^/dev/[a-zA-Z0-9_]+$', device):
        return {"error": "Invalid device path"}
    out, _ = run_cmd(f"sudo smartctl -c {safe_quote(device)} 2>/dev/null")
    result: Dict = {"device": device, "progress": "", "remaining": "", "status": ""}
    for line in out.splitlines():
        if "Self-test execution status" in line:
            result["status"] = line.split(":")[-1].strip().rstrip(")")
        if "remaining" in line.lower() and "%" in line:
            m = re.search(r'(\d+%)', line)
            if m: result["progress"] = m.group(1)
    return result


def smart_self_test_log(device: str) -> Dict:
    """获取 SMART 自检日志。"""
    if not re.match(r'^/dev/[a-zA-Z0-9_]+$', device):
        return {"error": "Invalid device path"}
    out, _ = run_cmd(f"sudo smartctl -l selftest {safe_quote(device)} 2>/dev/null")
    entries = []
    in_table = False
    for line in out.splitlines():
        if "Num " in line and "Test_Description" in line:
            in_table = True; continue
        if in_table and line.strip():
            parts = line.split()
            if len(parts) >= 4 and parts[0].startswith("#"):
                entries.append({
                    "num": parts[0].lstrip("#"),
                    "description": " ".join(parts[1:3]),
                    "status": parts[3] if len(parts) > 3 else "",
                    "remaining": parts[4] if len(parts) > 4 else "",
                })
        elif in_table and not line.strip():
            break
    return {"device": device, "entries": entries[-20:]}


# ═══════════════════ IO 监控 ═══════════════════

def get_io_stats() -> Dict:
    """获取实时 IO 统计（iostat 风格）。"""
    result: Dict = {"devices": [], "cpu_iowait": 0}

    # CPU iowait
    try:
        with open("/proc/stat") as f:
            for line in f:
                if line.startswith("cpu "):
                    parts = line.split()
                    if len(parts) >= 6:
                        # iowait is the 6th field
                        result["cpu_iowait"] = int(parts[5])
                    break
    except Exception:
        pass

    # Disk stats from /proc/diskstats
    try:
        with open("/proc/diskstats") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 14:
                    name = parts[2]
                    # Filter: only real block devices
                    if any(name.startswith(p) for p in ("loop", "ram", "dm-")):
                        continue
                    result["devices"].append({
                        "name": name,
                        "reads": int(parts[3]),
                        "reads_merged": int(parts[4]),
                        "sectors_read": int(parts[5]),
                        "read_ms": int(parts[6]),
                        "writes": int(parts[7]),
                        "writes_merged": int(parts[8]),
                        "sectors_written": int(parts[9]),
                        "write_ms": int(parts[10]),
                        "ios_in_progress": int(parts[11]),
                        "io_ms": int(parts[12]),
                        "io_ms_weighted": int(parts[13]),
                    })
    except Exception:
        pass

    return result


# ═══════════════════ 磁盘性能历史 ═══════════════════

import json as _json
import time as _time

_BENCHMARK_HISTORY_FILE = os.path.expanduser("~/.tuxtacklebox/benchmark_history.json")


def get_benchmark_history() -> List[Dict]:
    """获取历史性能测试记录。"""
    if not os.path.isfile(_BENCHMARK_HISTORY_FILE):
        return []
    try:
        with open(_BENCHMARK_HISTORY_FILE) as f:
            return _json.load(f)
    except Exception:
        return []


def save_benchmark_result(device: str, test_type: str, result: str) -> None:
    """保存性能测试结果到历史记录。"""
    history = get_benchmark_history()
    entry = {
        "device": device,
        "test_type": test_type,
        "result": result.strip()[:500],
        "timestamp": int(_time.time()),
        "date": _time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    history.append(entry)
    history = history[-100:]
    os.makedirs(os.path.dirname(_BENCHMARK_HISTORY_FILE), exist_ok=True)
    try:
        with open(_BENCHMARK_HISTORY_FILE, 'w') as f:
            _json.dump(history, f, indent=2)
    except Exception:
        pass
