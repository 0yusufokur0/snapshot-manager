#!/usr/bin/env python3
"""Snapshot Manager GUI - GTK4 + Adwaita based interface"""

import sys
import os

# If not root, restart with pkexec (one-time password)
if os.geteuid() != 0:
    script = os.path.abspath(__file__)
    # Detect user's theme preference (to pass to root)
    try:
        import subprocess as _sp
        _cs = _sp.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                      capture_output=True, text=True, timeout=5).stdout.strip().strip("'")
    except Exception:
        _cs = ""
    os.execvp("pkexec", ["pkexec", "env",
                          f"DISPLAY={os.environ.get('DISPLAY', ':0')}",
                          f"XAUTHORITY={os.environ.get('XAUTHORITY', '')}",
                          f"XDG_RUNTIME_DIR={os.environ.get('XDG_RUNTIME_DIR', '')}",
                          f"DBUS_SESSION_BUS_ADDRESS={os.environ.get('DBUS_SESSION_BUS_ADDRESS', '')}",
                          f"HOME={os.environ.get('HOME', '')}",
                          f"SNAPSHOT_COLOR_SCHEME={_cs}",
                          sys.executable, script] + sys.argv[1:])

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Gio
import subprocess
import re
import threading
import json

# ─── Translations ──────────────────────────────────────────
TRANSLATIONS = {
    "en": {
        # Window & Header
        "app.title": "Snapshot Manager",
        "tooltip.create": "Create New Snapshot",
        "tooltip.refresh": "Refresh",
        "tooltip.settings": "Settings",
        "tooltip.status": "System Status",
        "loading.label": "Operation in progress...",

        # Snapshot types
        "type.system": "System",
        "type.full": "Full",

        # List page
        "disk.warning": "Disk space is running low!",
        "disk.settings": "Settings",
        "disk.status_title": "Disk Status",
        "disk.loading": "Loading...",
        "disk.used": "Used: {used} / {total} ({pct}%)",
        "disk.free": "Free: {avail} · Snapshot space: {snap_size}",
        "disk.location": "Storage Location",
        "snap.group_title": "Snapshots",
        "snap.count": "{count} snapshot(s) available",
        "snap.empty_title": "No Snapshots Yet",
        "snap.empty_desc": "Click the + button to create your first snapshot.",
        "snap.locked_tooltip": "Locked",

        # Progress page
        "progress.title": "Creating Snapshot",
        "progress.preparing": "Preparing...",
        "progress.cancelling": "Cancelling...",
        "progress.cancel": "Cancel",
        "progress.copying": "Copying files...",
        "progress.kernel": "Copying kernel...",
        "progress.grub": "Updating GRUB...",
        "progress.manifest": "Generating manifest...",
        "progress.hardlinks": "Using hardlinks...",
        "progress.completed": "Completed!",
        "progress.files": "{done} / {total} files",
        "progress.creating_type": "Creating {type_label} Snapshot",
        "progress.cancelled": "Cancelled.",

        # Create dialog
        "create.title": "New Snapshot",
        "create.settings_group": "Snapshot Settings",
        "create.type": "Type",
        "create.type_system": "System (excluding home)",
        "create.type_full": "Full (including home)",
        "create.description": "Description (optional)",
        "create.location": "Storage Location",
        "create.button": "Create Snapshot",

        # Detail dialog
        "detail.info": "Information",
        "detail.name": "Name",
        "detail.type": "Type",
        "detail.date": "Date",
        "detail.kernel": "Kernel",
        "detail.description": "Description",
        "detail.status": "Status",
        "detail.locked": "Locked",
        "detail.unlocked": "Unlocked",
        "detail.size": "Size",
        "detail.actions": "Actions",
        "detail.unlock": "Unlock",
        "detail.lock": "Lock",
        "detail.verify": "Verify",
        "detail.delete": "Delete",
        "detail.unlock_subtitle": "Allow automatic deletion of the snapshot",
        "detail.lock_subtitle": "Protect the snapshot from automatic deletion",
        "detail.verify_subtitle": "Check snapshot integrity",
        "detail.restore": "Restore",
        "detail.restore_subtitle": "Extract from archive for GRUB boot restore",
        "detail.restoring": "Restoring...",
        "detail.restore_result": "Restore Result",
        "detail.archived_notice": "This snapshot is archived. Restore it to make it available for GRUB boot restore.",
        "detail.delete_subtitle": "Permanently delete this snapshot",
        "detail.delete_locked": "Unlock first",
        "detail.locking": "Locking...",
        "detail.unlocking": "Unlocking...",
        "detail.verifying": "Verifying...",
        "detail.deleting": "Deleting...",

        # Delete confirmation
        "delete.title": "Delete Snapshot?",
        "delete.body": "'{name}' will be permanently deleted.\nThis action cannot be undone.",
        "delete.cancel": "Cancel",
        "delete.confirm": "Delete",

        # Messages
        "msg.success": "Success",
        "msg.error": "Error",
        "msg.ok": "OK",
        "msg.created": "Snapshot created successfully.",
        "msg.unknown_error": "Unknown error",
        "msg.verify_result": "Verification Result",
        "msg.timeout": "Operation timed out (10 minutes).",
        "msg.not_found": "snapshot-manager command not found. Was install.sh run?",
        "msg.check_result": "Check Result",

        # Storage labels
        "snap.storage_local": "Local",
        "snap.storage_archived": "Archived",
        "snap.storage_both": "Local + Archived",

        # Check
        "tooltip.check": "Integrity Check",
        "check.running": "Running integrity check...",

        # Settings dialog
        "settings.title": "Settings",
        "settings.save": "Save",
        "settings.location": "Default Storage Location",
        "settings.location_desc": "All snapshots are saved to this disk. Changing the disk will move existing snapshots.",
        "settings.current": "(current)",
        "settings.snap_dir": "Snapshot directory: {path}",
        "settings.general": "General",
        "settings.language": "Language",
        "settings.low_priority": "Low Priority (I/O)",
        "settings.low_priority_desc": "Reduce system slowdown during snapshot",
        "settings.manifest": "SHA256 Manifest",
        "settings.manifest_desc": "Generate integrity hash after snapshot",
        "settings.retention_limits": "Retention Limits",
        "settings.unlimited": "0 = unlimited",
        "settings.max_system": "Max System Snapshots",
        "settings.max_full": "Max Full Snapshots",
        "settings.retention_policy": "Retention Policy",
        "settings.disabled": "0 = disabled",
        "settings.keep_daily": "Daily Retention",
        "settings.keep_weekly": "Weekly Retention",
        "settings.keep_monthly": "Monthly Retention",
        "settings.scheduled": "Scheduled Backup",
        "settings.daily_timer": "Daily Timer",
        "settings.weekly_timer": "Weekly Timer",
        "settings.daily_desc": "Automatic system snapshot every day at 02:00",
        "settings.weekly_desc": "Automatic full snapshot every Sunday at 03:00",
        "settings.saved": "Settings saved.",
        "settings.save_failed": "Failed to save settings.",
        "settings.lang_restart": "Language will change on next launch.",

        # Migration
        "migrate.calculating": "Calculating snapshot sizes...",
        "migrate.title": "Migrate Snapshots?",
        "migrate.body": "{count} snapshot(s) found ({size}).\nAvailable space on target: {avail}.\n\nMove snapshots to the new location?",
        "migrate.move": "Migrate",
        "migrate.change_only": "Change Directory Only",
        "migrate.cancel": "Cancel",
        "migrate.progress_title": "Migrating Snapshots",
        "migrate.progress_label": "Migrating snapshots...",
        "migrate.complete_title": "Migration Complete",
        "migrate.complete_body": "Snapshots migrated successfully.\nGRUB menu updated.",
        "migrate.dir_changed": "Storage location changed.",
        "migrate.not_enough_space": "Not enough space on target disk.",

        # Status dialog
        "status.title": "System Status",
        "status.disk": "Snapshot Disk",
        "status.location": "Location",
        "status.total": "Total",
        "status.used": "Used",
        "status.free": "Free",
        "status.snap_space": "Snapshot Space",
        "status.counts": "Snapshot Counts",
        "status.system": "System",
        "status.full": "Full",
        "status.total_count": "Total",
        "status.locked": "Locked",
        "status.archived": "Archived",
        "status.archive_size": "Archive Size",
    },
    "tr": {
        # Window & Header
        "app.title": "Snapshot Yöneticisi",
        "tooltip.create": "Yeni Snapshot Oluştur",
        "tooltip.refresh": "Yenile",
        "tooltip.settings": "Ayarlar",
        "tooltip.status": "Sistem Durumu",
        "loading.label": "İşlem devam ediyor...",

        # Snapshot types
        "type.system": "Sistem",
        "type.full": "Tam",

        # List page
        "disk.warning": "Disk alanı azalıyor!",
        "disk.settings": "Ayarlar",
        "disk.status_title": "Disk Durumu",
        "disk.loading": "Yükleniyor...",
        "disk.used": "Kullanılan: {used} / {total} ({pct}%)",
        "disk.free": "Boş: {avail} · Snapshot alanı: {snap_size}",
        "disk.location": "Kayıt Yeri",
        "snap.group_title": "Snapshot'lar",
        "snap.count": "{count} snapshot mevcut",
        "snap.empty_title": "Henüz Snapshot Yok",
        "snap.empty_desc": "İlk snapshot'ınızı oluşturmak için + butonuna tıklayın.",
        "snap.locked_tooltip": "Kilitli",

        # Progress page
        "progress.title": "Snapshot Oluşturuluyor",
        "progress.preparing": "Hazırlanıyor...",
        "progress.cancelling": "İptal ediliyor...",
        "progress.cancel": "İptal",
        "progress.copying": "Dosyalar kopyalanıyor...",
        "progress.kernel": "Kernel kopyalanıyor...",
        "progress.grub": "GRUB güncelleniyor...",
        "progress.manifest": "Manifest oluşturuluyor...",
        "progress.hardlinks": "Hardlink kullanılıyor...",
        "progress.completed": "Tamamlandı!",
        "progress.files": "{done} / {total} dosya",
        "progress.creating_type": "{type_label} Snapshot Oluşturuluyor",
        "progress.cancelled": "İptal edildi.",

        # Create dialog
        "create.title": "Yeni Snapshot",
        "create.settings_group": "Snapshot Ayarları",
        "create.type": "Tip",
        "create.type_system": "Sistem (home hariç)",
        "create.type_full": "Tam (home dahil)",
        "create.description": "Açıklama (isteğe bağlı)",
        "create.location": "Kayıt Yeri",
        "create.button": "Snapshot Oluştur",

        # Detail dialog
        "detail.info": "Bilgiler",
        "detail.name": "İsim",
        "detail.type": "Tip",
        "detail.date": "Tarih",
        "detail.kernel": "Kernel",
        "detail.description": "Açıklama",
        "detail.status": "Durum",
        "detail.locked": "Kilitli",
        "detail.unlocked": "Kilitsiz",
        "detail.size": "Boyut",
        "detail.actions": "İşlemler",
        "detail.unlock": "Kilidi Kaldır",
        "detail.lock": "Kilitle",
        "detail.verify": "Doğrula",
        "detail.delete": "Sil",
        "detail.unlock_subtitle": "Snapshot'ın otomatik silinmesine izin ver",
        "detail.lock_subtitle": "Snapshot'ı otomatik silmeden koru",
        "detail.verify_subtitle": "Snapshot bütünlüğünü kontrol et",
        "detail.restore": "Geri Yükle",
        "detail.restore_subtitle": "Arşivden çıkar, GRUB ile geri yükleme için hazırla",
        "detail.restoring": "Geri yükleniyor...",
        "detail.restore_result": "Geri Yükleme Sonucu",
        "detail.archived_notice": "Bu snapshot arşivlenmiş. GRUB ile geri yüklemek için önce 'Geri Yükle' butonuna tıklayın.",
        "detail.delete_subtitle": "Bu snapshot'ı kalıcı olarak sil",
        "detail.delete_locked": "Önce kilidi kaldırın",
        "detail.locking": "Kilitleniyor...",
        "detail.unlocking": "Kilit kaldırılıyor...",
        "detail.verifying": "Doğrulanıyor...",
        "detail.deleting": "Siliniyor...",

        # Delete confirmation
        "delete.title": "Snapshot Silinsin mi?",
        "delete.body": "'{name}' kalıcı olarak silinecek.\nBu işlem geri alınamaz.",
        "delete.cancel": "İptal",
        "delete.confirm": "Sil",

        # Messages
        "msg.success": "Başarılı",
        "msg.error": "Hata",
        "msg.ok": "Tamam",
        "msg.created": "Snapshot başarıyla oluşturuldu.",
        "msg.unknown_error": "Bilinmeyen hata",
        "msg.verify_result": "Doğrulama Sonucu",
        "msg.timeout": "İşlem zaman aşımına uğradı (10 dakika).",
        "msg.not_found": "snapshot-manager komutu bulunamadı. install.sh çalıştırıldı mı?",
        "msg.check_result": "Kontrol Sonucu",

        # Storage labels
        "snap.storage_local": "Yerel",
        "snap.storage_archived": "Arşiv",
        "snap.storage_both": "Yerel + Arşiv",

        # Check
        "tooltip.check": "Bütünlük Kontrolü",
        "check.running": "Bütünlük kontrolü yapılıyor...",

        # Settings dialog
        "settings.title": "Ayarlar",
        "settings.save": "Kaydet",
        "settings.location": "Varsayılan Kayıt Yeri",
        "settings.location_desc": "Tüm snapshot'lar bu diske kaydedilir. Disk değiştirilirse mevcut snapshot'lar taşınır.",
        "settings.current": "(mevcut)",
        "settings.snap_dir": "Snapshot dizini: {path}",
        "settings.general": "Genel",
        "settings.language": "Dil",
        "settings.low_priority": "Düşük Öncelik (I/O)",
        "settings.low_priority_desc": "Snapshot sırasında sistem yavaşlamasını azalt",
        "settings.manifest": "SHA256 Manifest",
        "settings.manifest_desc": "Snapshot sonrası bütünlük hash'i oluştur",
        "settings.retention_limits": "Saklama Limitleri",
        "settings.unlimited": "0 = sınırsız",
        "settings.max_system": "Maks Sistem Snapshot",
        "settings.max_full": "Maks Tam Snapshot",
        "settings.retention_policy": "Saklama Politikası",
        "settings.disabled": "0 = devre dışı",
        "settings.keep_daily": "Günlük Saklama",
        "settings.keep_weekly": "Haftalık Saklama",
        "settings.keep_monthly": "Aylık Saklama",
        "settings.scheduled": "Zamanlanmış Yedekleme",
        "settings.daily_timer": "Günlük Zamanlayıcı",
        "settings.weekly_timer": "Haftalık Zamanlayıcı",
        "settings.daily_desc": "Her gün 02:00'de otomatik sistem snapshot'ı",
        "settings.weekly_desc": "Her Pazar 03:00'te otomatik tam snapshot",
        "settings.saved": "Ayarlar kaydedildi.",
        "settings.save_failed": "Ayarlar kaydedilemedi.",
        "settings.lang_restart": "Dil değişikliği yeniden başlatmayla uygulanacak.",

        # Migration
        "migrate.calculating": "Snapshot boyutları hesaplanıyor...",
        "migrate.title": "Snapshot'lar Taşınsın mı?",
        "migrate.body": "{count} snapshot bulundu ({size}).\nHedefte kullanılabilir alan: {avail}.\n\nSnapshot'lar yeni konuma taşınsın mı?",
        "migrate.move": "Taşı",
        "migrate.change_only": "Sadece Dizini Değiştir",
        "migrate.cancel": "İptal",
        "migrate.progress_title": "Snapshot'lar Taşınıyor",
        "migrate.progress_label": "Snapshot'lar taşınıyor...",
        "migrate.complete_title": "Taşıma Tamamlandı",
        "migrate.complete_body": "Snapshot'lar başarıyla taşındı.\nGRUB menüsü güncellendi.",
        "migrate.dir_changed": "Kayıt yeri değiştirildi.",
        "migrate.not_enough_space": "Hedef diskte yeterli alan yok.",

        # Status dialog
        "status.title": "Sistem Durumu",
        "status.disk": "Snapshot Diski",
        "status.location": "Konum",
        "status.total": "Toplam",
        "status.used": "Kullanılan",
        "status.free": "Boş",
        "status.snap_space": "Snapshot Alanı",
        "status.counts": "Snapshot Sayıları",
        "status.system": "Sistem",
        "status.full": "Tam",
        "status.total_count": "Toplam",
        "status.locked": "Kilitli",
        "status.archived": "Arşivlenmiş",
        "status.archive_size": "Arşiv Boyutu",
    },
}

_current_lang = "en"

def _(key, **kwargs):
    """Get translated string by key. Falls back to English if key not found."""
    text = TRANSLATIONS.get(_current_lang, TRANSLATIONS["en"]).get(key)
    if text is None:
        text = TRANSLATIONS["en"].get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text

def set_language(lang):
    """Set current language. Falls back to 'en' if invalid."""
    global _current_lang
    _current_lang = lang if lang in TRANSLATIONS else "en"

# Disk space warning threshold (percentage)
DISK_WARN_PCT = 85


class SnapshotInfo:
    """Holds information about a single snapshot."""
    def __init__(self, path=None, archived_name=None):
        self.path = path or ""
        self.name = ""
        self.type = ""
        self.date = ""
        self.kernel = ""
        self.description = ""
        self.locked = False
        self.size = ""
        self.storage = "local"  # "local", "archived", "local+arch"
        if path:
            self._parse()
        elif archived_name:
            self._parse_from_name(archived_name)

    def _parse_from_name(self, name):
        """Parse type and date from snapshot name (for archived-only snapshots)."""
        self.name = name
        self.storage = "archived"
        if name.startswith("full_"):
            self.type = "full"
            self.date = name[5:]
        elif name.startswith("system_"):
            self.type = "system"
            self.date = name[7:]

    def _parse(self):
        info_file = os.path.join(self.path, "info.conf")
        if not os.path.isfile(info_file):
            return
        with open(info_file, "r") as f:
            for line in f:
                line = line.strip()
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key == "NAME":
                    self.name = val
                elif key == "TYPE":
                    self.type = val
                elif key == "DATE":
                    self.date = val
                elif key == "KERNEL":
                    self.kernel = val
                elif key == "DESCRIPTION":
                    self.description = val
                elif key == "LOCKED":
                    self.locked = val.lower() == "true"

    @property
    def type_label(self):
        return _("type.system") if self.type == "system" else _("type.full")

    @property
    def display_date(self):
        try:
            parts = self.date.split("_")
            d = parts[0].split("-")
            t = parts[1].split("-")
            return f"{d[2]}.{d[1]}.{d[0]} {t[0]}:{t[1]}"
        except (IndexError, ValueError):
            return self.date


def read_config():
    """Reads the config file."""
    config = {
        "SNAPSHOT_DIR": "/snapshots",
        "MAX_SYSTEM_SNAPSHOTS": "0",
        "MAX_FULL_SNAPSHOTS": "0",
        "KEEP_DAILY": "0",
        "KEEP_WEEKLY": "0",
        "KEEP_MONTHLY": "0",
        "LOW_PRIORITY": "true",
        "GENERATE_MANIFEST": "false",
        "LANGUAGE": "en",
        "ARCHIVE_MODE": "none",
        "BORG_REPO": "",
        "BORG_COMPRESSION": "zstd,3",
        "BORG_KEEP_DAILY": "7",
        "BORG_KEEP_WEEKLY": "4",
        "BORG_KEEP_MONTHLY": "6",
        "MAX_RECENT_RSYNC": "3",
    }
    conf_path = "/etc/snapshot-manager.conf"
    if os.path.isfile(conf_path):
        with open(conf_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key in config:
                        config[key] = val
    return config


def get_snapshots(snapshot_dir):
    """Returns all snapshots in the snapshot directory."""
    snapshots = []
    if not os.path.isdir(snapshot_dir):
        return snapshots
    for entry in sorted(os.listdir(snapshot_dir), reverse=True):
        full = os.path.join(snapshot_dir, entry)
        if os.path.isdir(full) and not entry.startswith("."):
            info_file = os.path.join(full, "info.conf")
            if os.path.isfile(info_file):
                snapshots.append(SnapshotInfo(full))
    return snapshots


def get_archived_names(config):
    """Returns set of archived snapshot names from borg repository."""
    snapshot_dir = config.get("SNAPSHOT_DIR", "/snapshots")
    borg_repo = config.get("BORG_REPO", "") or os.path.join(snapshot_dir, ".borg-repo")
    archive_mode = config.get("ARCHIVE_MODE", "none")
    if archive_mode != "borg" or not os.path.isdir(borg_repo):
        return set()
    try:
        env = {**os.environ,
               "BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK": "yes",
               "BORG_RELOCATED_REPO_ACCESS_IS_OK": "yes"}
        result = subprocess.run(
            ["borg", "list", "--short", borg_repo],
            capture_output=True, text=True, timeout=30, env=env
        )
        if result.returncode == 0:
            return set(line.strip() for line in result.stdout.strip().split("\n") if line.strip())
    except Exception:
        pass
    return set()


def get_archive_size(config):
    """Returns human-readable size of borg repository."""
    snapshot_dir = config.get("SNAPSHOT_DIR", "/snapshots")
    borg_repo = config.get("BORG_REPO", "") or os.path.join(snapshot_dir, ".borg-repo")
    if not os.path.isdir(borg_repo):
        return None
    try:
        result = subprocess.run(
            ["du", "-sh", borg_repo],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.split()[0]
    except Exception:
        pass
    return None


def get_disk_info(snapshot_dir):
    """Returns disk information for the partition where the snapshot directory resides."""
    try:
        # Get partition info for the snapshot directory
        target = snapshot_dir if os.path.isdir(snapshot_dir) else "/"
        st = os.statvfs(target)
        total = st.f_frsize * st.f_blocks
        avail = st.f_frsize * st.f_bavail
        used = total - avail
        pct = int(used / total * 100) if total > 0 else 0

        snap_size = "0"
        if os.path.isdir(snapshot_dir):
            result = subprocess.run(
                ["du", "-sh", snapshot_dir],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                snap_size = result.stdout.split()[0]

        return {
            "total": _human_size(total),
            "used": _human_size(used),
            "avail": _human_size(avail),
            "avail_bytes": avail,
            "pct": pct,
            "snap_size": snap_size,
        }
    except Exception:
        return {"total": "?", "used": "?", "avail": "?", "avail_bytes": 0, "pct": 0, "snap_size": "?"}


def _human_size(b):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def get_available_drives():
    """Returns a list of mountable disks/partitions."""
    drives = []
    try:
        result = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT,LABEL,MODEL"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return drives
        data = json.loads(result.stdout)
        for dev in data.get("blockdevices", []):
            _collect_parts(dev, drives, dev.get("model") or "")
    except Exception:
        pass
    return drives


def _collect_parts(dev, drives, model):
    """Recursively collects partitions."""
    dtype = dev.get("type", "")
    fstype = dev.get("fstype") or ""
    name = dev.get("name", "")
    size = dev.get("size", "")
    mountpoint = dev.get("mountpoint") or ""
    label = dev.get("label") or ""

    if dtype == "part" and fstype and fstype not in ("swap", "BitLocker", "squashfs"):
        if label:
            display = f"{label} ({name}) - {size} [{fstype}]"
        elif mountpoint:
            display = f"{mountpoint} ({name}) - {size} [{fstype}]"
        else:
            display = f"/dev/{name} - {size} [{fstype}]"
        if model:
            display += f" · {model}"
        drives.append({
            "name": name, "size": size, "fstype": fstype,
            "mountpoint": mountpoint, "label": label,
            "model": model, "display": display,
        })
    elif dtype == "disk" and fstype and fstype not in ("swap", "BitLocker", "squashfs") \
            and not dev.get("children"):
        display = f"/dev/{name} - {size} [{fstype}]"
        if model:
            display += f" · {model}"
        drives.append({
            "name": name, "size": size, "fstype": fstype,
            "mountpoint": mountpoint, "label": label,
            "model": model, "display": display,
        })

    for child in dev.get("children", []):
        _collect_parts(child, drives, model)


def run_cmd(args):
    """Runs a snapshot-manager command as root."""
    cmd = ["snapshot-manager"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", _("msg.timeout"), 1
    except FileNotFoundError:
        return "", _("msg.not_found"), 1


def parse_rsync_progress(line):
    """Parses file counts and percentage from rsync --info=progress2 output.
    to-chk = full list ready (reliable), ir-chk = incremental (total may change).
    Byte percentage is always stable, so use it as the main percentage.
    """
    parts = line.split('\r')
    last = parts[-1].strip()

    result = {}

    # Byte percentage (main percentage - always increases stably)
    m_pct = re.search(r'(\d+)%', last)
    if m_pct:
        result["byte_pct"] = int(m_pct.group(1))

    # File counts
    m_to = re.search(r'xfr#(\d+),\s*to-chk=(\d+)/(\d+)', last)
    m_ir = re.search(r'xfr#(\d+),\s*ir-chk=(\d+)/(\d+)', last)

    if m_to:
        # to-chk: full list ready, reliable
        remaining = int(m_to.group(2))
        total = int(m_to.group(3))
        done = total - remaining
        result["done"] = done
        result["total"] = total
        result["stable"] = True
    elif m_ir:
        # ir-chk: incremental, total not yet certain
        remaining = int(m_ir.group(2))
        total = int(m_ir.group(3))
        done = total - remaining
        result["done"] = done
        result["total"] = total
        result["stable"] = False

    if result:
        return result
    return None


def get_snapshot_dir_size_bytes(snapshot_dir):
    """Returns the total size of the snapshot directory in bytes."""
    try:
        result = subprocess.run(
            ["du", "-sb", snapshot_dir],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return int(result.stdout.split()[0])
    except Exception:
        pass
    return 0


class SnapshotRow(Adw.ActionRow):
    """A single row in the snapshot list."""
    def __init__(self, snap):
        super().__init__()
        self.snap = snap
        self.set_title(snap.name)
        subtitle_parts = [snap.display_date, snap.type_label]
        if snap.description:
            subtitle_parts.append(snap.description)
        self.set_subtitle(" · ".join(subtitle_parts))

        if snap.locked:
            lock_icon = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
            lock_icon.set_tooltip_text(_("snap.locked_tooltip"))
            self.add_prefix(lock_icon)

        if snap.storage == "archived":
            type_icon = Gtk.Image.new_from_icon_name("folder-download-symbolic")
            type_icon.set_tooltip_text(_("snap.storage_archived"))
        elif snap.type == "system":
            type_icon = Gtk.Image.new_from_icon_name("computer-symbolic")
            type_icon.set_tooltip_text(snap.type_label)
        else:
            type_icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
            type_icon.set_tooltip_text(snap.type_label)
        self.add_prefix(type_icon)
        self.set_activatable(True)


class SnapshotManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.snapshot.manager",
                         flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.config = read_config()
        set_language(self.config.get("LANGUAGE", "en"))

    def do_activate(self):
        # Apply the user's theme preference
        color_scheme = os.environ.get("SNAPSHOT_COLOR_SCHEME", "")
        style_mgr = self.get_style_manager()
        if color_scheme == "prefer-dark":
            style_mgr.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        elif color_scheme == "prefer-light":
            style_mgr.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)

        self.win = SnapshotManagerWindow(self)
        self.win.present()


class SnapshotManagerWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_("app.title"))
        self.app = app
        self.config = app.config
        self.set_default_size(800, 600)
        self._create_cancel = False

        # Main layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self.main_box)

        # Header bar
        header = Adw.HeaderBar()
        self.main_box.append(header)

        create_btn = Gtk.Button(icon_name="list-add-symbolic")
        create_btn.set_tooltip_text(_("tooltip.create"))
        create_btn.add_css_class("suggested-action")
        create_btn.connect("clicked", self._on_create_clicked)
        header.pack_start(create_btn)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("tooltip.refresh"))
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_start(refresh_btn)

        settings_btn = Gtk.Button(icon_name="emblem-system-symbolic")
        settings_btn.set_tooltip_text(_("tooltip.settings"))
        settings_btn.connect("clicked", self._on_settings_clicked)
        header.pack_end(settings_btn)

        check_btn = Gtk.Button(icon_name="emblem-ok-symbolic")
        check_btn.set_tooltip_text(_("tooltip.check"))
        check_btn.connect("clicked", self._on_check_clicked)
        header.pack_end(check_btn)

        status_btn = Gtk.Button(icon_name="dialog-information-symbolic")
        status_btn.set_tooltip_text(_("tooltip.status"))
        status_btn.connect("clicked", self._on_status_clicked)
        header.pack_end(status_btn)

        # Content
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.main_box.append(self.content_stack)

        self._build_list_page()
        self._build_empty_page()
        self._build_progress_page()

        # Loading page
        spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                              valign=Gtk.Align.CENTER, spacing=12)
        spinner = Gtk.Spinner(spinning=True, width_request=48, height_request=48)
        spinner_box.append(spinner)
        spinner_label = Gtk.Label(label=_("loading.label"))
        spinner_label.add_css_class("title-3")
        spinner_box.append(spinner_label)
        self.spinner_label = spinner_label
        self.content_stack.add_named(spinner_box, "loading")

        self._refresh_list()

    def _build_list_page(self):
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        self.list_clamp = Adw.Clamp(maximum_size=900)
        scrolled.set_child(self.list_clamp)

        self.list_box_outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                      margin_top=16, margin_bottom=16,
                                      margin_start=16, margin_end=16,
                                      spacing=12)
        self.list_clamp.set_child(self.list_box_outer)

        # Disk warning banner (initially hidden)
        self.disk_warn_bar = Adw.Banner(title=_("disk.warning"))
        self.disk_warn_bar.set_revealed(False)
        self.disk_warn_bar.set_button_label(_("disk.settings"))
        self.disk_warn_bar.connect("button-clicked", self._on_settings_clicked)
        self.list_box_outer.append(self.disk_warn_bar)

        # Disk info card
        self.disk_group = Adw.PreferencesGroup(title=_("disk.status_title"))
        self.disk_row = Adw.ActionRow(title=_("disk.loading"))
        self.disk_group.add(self.disk_row)
        self.list_box_outer.append(self.disk_group)

        # Snapshot list
        self.snap_group = Adw.PreferencesGroup(title=_("snap.group_title"))
        self.list_box_outer.append(self.snap_group)

        self.content_stack.add_named(scrolled, "list")

    def _build_empty_page(self):
        status = Adw.StatusPage(
            icon_name="drive-harddisk-symbolic",
            title=_("snap.empty_title"),
            description=_("snap.empty_desc")
        )
        self.content_stack.add_named(status, "empty")

    def _build_progress_page(self):
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                               valign=Gtk.Align.CENTER,
                               halign=Gtk.Align.CENTER,
                               spacing=20, width_request=450,
                               margin_start=32, margin_end=32)

        icon = Gtk.Image.new_from_icon_name("drive-harddisk-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("dim-label")
        progress_box.append(icon)

        self.progress_title = Gtk.Label(label=_("progress.title"))
        self.progress_title.add_css_class("title-2")
        progress_box.append(self.progress_title)

        self.progress_stage = Gtk.Label(label=_("progress.preparing"))
        self.progress_stage.add_css_class("title-4")
        self.progress_stage.add_css_class("dim-label")
        progress_box.append(self.progress_stage)

        self.progress_pct_label = Gtk.Label(label="%0")
        self.progress_pct_label.add_css_class("title-1")
        progress_box.append(self.progress_pct_label)

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_size_request(400, -1)
        progress_box.append(self.progress_bar)

        self.progress_files_label = Gtk.Label(label=_("progress.files", done="0", total="0"))
        self.progress_files_label.add_css_class("title-4")
        progress_box.append(self.progress_files_label)

        self.progress_log = Gtk.Label(label="")
        self.progress_log.set_wrap(True)
        self.progress_log.set_max_width_chars(60)
        self.progress_log.add_css_class("caption")
        self.progress_log.add_css_class("dim-label")
        progress_box.append(self.progress_log)

        cancel_btn = Gtk.Button(label=_("progress.cancel"))
        cancel_btn.add_css_class("destructive-action")
        cancel_btn.add_css_class("pill")
        cancel_btn.set_halign(Gtk.Align.CENTER)
        cancel_btn.set_size_request(120, -1)
        cancel_btn.set_margin_top(8)
        cancel_btn.connect("clicked", self._on_cancel_create)
        self.progress_cancel_btn = cancel_btn
        progress_box.append(cancel_btn)

        self.content_stack.add_named(progress_box, "progress")

    def _on_cancel_create(self, _btn):
        self._create_cancel = True
        self.progress_stage.set_label(_("progress.cancelling"))
        self.progress_cancel_btn.set_sensitive(False)

    def _refresh_list(self):
        local_snaps = get_snapshots(self.config["SNAPSHOT_DIR"])
        archived_names = get_archived_names(self.config)

        # Merge: set storage attribute, add archived-only snapshots
        local_names = set(s.name for s in local_snaps)
        for snap in local_snaps:
            snap.storage = "local+arch" if snap.name in archived_names else "local"

        # Add archived-only snapshots
        archived_only = archived_names - local_names
        for name in sorted(archived_only, reverse=True):
            local_snaps.append(SnapshotInfo(archived_name=name))

        # Sort by name (newest first)
        snapshots = sorted(local_snaps, key=lambda s: s.name, reverse=True)

        disk = get_disk_info(self.config["SNAPSHOT_DIR"])

        # Disk warning
        if disk["pct"] >= DISK_WARN_PCT:
            self.disk_warn_bar.set_title(
                f"{_('disk.warning')} "
                f"({disk['pct']}% full, {disk['avail']} free)"
            )
            self.disk_warn_bar.set_revealed(True)
        else:
            self.disk_warn_bar.set_revealed(False)

        # Recreate disk rows
        self.disk_group.remove(self.disk_row)
        if hasattr(self, 'disk_dir_row'):
            self.disk_group.remove(self.disk_dir_row)

        self.disk_row = Adw.ActionRow(
            title=_("disk.used", used=disk['used'], total=disk['total'], pct=disk['pct']),
            subtitle=_("disk.free", avail=disk['avail'], snap_size=disk['snap_size'])
        )
        pbar = Gtk.LevelBar(
            min_value=0, max_value=100, value=disk['pct'],
            valign=Gtk.Align.CENTER, width_request=120
        )
        self.disk_row.add_suffix(pbar)
        self.disk_group.add(self.disk_row)

        self.disk_dir_row = Adw.ActionRow(
            title=_("disk.location"),
            subtitle=self.config['SNAPSHOT_DIR']
        )
        self.disk_dir_row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))
        self.disk_group.add(self.disk_dir_row)

        # Snapshot list
        self.list_box_outer.remove(self.snap_group)
        self.snap_group = Adw.PreferencesGroup(
            title=_("snap.group_title"),
            description=_("snap.count", count=len(snapshots))
        )
        self.list_box_outer.append(self.snap_group)

        if not snapshots:
            self.content_stack.set_visible_child_name("empty")
            return

        for snap in snapshots:
            row = SnapshotRow(snap)
            row.connect("activated", self._on_row_activated)

            # Storage badge
            if snap.storage == "local+arch":
                badge = Gtk.Label(label=_("snap.storage_both"))
            elif snap.storage == "archived":
                badge = Gtk.Label(label=_("snap.storage_archived"))
            else:
                badge = Gtk.Label(label=_("snap.storage_local"))
            badge.add_css_class("dim-label")
            badge.add_css_class("caption")
            row.add_suffix(badge)

            # Size (only for local snapshots)
            if snap.storage != "archived" and snap.path:
                try:
                    result = subprocess.run(
                        ["du", "-sh", snap.path],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        size = result.stdout.split()[0]
                        size_label = Gtk.Label(label=size)
                        size_label.add_css_class("dim-label")
                        row.add_suffix(size_label)
                except Exception:
                    pass

            arrow = Gtk.Image.new_from_icon_name("go-next-symbolic")
            row.add_suffix(arrow)
            self.snap_group.add(row)

        self.content_stack.set_visible_child_name("list")

    def _on_refresh(self, _btn):
        self._refresh_list()

    def _on_row_activated(self, row):
        self._show_snapshot_detail(row.snap)

    # ─── Snapshot creation ──────────────────────────────────

    def _on_create_clicked(self, _btn):
        """New snapshot - always to default storage location."""
        dialog = Adw.Dialog(title=_("create.title"))
        dialog.set_content_width(500)
        dialog.set_content_height(300)

        toolbar_view = Adw.ToolbarView()
        dialog.set_child(toolbar_view)
        toolbar_view.add_top_bar(Adw.HeaderBar())

        clamp = Adw.Clamp(maximum_size=450)
        toolbar_view.set_content(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                      margin_top=24, margin_bottom=24,
                      margin_start=24, margin_end=24,
                      spacing=16)
        clamp.set_child(box)

        group = Adw.PreferencesGroup(title=_("create.settings_group"))
        box.append(group)

        type_row = Adw.ComboRow(title=_("create.type"))
        type_model = Gtk.StringList.new([_("create.type_system"), _("create.type_full")])
        type_row.set_model(type_model)
        group.add(type_row)

        desc_row = Adw.EntryRow(title=_("create.description"))
        group.add(desc_row)

        # Storage location info (display only)
        dir_row = Adw.ActionRow(
            title=_("create.location"),
            subtitle=self.config["SNAPSHOT_DIR"]
        )
        dir_row.add_prefix(Gtk.Image.new_from_icon_name("folder-symbolic"))
        group.add(dir_row)

        create_btn = Gtk.Button(label=_("create.button"))
        create_btn.add_css_class("suggested-action")
        create_btn.add_css_class("pill")
        create_btn.set_margin_top(12)
        create_btn.set_halign(Gtk.Align.CENTER)
        create_btn.set_size_request(200, -1)

        def on_create(btn):
            snap_type = "system" if type_row.get_selected() == 0 else "full"
            desc = desc_row.get_text().strip()
            args = ["create", snap_type]
            if desc:
                args.append(desc)
            dialog.close()
            self._start_snapshot_create(snap_type, desc)

        create_btn.connect("clicked", on_create)
        box.append(create_btn)
        dialog.present(self)

    def _start_snapshot_create(self, snap_type, description):
        """Snapshot creation with progress tracking - always to config's SNAPSHOT_DIR."""
        self._create_cancel = False
        self._progress_max_pct = 0
        self._progress_max_done = 0
        self._progress_last_total = 0
        self.progress_bar.set_fraction(0)
        self.progress_pct_label.set_label("%0")
        self.progress_files_label.set_label(_("progress.files", done="0", total="0"))
        self.progress_stage.set_label(_("progress.preparing"))
        self.progress_log.set_label("")
        self.progress_cancel_btn.set_sensitive(True)
        type_label = _("type.system") if snap_type == "system" else _("type.full")
        self.progress_title.set_label(_("progress.creating_type", type_label=type_label))
        self.content_stack.set_visible_child_name("progress")

        def run():
            try:
                args = ["create", snap_type]
                if description:
                    args.append(description)
                cmd = ["snapshot-manager"] + args

                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False
                )

                import select
                buffer = b""
                fd = proc.stdout.fileno()
                while True:
                    if self._create_cancel:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        GLib.idle_add(self._create_done, -1, _("progress.cancelled"), "")
                        return

                    ready, _, _ = select.select([fd], [], [], 0.1)
                    if not ready:
                        if proc.poll() is not None:
                            break
                        continue

                    data = os.read(fd, 4096)
                    if not data:
                        break

                    buffer += data
                    while b'\r' in buffer or b'\n' in buffer:
                        # Cut at whichever of \r or \n comes first
                        idx_r = buffer.find(b'\r')
                        idx_n = buffer.find(b'\n')
                        if idx_r == -1:
                            idx = idx_n
                        elif idx_n == -1:
                            idx = idx_r
                        else:
                            idx = min(idx_r, idx_n)
                        line = buffer[:idx].decode('utf-8', errors='replace')
                        buffer = buffer[idx + 1:]
                        if line.strip():
                            self._process_output_line(line)

                if buffer:
                    line = buffer.decode('utf-8', errors='replace')
                    if line.strip():
                        self._process_output_line(line)

                rc = proc.wait()
                stderr = proc.stderr.read().decode('utf-8', errors='replace')
                GLib.idle_add(self._create_done, rc, "", stderr)
            except Exception as e:
                GLib.idle_add(self._create_done, 1, "", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _process_output_line(self, line):
        clean = re.sub(r'\033\[[0-9;]*m', '', line).strip()
        if not clean:
            return

        progress = parse_rsync_progress(line)
        if progress:
            GLib.idle_add(self._update_progress, progress)
            return

        if "kopyalaniyor" in clean.lower() or "rsync" in clean.lower():
            GLib.idle_add(self.progress_stage.set_label, _("progress.copying"))
        elif "kernel" in clean.lower() or "initramfs" in clean.lower():
            GLib.idle_add(self.progress_stage.set_label, _("progress.kernel"))
        elif "grub" in clean.lower():
            GLib.idle_add(self.progress_stage.set_label, _("progress.grub"))
        elif "sha256" in clean.lower() or "manifest" in clean.lower():
            GLib.idle_add(self.progress_stage.set_label, _("progress.manifest"))
        elif "hardlink" in clean.lower():
            GLib.idle_add(self.progress_stage.set_label, _("progress.hardlinks"))
        elif "completed" in clean.lower() or "tamamlandi" in clean.lower():
            GLib.idle_add(self._update_progress, {"byte_pct": 100, "done": 0, "total": 0})
            GLib.idle_add(self.progress_stage.set_label, _("progress.completed"))

        if len(clean) < 100:
            GLib.idle_add(self.progress_log.set_label, clean)

    def _update_progress(self, info):
        # Main percentage: byte-based (stable, never goes backwards)
        byte_pct = info.get("byte_pct", 0)
        pct = max(byte_pct, self._progress_max_pct)
        self._progress_max_pct = pct

        fraction = min(pct / 100.0, 1.0)
        self.progress_bar.set_fraction(fraction)
        self.progress_pct_label.set_label(f"%{pct}")

        # File count: only show in increasing direction
        done = info.get("done", 0)
        total = info.get("total", 0)
        if total > 0:
            # done should never go backwards
            done = max(done, self._progress_max_done)
            self._progress_max_done = done
            # total: update if stable (to-chk), otherwise keep the largest
            if info.get("stable", False) or total > self._progress_last_total:
                self._progress_last_total = total
            show_total = self._progress_last_total
            show_done = min(done, show_total)
            self.progress_files_label.set_label(
                _("progress.files", done=f"{show_done:,}".replace(",", "."), total=f"{show_total:,}".replace(",", "."))
            )

    def _create_done(self, rc, stdout, stderr):
        self._refresh_list()
        if rc == 0:
            self._show_message(_("msg.success"), _("msg.created"))
        elif rc == -1:
            pass
        else:
            msg = stderr or stdout or _("msg.unknown_error")
            msg = re.sub(r'\033\[[0-9;]*m', '', msg)
            self._show_message(_("msg.error"), msg.strip(), error=True)

    # ─── Snapshot detail ──────────────────────────────────────

    def _show_snapshot_detail(self, snap):
        dialog = Adw.Dialog(title=snap.name)
        dialog.set_content_width(500)
        dialog.set_content_height(450)

        toolbar_view = Adw.ToolbarView()
        dialog.set_child(toolbar_view)
        toolbar_view.add_top_bar(Adw.HeaderBar())

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        toolbar_view.set_content(scrolled)

        clamp = Adw.Clamp(maximum_size=500)
        scrolled.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                      margin_top=16, margin_bottom=16,
                      margin_start=16, margin_end=16, spacing=12)
        clamp.set_child(box)

        info_group = Adw.PreferencesGroup(title=_("detail.info"))
        box.append(info_group)
        info_group.add(self._info_row(_("detail.name"), snap.name))
        info_group.add(self._info_row(_("detail.type"), snap.type_label))
        info_group.add(self._info_row(_("detail.date"), snap.display_date))
        info_group.add(self._info_row(_("detail.kernel"), snap.kernel))
        info_group.add(self._info_row(_("detail.description"), snap.description))
        info_group.add(self._info_row(_("detail.status"), _("detail.locked") if snap.locked else _("detail.unlocked")))

        # Storage type
        if snap.storage == "local+arch":
            storage_label = _("snap.storage_both")
        elif snap.storage == "archived":
            storage_label = _("snap.storage_archived")
        else:
            storage_label = _("snap.storage_local")
        info_group.add(self._info_row("Storage", storage_label))

        if snap.storage != "archived" and snap.path:
            try:
                result = subprocess.run(
                    ["du", "-sh", snap.path], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    info_group.add(self._info_row(_("detail.size"), result.stdout.split()[0]))
            except Exception:
                pass

        # Archived notice
        if snap.storage == "archived":
            notice_group = Adw.PreferencesGroup()
            box.append(notice_group)
            notice_row = Adw.ActionRow(
                title=_("detail.archived_notice"),
                icon_name="dialog-warning-symbolic"
            )
            notice_row.add_css_class("warning")
            notice_group.add(notice_row)

        actions_group = Adw.PreferencesGroup(title=_("detail.actions"))
        box.append(actions_group)

        # Restore button (for archived snapshots)
        if snap.storage in ("archived", "local+arch"):
            restore_row = Adw.ActionRow(title=_("detail.restore"),
                                        subtitle=_("detail.restore_subtitle"))
            restore_row.add_prefix(Gtk.Image.new_from_icon_name("folder-download-symbolic"))
            restore_btn = Gtk.Button(label=_("detail.restore"), valign=Gtk.Align.CENTER)
            restore_btn.add_css_class("suggested-action")
            if snap.storage == "local+arch":
                restore_btn.set_sensitive(False)
                restore_btn.set_tooltip_text(_("snap.storage_local"))
            restore_btn.connect("clicked", lambda b: self._do_restore(snap.name, dialog))
            restore_row.add_suffix(restore_btn)
            restore_row.set_activatable_widget(restore_btn)
            actions_group.add(restore_row)

        # Lock/Unlock (only for local snapshots)
        if snap.storage != "archived":
            if snap.locked:
                lock_row = Adw.ActionRow(title=_("detail.unlock"),
                                         subtitle=_("detail.unlock_subtitle"))
                lock_row.add_prefix(Gtk.Image.new_from_icon_name("changes-allow-symbolic"))
                lock_btn = Gtk.Button(label=_("detail.unlock"), valign=Gtk.Align.CENTER)
                lock_btn.connect("clicked", lambda b: self._do_action(
                    ["unlock", snap.name], _("detail.unlocking"), dialog))
                lock_row.add_suffix(lock_btn)
                lock_row.set_activatable_widget(lock_btn)
            else:
                lock_row = Adw.ActionRow(title=_("detail.lock"),
                                         subtitle=_("detail.lock_subtitle"))
                lock_row.add_prefix(Gtk.Image.new_from_icon_name("changes-prevent-symbolic"))
                lock_btn = Gtk.Button(label=_("detail.lock"), valign=Gtk.Align.CENTER)
                lock_btn.connect("clicked", lambda b: self._do_action(
                    ["lock", snap.name], _("detail.locking"), dialog))
                lock_row.add_suffix(lock_btn)
                lock_row.set_activatable_widget(lock_btn)
            actions_group.add(lock_row)

        # Verify (only for local snapshots)
        if snap.storage != "archived":
            verify_row = Adw.ActionRow(title=_("detail.verify"),
                                       subtitle=_("detail.verify_subtitle"))
            verify_row.add_prefix(Gtk.Image.new_from_icon_name("emblem-ok-symbolic"))
            verify_btn = Gtk.Button(label=_("detail.verify"), valign=Gtk.Align.CENTER)
            verify_btn.connect("clicked", lambda b: self._do_verify(snap.name, dialog))
            verify_row.add_suffix(verify_btn)
            verify_row.set_activatable_widget(verify_btn)
            actions_group.add(verify_row)

        # Delete (works for both local and archived)
        delete_row = Adw.ActionRow(title=_("detail.delete"), subtitle=_("detail.delete_subtitle"))
        delete_row.add_prefix(Gtk.Image.new_from_icon_name("user-trash-symbolic"))
        delete_btn = Gtk.Button(label=_("detail.delete"), valign=Gtk.Align.CENTER)
        delete_btn.add_css_class("destructive-action")
        if snap.locked:
            delete_btn.set_sensitive(False)
            delete_btn.set_tooltip_text(_("detail.delete_locked"))
        delete_btn.connect("clicked", lambda b: self._confirm_delete(snap, dialog))
        delete_row.add_suffix(delete_btn)
        delete_row.set_activatable_widget(delete_btn)
        actions_group.add(delete_row)

        dialog.present(self)

    def _info_row(self, title, value):
        return Adw.ActionRow(title=title, subtitle=value or "-")

    def _confirm_delete(self, snap, parent_dialog):
        alert = Adw.AlertDialog(
            heading=_("delete.title"),
            body=_("delete.body", name=snap.name),
        )
        alert.add_response("cancel", _("delete.cancel"))
        alert.add_response("delete", _("delete.confirm"))
        alert.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_default_response("cancel")
        alert.set_close_response("cancel")
        alert.connect("response", lambda d, r: self._on_delete_response(r, snap, parent_dialog))
        alert.present(self)

    def _on_delete_response(self, response, snap, parent_dialog):
        if response == "delete":
            self._do_action(["delete", snap.name], _("detail.deleting"), parent_dialog)

    # ─── Simple action ───────────────────────────────────────

    def _do_action(self, args, message, close_dialog=None):
        if close_dialog:
            close_dialog.close()
        self.spinner_label.set_label(message)
        self.content_stack.set_visible_child_name("loading")

        def run():
            try:
                stdout, stderr, rc = run_cmd(args)
                GLib.idle_add(self._action_done, rc, stdout, stderr)
            except Exception as e:
                GLib.idle_add(self._action_done, 1, "", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _action_done(self, rc, stdout, stderr):
        self._refresh_list()
        if rc != 0:
            self._show_message(_("msg.error"), stderr or stdout or _("msg.unknown_error"), error=True)

    def _do_verify(self, name, parent_dialog):
        if parent_dialog:
            parent_dialog.close()
        self.spinner_label.set_label(_("detail.verifying"))
        self.content_stack.set_visible_child_name("loading")

        def run():
            try:
                stdout, stderr, rc = run_cmd(["verify", name])
                GLib.idle_add(self._verify_done, rc, stdout, stderr)
            except Exception as e:
                GLib.idle_add(self._verify_done, 1, "", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _verify_done(self, rc, stdout, stderr):
        self._refresh_list()
        clean = re.sub(r'\033\[[0-9;]*m', '', stdout)
        self._show_message(_("msg.verify_result"), clean.strip())

    def _do_restore(self, name, parent_dialog):
        if parent_dialog:
            parent_dialog.close()
        self.spinner_label.set_label(_("detail.restoring"))
        self.content_stack.set_visible_child_name("loading")

        def run():
            try:
                stdout, stderr, rc = run_cmd(["restore", name])
                GLib.idle_add(self._restore_done, rc, stdout, stderr)
            except Exception as e:
                GLib.idle_add(self._restore_done, 1, "", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _restore_done(self, rc, stdout, stderr):
        self._refresh_list()
        clean = re.sub(r'\033\[[0-9;]*m', '', stdout + stderr)
        if rc == 0:
            self._show_message(_("detail.restore_result"), clean.strip())
        else:
            self._show_message(_("msg.error"), clean.strip(), error=True)

    # ─── Integrity check ─────────────────────────────────────

    def _on_check_clicked(self, _btn):
        self.spinner_label.set_label(_("check.running"))
        self.content_stack.set_visible_child_name("loading")

        def run():
            try:
                stdout, stderr, rc = run_cmd(["check"])
                GLib.idle_add(self._check_done, rc, stdout, stderr)
            except Exception as e:
                GLib.idle_add(self._check_done, 1, "", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _check_done(self, rc, stdout, stderr):
        self._refresh_list()
        clean = re.sub(r'\033\[[0-9;]*m', '', stdout + stderr)
        self._show_message(_("msg.check_result"), clean.strip())

    # ─── Settings ─────────────────────────────────────────────

    def _on_settings_clicked(self, _btn):
        self.config = read_config()

        dialog = Adw.Dialog(title=_("settings.title"))
        dialog.set_content_width(850)
        dialog.set_content_height(650)

        toolbar_view = Adw.ToolbarView()
        dialog.set_child(toolbar_view)

        settings_header = Adw.HeaderBar()
        save_header_btn = Gtk.Button(label=_("settings.save"))
        save_header_btn.add_css_class("suggested-action")
        save_header_btn.set_sensitive(False)  # Inactive when no changes
        settings_header.pack_end(save_header_btn)
        toolbar_view.add_top_bar(settings_header)

        def mark_dirty(*_args):
            save_header_btn.set_sensitive(True)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        toolbar_view.set_content(scrolled)

        clamp = Adw.Clamp(maximum_size=800)
        scrolled.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                      margin_top=16, margin_bottom=16,
                      margin_start=16, margin_end=16, spacing=12)
        clamp.set_child(box)

        # ─── Default Storage Location (radio button) ───
        disk_group = Adw.PreferencesGroup(
            title=_("settings.location"),
            description=_("settings.location_desc")
        )
        box.append(disk_group)

        drives = get_available_drives()
        drive_checks = []
        drive_paths = []
        check_group = None
        current_dir = self.config["SNAPSHOT_DIR"]

        for i, drv in enumerate(drives):
            mp = drv["mountpoint"]
            if mp:
                path = os.path.join(mp, "snapshots") if mp != "/" else "/snapshots"
            else:
                path = f"/mnt/{drv['name']}/snapshots"
            drive_paths.append(path)

            is_current = (path == current_dir)

            title = drv["display"]
            if is_current:
                title += " " + _("settings.current")
            subtitle = _("settings.snap_dir", path=path)

            row = Adw.ActionRow(title=title, subtitle=subtitle)
            row.set_subtitle_lines(2)
            row.set_title_lines(2)

            check = Gtk.CheckButton()
            check.set_valign(Gtk.Align.CENTER)
            if is_current:
                check.set_active(True)
            if check_group is None:
                check_group = check
            else:
                check.set_group(check_group)

            check.connect("toggled", mark_dirty)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            disk_group.add(row)
            drive_checks.append(check)

        # If current dir matches no drive, select the first one
        if check_group and not any(c.get_active() for c in drive_checks):
            drive_checks[0].set_active(True)

        # General settings
        gen_group = Adw.PreferencesGroup(title=_("settings.general"))
        box.append(gen_group)

        lang_row = Adw.ComboRow(title=_("settings.language"))
        lang_model = Gtk.StringList.new(["English", "Türkçe"])
        lang_row.set_model(lang_model)
        lang_row.set_selected(0 if self.config.get("LANGUAGE", "en") == "en" else 1)
        lang_row.connect("notify::selected", mark_dirty)
        gen_group.add(lang_row)

        low_prio_row = Adw.ActionRow(
            title=_("settings.low_priority"),
            subtitle=_("settings.low_priority_desc")
        )
        low_prio_switch = Gtk.Switch(
            active=self.config["LOW_PRIORITY"].lower() == "true",
            valign=Gtk.Align.CENTER
        )
        low_prio_switch.connect("state-set", mark_dirty)
        low_prio_row.add_suffix(low_prio_switch)
        gen_group.add(low_prio_row)

        manifest_row = Adw.ActionRow(
            title=_("settings.manifest"),
            subtitle=_("settings.manifest_desc")
        )
        manifest_switch = Gtk.Switch(
            active=self.config["GENERATE_MANIFEST"].lower() == "true",
            valign=Gtk.Align.CENTER
        )
        manifest_switch.connect("state-set", mark_dirty)
        manifest_row.add_suffix(manifest_switch)
        gen_group.add(manifest_row)

        # Retention limits
        limit_group = Adw.PreferencesGroup(title=_("settings.retention_limits"), description=_("settings.unlimited"))
        box.append(limit_group)

        max_sys_row = Adw.SpinRow.new_with_range(0, 100, 1)
        max_sys_row.set_title(_("settings.max_system"))
        max_sys_row.set_value(int(self.config["MAX_SYSTEM_SNAPSHOTS"]))
        max_sys_row.connect("changed", mark_dirty)
        limit_group.add(max_sys_row)

        max_full_row = Adw.SpinRow.new_with_range(0, 100, 1)
        max_full_row.set_title(_("settings.max_full"))
        max_full_row.set_value(int(self.config["MAX_FULL_SNAPSHOTS"]))
        max_full_row.connect("changed", mark_dirty)
        limit_group.add(max_full_row)

        # Retention policy
        policy_group = Adw.PreferencesGroup(title=_("settings.retention_policy"), description=_("settings.disabled"))
        box.append(policy_group)

        keep_daily_row = Adw.SpinRow.new_with_range(0, 365, 1)
        keep_daily_row.set_title(_("settings.keep_daily"))
        keep_daily_row.set_value(int(self.config["KEEP_DAILY"]))
        keep_daily_row.connect("changed", mark_dirty)
        policy_group.add(keep_daily_row)

        keep_weekly_row = Adw.SpinRow.new_with_range(0, 52, 1)
        keep_weekly_row.set_title(_("settings.keep_weekly"))
        keep_weekly_row.set_value(int(self.config["KEEP_WEEKLY"]))
        keep_weekly_row.connect("changed", mark_dirty)
        policy_group.add(keep_weekly_row)

        keep_monthly_row = Adw.SpinRow.new_with_range(0, 24, 1)
        keep_monthly_row.set_title(_("settings.keep_monthly"))
        keep_monthly_row.set_value(int(self.config["KEEP_MONTHLY"]))
        keep_monthly_row.connect("changed", mark_dirty)
        policy_group.add(keep_monthly_row)

        # Timer
        timer_group = Adw.PreferencesGroup(title=_("settings.scheduled"))
        box.append(timer_group)

        daily_active = self._is_timer_active("snapshot-daily.timer")
        daily_row = Adw.ActionRow(title=_("settings.daily_timer"),
                                  subtitle=_("settings.daily_desc"))
        daily_switch = Gtk.Switch(active=daily_active, valign=Gtk.Align.CENTER)
        daily_switch.connect("state-set", self._on_timer_toggle, "snapshot-daily.timer")
        daily_row.add_suffix(daily_switch)
        timer_group.add(daily_row)

        weekly_active = self._is_timer_active("snapshot-weekly.timer")
        weekly_row = Adw.ActionRow(title=_("settings.weekly_timer"),
                                   subtitle=_("settings.weekly_desc"))
        weekly_switch = Gtk.Switch(active=weekly_active, valign=Gtk.Align.CENTER)
        weekly_switch.connect("state-set", self._on_timer_toggle, "snapshot-weekly.timer")
        weekly_row.add_suffix(weekly_switch)
        timer_group.add(weekly_row)

        def on_save(btn):
            # Double-click protection + show spinner
            btn.set_sensitive(False)
            spinner = Gtk.Spinner(spinning=True)
            btn.set_child(spinner)

            # Find selected disk
            new_dir = current_dir
            for i, chk in enumerate(drive_checks):
                if chk.get_active():
                    new_dir = drive_paths[i]
                    break

            new_lang = "en" if lang_row.get_selected() == 0 else "tr"

            # Preserve borg settings from current config
            archive_mode = self.config.get("ARCHIVE_MODE", "none")
            borg_repo = self.config.get("BORG_REPO", "")
            borg_compression = self.config.get("BORG_COMPRESSION", "zstd,3")
            borg_keep_daily = self.config.get("BORG_KEEP_DAILY", "7")
            borg_keep_weekly = self.config.get("BORG_KEEP_WEEKLY", "4")
            borg_keep_monthly = self.config.get("BORG_KEEP_MONTHLY", "6")
            max_recent_rsync = self.config.get("MAX_RECENT_RSYNC", "3")

            new_config = (
                '# Snapshot Manager Configuration\n'
                '# ================================\n\n'
                f'SNAPSHOT_DIR="{new_dir}"\n'
                f'LANGUAGE={new_lang}\n\n'
                f'MAX_SYSTEM_SNAPSHOTS={int(max_sys_row.get_value())}\n'
                f'MAX_FULL_SNAPSHOTS={int(max_full_row.get_value())}\n\n'
                f'KEEP_DAILY={int(keep_daily_row.get_value())}\n'
                f'KEEP_WEEKLY={int(keep_weekly_row.get_value())}\n'
                f'KEEP_MONTHLY={int(keep_monthly_row.get_value())}\n\n'
                f'LOW_PRIORITY={"true" if low_prio_switch.get_active() else "false"}\n'
                f'GENERATE_MANIFEST={"true" if manifest_switch.get_active() else "false"}\n\n'
                '# Archive Settings\n'
                f'ARCHIVE_MODE={archive_mode}\n'
                f'BORG_REPO="{borg_repo}"\n'
                f'BORG_COMPRESSION="{borg_compression}"\n'
                f'BORG_KEEP_DAILY={borg_keep_daily}\n'
                f'BORG_KEEP_WEEKLY={borg_keep_weekly}\n'
                f'BORG_KEEP_MONTHLY={borg_keep_monthly}\n'
                f'MAX_RECENT_RSYNC={max_recent_rsync}\n'
            )

            old_lang = self.config.get("LANGUAGE", "en")

            def restore_btn():
                btn.set_child(None)
                btn.set_label(_("settings.save"))
                btn.set_sensitive(False)  # Disable again after saving

            old_dir = self.config["SNAPSHOT_DIR"]
            dir_changed = (new_dir != old_dir)

            if dir_changed:
                # Are there existing snapshots?
                old_snapshots = get_snapshots(old_dir)
                if old_snapshots:
                    # Request migration confirmation
                    btn.set_child(None)
                    btn.set_label(_("settings.save"))
                    self._confirm_migrate(old_dir, new_dir, new_config, dialog)
                    return
                else:
                    self._save_config_and_close(new_config, dialog, restore_btn, lang_changed=(new_lang != old_lang))
            else:
                self._save_config_and_close(new_config, dialog, restore_btn, lang_changed=(new_lang != old_lang))

        save_header_btn.connect("clicked", on_save)

        dialog.present(self)

    def _save_config_and_close(self, new_config, dialog, on_done=None, lang_changed=False):
        """Saves config and closes dialog."""
        def _do():
            try:
                result = subprocess.run(
                    ["tee", "/etc/snapshot-manager.conf"],
                    input=new_config, capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    GLib.idle_add(_on_ok)
                else:
                    GLib.idle_add(_on_err, _("settings.save_failed"))
            except Exception as e:
                GLib.idle_add(_on_err, str(e))

        def _on_ok():
            self.config = read_config()
            dialog.close()
            self._refresh_list()
            msg = _("settings.saved")
            if lang_changed:
                msg += "\n" + _("settings.lang_restart")
            self._show_message(_("msg.success"), msg)

        def _on_err(msg):
            if on_done:
                on_done()
            self._show_message(_("msg.error"), msg, error=True)

        threading.Thread(target=_do, daemon=True).start()

    def _confirm_migrate(self, old_dir, new_dir, new_config, settings_dialog):
        """Snapshot migration confirmation dialog - with space check."""
        old_snapshots = get_snapshots(old_dir)
        snap_count = len(old_snapshots)

        # Calculate total size of existing snapshots
        self.spinner_label.set_label(_("migrate.calculating"))
        settings_dialog.close()
        self.content_stack.set_visible_child_name("loading")

        def check_space():
            snap_bytes = get_snapshot_dir_size_bytes(old_dir)
            snap_human = _human_size(snap_bytes)

            # How much space is available on the target disk?
            target_dir = os.path.dirname(new_dir) if not os.path.isdir(new_dir) else new_dir
            # Get statvfs of target_dir's parent if it exists
            check_path = new_dir
            while not os.path.isdir(check_path):
                check_path = os.path.dirname(check_path)
                if check_path == "/":
                    break
            try:
                st = os.statvfs(check_path)
                avail_bytes = st.f_frsize * st.f_bavail
            except Exception:
                avail_bytes = 0
            avail_human = _human_size(avail_bytes)

            enough_space = avail_bytes > snap_bytes

            GLib.idle_add(
                self._show_migrate_dialog,
                old_dir, new_dir, new_config,
                snap_count, snap_human, snap_bytes,
                avail_human, avail_bytes, enough_space
            )

        threading.Thread(target=check_space, daemon=True).start()

    def _show_migrate_dialog(self, old_dir, new_dir, new_config,
                              snap_count, snap_human, snap_bytes,
                              avail_human, avail_bytes, enough_space):
        """Shows the migration confirmation dialog."""
        self.content_stack.set_visible_child_name("list")

        if enough_space:
            body = (
                _("migrate.body", count=snap_count, size=snap_human, avail=avail_human) +
                f"\n\nSource: {old_dir}\nTarget: {new_dir}"
            )
        else:
            body = (
                f"{snap_count} snapshot(s) ({snap_human}).\n"
                f"{_('migrate.not_enough_space')}\n"
                f"Target: {avail_human} free.\n\n"
                f"Source: {old_dir}\nTarget: {new_dir}"
            )

        alert = Adw.AlertDialog(heading=_("migrate.title"), body=body)
        alert.add_response("cancel", _("migrate.cancel"))

        if enough_space:
            alert.add_response("migrate", _("migrate.move"))
            alert.set_response_appearance("migrate", Adw.ResponseAppearance.SUGGESTED)
        alert.add_response("change_only", _("migrate.change_only"))
        alert.set_default_response("cancel")
        alert.set_close_response("cancel")

        alert.connect("response", self._on_migrate_response,
                       old_dir, new_dir, new_config)
        alert.present(self)

    def _on_migrate_response(self, alert, response, old_dir, new_dir, new_config):
        if response == "cancel":
            return
        elif response == "change_only":
            # Only change config, no migration
            self._do_save_config(new_config)
        elif response == "migrate":
            # Start migration
            self._do_migrate(old_dir, new_dir, new_config)

    def _do_save_config(self, new_config):
        """Save config and refresh."""
        try:
            result = subprocess.run(
                ["tee", "/etc/snapshot-manager.conf"],
                input=new_config, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                self.config = read_config()
                self._refresh_list()
                self._show_message(_("msg.success"), _("migrate.dir_changed"))
            else:
                self._show_message(_("msg.error"), _("settings.save_failed"), error=True)
        except Exception as e:
            self._show_message(_("msg.error"), str(e), error=True)

    def _do_migrate(self, old_dir, new_dir, new_config):
        """Migrates snapshots from old disk to new disk (with progress)."""
        self._create_cancel = False
        self._progress_max_pct = 0
        self._progress_max_done = 0
        self._progress_last_total = 0
        self.progress_bar.set_fraction(0)
        self.progress_pct_label.set_label("%0")
        self.progress_files_label.set_label(_("migrate.progress_label"))
        self.progress_stage.set_label(_("migrate.progress_label"))
        self.progress_log.set_label(f"{old_dir} → {new_dir}")
        self.progress_cancel_btn.set_sensitive(False)  # Migration cannot be cancelled
        self.progress_title.set_label(_("migrate.progress_title"))
        self.content_stack.set_visible_child_name("progress")

        def run():
            try:
                # 1. Save config first
                result = subprocess.run(
                    ["tee", "/etc/snapshot-manager.conf"],
                    input=new_config, capture_output=True, text=True, timeout=30
                )
                if result.returncode != 0:
                    GLib.idle_add(self._migrate_done, False, _("settings.save_failed"))
                    return

                # 2. Create target directory and migrate with rsync
                import shlex
                q_old = shlex.quote(old_dir)
                q_new = shlex.quote(new_dir)
                cmd = [
                    "bash", "-c",
                    f'mkdir -p {q_new} && '
                    f'rsync -aAXH --info=progress2 --remove-source-files '
                    f'{q_old}/ {q_new}/ && '
                    f'find {q_old} -mindepth 1 -type d -empty -delete 2>/dev/null; '
                    f'chattr -i {q_old}/restore.sh 2>/dev/null; '
                    f'rm -f {q_old}/restore.sh 2>/dev/null; '
                    f'cp /usr/local/bin/snapshot-restore {q_new}/restore.sh && '
                    f'chmod +x {q_new}/restore.sh && '
                    f'chattr +i {q_new}/restore.sh 2>/dev/null; '
                    f'echo "MIGRATION_COMPLETE"'
                ]

                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False
                )

                import select
                buffer = b""
                fd = proc.stdout.fileno()
                while True:
                    ready, _, _ = select.select([fd], [], [], 0.1)
                    if not ready:
                        if proc.poll() is not None:
                            break
                        continue

                    data = os.read(fd, 4096)
                    if not data:
                        break

                    buffer += data
                    while b'\r' in buffer or b'\n' in buffer:
                        idx_r = buffer.find(b'\r')
                        idx_n = buffer.find(b'\n')
                        if idx_r == -1:
                            idx = idx_n
                        elif idx_n == -1:
                            idx = idx_r
                        else:
                            idx = min(idx_r, idx_n)
                        line = buffer[:idx].decode('utf-8', errors='replace')
                        buffer = buffer[idx + 1:]
                        if line.strip():
                            progress = parse_rsync_progress(line)
                            if progress:
                                GLib.idle_add(self._update_progress, progress)
                            elif "MIGRATION_COMPLETE" in line:
                                GLib.idle_add(self._update_progress,
                                              {"byte_pct": 100, "done": 0, "total": 0})

                rc = proc.wait()
                stderr_out = proc.stderr.read().decode('utf-8', errors='replace')

                if rc == 0:
                    # Update GRUB
                    subprocess.run(
                        ["bash", "-c",
                         "update-grub 2>/dev/null || grub-mkconfig -o /boot/grub/grub.cfg 2>/dev/null"],
                        capture_output=True, timeout=60
                    )
                    GLib.idle_add(self._migrate_done, True, "")
                else:
                    GLib.idle_add(self._migrate_done, False, stderr_out)

            except Exception as e:
                GLib.idle_add(self._migrate_done, False, str(e))

        threading.Thread(target=run, daemon=True).start()

    def _migrate_done(self, success, error_msg):
        self.config = read_config()
        self._refresh_list()
        if success:
            self._show_message(
                _("migrate.complete_title"),
                _("migrate.complete_body") +
                f"\n{_('disk.location')}: {self.config['SNAPSHOT_DIR']}"
            )
        elif error_msg:
            self._show_message(_("msg.error"), error_msg, error=True)

    def _is_timer_active(self, timer_name):
        try:
            result = subprocess.run(
                ["systemctl", "is-active", timer_name],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() == "active"
        except Exception:
            return False

    def _on_timer_toggle(self, switch, state, timer_name):
        action = "enable" if state else "disable"
        try:
            subprocess.run(
                ["systemctl", f"{action}", "--now", timer_name],
                capture_output=True, text=True, timeout=15
            )
        except Exception:
            pass
        return False

    # ─── System status ───────────────────────────────────────

    def _on_status_clicked(self, _btn):
        disk = get_disk_info(self.config["SNAPSHOT_DIR"])
        snapshots = get_snapshots(self.config["SNAPSHOT_DIR"])

        sys_count = sum(1 for s in snapshots if s.type == "system")
        full_count = sum(1 for s in snapshots if s.type == "full")
        locked_count = sum(1 for s in snapshots if s.locked)

        dialog = Adw.Dialog(title=_("status.title"))
        dialog.set_content_width(450)
        dialog.set_content_height(400)

        toolbar_view = Adw.ToolbarView()
        dialog.set_child(toolbar_view)
        toolbar_view.add_top_bar(Adw.HeaderBar())

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        toolbar_view.set_content(scrolled)

        clamp = Adw.Clamp(maximum_size=450)
        scrolled.set_child(clamp)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                      margin_top=16, margin_bottom=16,
                      margin_start=16, margin_end=16, spacing=12)
        clamp.set_child(box)

        disk_group = Adw.PreferencesGroup(title=_("status.disk"))
        box.append(disk_group)
        disk_group.add(self._info_row(_("status.location"), self.config["SNAPSHOT_DIR"]))
        disk_group.add(self._info_row(_("status.total"), disk["total"]))
        disk_group.add(self._info_row(_("status.used"), f'{disk["used"]} ({disk["pct"]}%)'))
        disk_group.add(self._info_row(_("status.free"), disk["avail"]))
        disk_group.add(self._info_row(_("status.snap_space"), disk["snap_size"]))

        count_group = Adw.PreferencesGroup(title=_("status.counts"))
        box.append(count_group)
        count_group.add(self._info_row(_("status.system"), str(sys_count)))
        count_group.add(self._info_row(_("status.full"), str(full_count)))
        count_group.add(self._info_row(_("status.total_count"), str(len(snapshots))))
        count_group.add(self._info_row(_("status.locked"), str(locked_count)))

        # Archive info
        archived = get_archived_names(self.config)
        if archived:
            arch_size = get_archive_size(self.config)
            count_group.add(self._info_row(_("status.archived"), str(len(archived))))
            if arch_size:
                count_group.add(self._info_row(_("status.archive_size"), arch_size))

        dialog.present(self)

    def _show_message(self, title, message, error=False):
        alert = Adw.AlertDialog(heading=title, body=message)
        alert.add_response("ok", _("msg.ok"))
        alert.set_default_response("ok")
        alert.present(self)


def main():
    app = SnapshotManagerApp()
    app.run()


if __name__ == "__main__":
    main()
