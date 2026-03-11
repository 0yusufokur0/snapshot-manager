# Snapshot Manager - Architecture Documentation

This document provides a comprehensive overview of the snapshot-manager project: an rsync-based system snapshot tool for Linux with GRUB2 boot-time restore capability.

## Project Overview

Snapshot Manager creates filesystem snapshots using `rsync` with hardlink deduplication and integrates them into the GRUB2 boot menu so that a user can restore their system to a previous state at boot time, before any services start.

**Key characteristics:**

- **rsync + hardlinks**: Snapshots are filesystem-level copies created with `rsync -aAXH`. Subsequent snapshots use `--link-dest` to hardlink unchanged files, making them extremely space-efficient.
- **Filesystem support**: Designed for ext4, ext3, and xfs root filesystems. The installer validates the root filesystem type.
- **GRUB2 integration**: A GRUB script (`41_snapshots`) generates boot menu entries for every snapshot. Selecting one boots the system's own kernel/initramfs from the snapshot and passes `init=` to redirect PID 1 to the restore script.
- **Restore as PID 1**: The restore script (`snapshot-restore`) runs as the init process (PID 1) during early boot, rsync-restores the filesystem, then reboots. No running services, no open files, no conflicts.
- **CLI + GTK4 GUI**: Full-featured CLI for scripting/automation and a GTK4 + libadwaita GUI for desktop users.
- **Local and external disk support**: Snapshots can live on the root partition or on a separate/external disk. GRUB entries adapt automatically.

---

## Component Overview

### 1. `snapshot-manager` (CLI)

**Location:** `/usr/local/bin/snapshot-manager`
**Language:** Bash
**Runs as:** root (enforced with `check_root`)

The main management tool. Handles all snapshot lifecycle operations:

| Command | Description |
|---------|-------------|
| `create [system\|full] [description]` | Create a new snapshot (default: full) |
| `list` | List all snapshots (local and archived) |
| `delete <name>` | Delete a snapshot (from local and/or archive) |
| `restore <name>` | Restore an archived snapshot for GRUB boot restore |
| `check` | Run integrity check on all snapshots and archives |
| `archive <name>` | Manually archive a local snapshot |
| `lock <name>` | Lock a snapshot (prevents auto-cleanup and deletion) |
| `unlock <name>` | Unlock a snapshot |
| `diff <snap1> <snap2>` | Show file-level differences between two snapshots |
| `restore-file <snap> <path> [dest]` | Restore a single file from a snapshot |
| `verify <name>` | Validate snapshot integrity (structure + optional SHA256 manifest) |
| `status` | Show disk usage, snapshot counts, config, timer status |

**Snapshot types:**
- `full` - Everything including `/home`. Full system + user data backup (default).
- `system` - System files only. Excludes `/home/*`. Useful for OS-level rollback.

**Concurrency control:** Uses `flock` on `/var/run/snapshot-manager.lock` to prevent concurrent snapshot operations.

**Path traversal protection:** All user-supplied snapshot names are validated to reject `/` and `..` characters.

### 2. `snapshot-restore` (PID 1 Init Replacement)

**Location:** `/usr/local/bin/snapshot-restore` and `<SNAPSHOT_DIR>/restore.sh`
**Language:** Bash
**Runs as:** PID 1 (kernel init process)

This is the boot-time restore engine. When a user selects a snapshot from the GRUB menu, the kernel boots with `init=<path-to-restore-script>`, making this script the very first process (PID 1).

**Kernel command-line parameters parsed:**

| Parameter | Description |
|-----------|-------------|
| `snapshot.restore=<name>` | Snapshot directory name to restore |
| `snapshot.mode=<mode>` | Restore mode: `full`, `system`, `userdata`, `kernel` |
| `snapshot.disk=<UUID>` | UUID of external disk containing snapshots |
| `snapshot.dir=<path>` | Snapshot directory path on external disk |
| `snapshot.mountpoint=<path>` | Mount point for external disk |

**Restore modes:**

| Mode | What it restores | Excludes |
|------|-----------------|----------|
| `full` | Everything in the snapshot | Virtual filesystems, snapshot dir |
| `system` | System files only | `/home`, virtual filesystems |
| `userdata` | Only `/home` | Everything else |
| `kernel` | Only `/boot` | Everything else (excludes `/boot/efi`) |

**Restore flow:**
1. Mount `/proc`, `/sys`, `/dev`
2. Parse `/proc/cmdline` for snapshot parameters
3. If no `snapshot.restore` parameter found, fall through to `/sbin/init` (normal boot)
4. If external disk: resolve UUID via `blkid`, mount the disk
5. Validate snapshot exists and mode is compatible with snapshot type
6. Display info, wait 5 seconds (user can power off to cancel)
7. Remount root as read-write
8. Run `rsync -aAXH --delete-after` from snapshot to live filesystem
9. Create a oneshot systemd service (`snapshot-post-restore.service`) to update GRUB on next normal boot
10. Graceful reboot via sysrq triggers: sync (s) -> remount-ro (u) -> reboot (b)

### 3. `41_snapshots` (GRUB Script)

**Location:** `/etc/grub.d/41_snapshots`
**Language:** Bash (GRUB script generator)
**Runs during:** `update-grub` / `grub-mkconfig`

Generates GRUB menu entries for all valid snapshots. Called automatically whenever `update-grub` runs.

**Generated menu structure** (English, default):
```
Snapshot Restore >
  [System] 2026.03.08 14:30:00 - Description >
    System Restore
    Kernel Only (/boot)
  [Full] 2026.03.07 10:00:00 - Description >
    Full Restore (system + user data)
    System Only (excludes user data)
    User Data Only (/home)
    Kernel Only (/boot)
```

Menu labels are localized based on the `LANGUAGE` setting in `/etc/snapshot-manager.conf`. Supported languages: English (`en`, default) and Turkish (`tr`).

**External disk handling:**
When snapshots reside on a disk different from root:
- GRUB uses `search --no-floppy --fs-uuid --set=root <SNAP_UUID>` to find the snapshot disk
- Kernel/initrd paths are relative to the snapshot disk's root
- `init=` points to `/usr/local/bin/snapshot-restore` (on root disk) instead of `<SNAPSHOT_DIR>/restore.sh` (on external disk, not accessible before mount)
- Extra kernel params (`snapshot.disk`, `snapshot.dir`, `snapshot.mountpoint`) tell the restore script where to find snapshots

**Validation:** Only snapshots with all three required files (`info.conf`, `boot/vmlinuz`, `boot/initrd.img`) get GRUB entries.

### 4. `snapshot-manager-gui` (GUI)

**Location:** `/usr/local/bin/snapshot-manager-gui`
**Language:** Python 3 (GTK4 + libadwaita)
**Runs as:** Launched as normal user, auto-escalates to root via `pkexec`

Full graphical interface providing:
- Snapshot list with type, date, size, storage status, lock status, and description
- Create/delete/lock/unlock operations
- Archived snapshot restore and integrity checking
- Snapshot diff viewer
- Single-file restore
- Snapshot verification
- System status dashboard (disk usage, snapshot counts, archive info, timer status)
- Disk space warning when usage exceeds 85%
- Dark/light theme support (inherits user's GNOME color-scheme preference)
- **Multi-language support** (English and Turkish) with language selector in Settings
- Progress feedback for long-running operations (runs CLI commands in background threads)

**Architecture note:** The GUI is a thin wrapper around the CLI. It invokes `/usr/local/bin/snapshot-manager` subprocess commands and parses their output. This ensures the GUI and CLI always behave identically.

**Internationalization (i18n):** The GUI uses a dict-based translation system with a `TRANSLATIONS` dictionary containing ~130 keys per language. The `_()` function looks up the current language at runtime. Language is stored in `/etc/snapshot-manager.conf` as `LANGUAGE=en|tr` and shared with the GRUB script for consistent localization across the entire system.

### 5. `install.sh` (Installer)

**Location:** Project root
**Language:** Bash

Performs full installation:
1. Validates prerequisites (filesystem type, rsync, GRUB2, disk space)
2. Copies all files to system locations
3. Creates snapshot directory
4. Installs `restore.sh` to `<SNAPSHOT_DIR>/restore.sh` with immutable flag
5. Configures GRUB: sets `GRUB_TIMEOUT=5` and `GRUB_TIMEOUT_STYLE=menu` (menu must be visible for snapshot selection)
6. Runs `update-grub`
7. Optionally creates first snapshot

### 6. APT Hook

**Location:** `/etc/apt/apt.conf.d/80snapshot-manager`

A `DPkg::Pre-Invoke` hook that automatically creates a system snapshot before any `apt install`, `apt upgrade`, or `apt remove` operation. This provides automatic rollback points for every package change.

```
DPkg::Pre-Invoke { "if [ -x /usr/local/bin/snapshot-manager ]; then
    ionice -c3 nice -n 19 /usr/local/bin/snapshot-manager create system
    'apt: automatic pre-upgrade backup'
    >> /var/log/snapshot-manager.log 2>&1 || true; fi"; };
```

Key details:
- Runs at low I/O and CPU priority (`ionice -c3 nice -n 19`)
- Failure does not block the package operation (`|| true`)
- Output logged to `/var/log/snapshot-manager.log`

### 7. Kernel Postinst Hook

**Location:** `/etc/kernel/postinst.d/zz-snapshot-grub-update`

When a new kernel is installed, this hook ensures the restore script in `<SNAPSHOT_DIR>/restore.sh` is updated to match the version in `/usr/local/bin/snapshot-restore`. It handles the immutable flag: removes it, copies the file, re-applies it.

This is important because GRUB loads `restore.sh` directly from the snapshot directory for local-disk snapshots. If the restore script has a bug fix, it must be propagated to the GRUB-accessible copy.

### 8. Systemd Timers

**Location:** `/etc/systemd/system/snapshot-daily.*` and `snapshot-weekly.*`

| Timer | Schedule | Snapshot Type |
|-------|----------|---------------|
| `snapshot-daily.timer` | Every day at 02:00 (with up to 15 min random delay) | `system` |
| `snapshot-weekly.timer` | Every Monday at 03:00 (with up to 30 min random delay) | `full` |

Both services run with `Nice=19` and `IOSchedulingClass=idle`. Timers are `Persistent=true`, meaning missed runs (e.g., system was off) execute on next boot.

Timers are installed but **not enabled by default**. The user must explicitly enable them:
```bash
sudo systemctl enable --now snapshot-daily.timer
sudo systemctl enable --now snapshot-weekly.timer
```

### 9. Logrotate Config

**Location:** `/etc/logrotate.d/snapshot-manager`

Rotates `/var/log/snapshot-manager.log` monthly, keeping 3 compressed archives. Tolerates missing log file (`missingok`).

---

## Data Flow

### Creating a Snapshot

```
User runs: sudo snapshot-manager create system "Pre-upgrade backup"
                          |
                          v
                  [1] Acquire flock
                          |
                          v
                  [2] Find latest snapshot of same type
                      for --link-dest (hardlink dedup)
                          |
                          v
                  [3] Check available disk space
                      (first snapshot needs ~used space,
                       subsequent ones much less)
                          |
                          v
                  [4] rsync -aAXH --one-file-system --delete
                      --link-dest=<previous>/fs/
                      --exclude={virtual filesystems}
                      / -> <SNAPSHOT_DIR>/<name>/fs/
                          |
                          v
                  [5] Copy kernel + initramfs
                      /boot/vmlinuz-$(uname -r) -> <name>/boot/vmlinuz
                      /boot/initrd.img-$(uname -r) -> <name>/boot/initrd.img
                          |
                          v
                  [6] (Optional) Generate SHA256 manifest
                          |
                          v
                  [7] Write info.conf metadata
                          |
                          v
                  [8] Cleanup old snapshots per retention policy
                          |
                          v
                  [9] update-grub (regenerates GRUB menu
                      including new snapshot entry)
                          |
                          v
                  [10] Release flock
```

**rsync flags explained:**
- `-a` : Archive mode (preserves permissions, ownership, timestamps, symlinks)
- `-A` : Preserve ACLs
- `-X` : Preserve extended attributes
- `-H` : Preserve hardlinks within the source
- `--one-file-system` : Do not cross mount boundaries (prevents backing up /proc, /sys, etc. even without explicit excludes)
- `--delete` : Remove files from snapshot that no longer exist on source
- `--link-dest` : Hardlink files that are identical to the reference snapshot (massive space savings)
- `--info=progress2` : Show overall transfer progress

### Boot-Time Restore

```
 GRUB Menu
   |
   v
 User selects: "Snapshot Restore > [System] 2026.03.08 > System Restore"
   |
   v
 GRUB loads kernel + initramfs FROM the snapshot:
   linux <SNAPSHOT_DIR>/<name>/boot/vmlinuz root=UUID=<ROOT_UUID> rw \
         snapshot.restore=<name> snapshot.mode=system \
         init=<SNAPSHOT_DIR>/restore.sh
   initrd <SNAPSHOT_DIR>/<name>/boot/initrd.img
   |
   v
 Kernel boots, runs restore.sh as PID 1 (instead of /sbin/init)
   |
   v
 [1] Mount /proc, /sys, /dev
 [2] Parse /proc/cmdline -> extract snapshot.restore, snapshot.mode, etc.
 [3] If snapshot.restore is empty -> exec /sbin/init (normal boot)
 [4] Validate snapshot exists
 [5] Validate mode vs. snapshot type (e.g., can't do "userdata" on "system" snapshot)
 [6] Display info + 5-second countdown (power off to cancel)
 [7] mount -o remount,rw /
 [8] rsync -aAXH --delete-after from snapshot/fs/ to /
 [9] sync; sync
 [10] Install oneshot systemd service to update-grub on next boot
 [11] Graceful reboot: sysrq s -> u -> b
   |
   v
 System reboots into restored state
   |
   v
 On next normal boot: snapshot-post-restore.service runs update-grub,
 then self-destructs
```

### External Disk Flow

When `SNAPSHOT_DIR` is on a different disk than root (e.g., an external USB drive):

```
 [GRUB Phase]
   GRUB detects SNAP_UUID != ROOT_UUID during update-grub
     |
     v
   GRUB entry uses:
     search --no-floppy --fs-uuid --set=root <SNAP_UUID>   # find external disk
     linux <relative-path>/boot/vmlinuz root=UUID=<ROOT_UUID> rw \
           snapshot.restore=<name> snapshot.mode=full \
           snapshot.disk=<SNAP_UUID> snapshot.dir=<SNAPSHOT_DIR> \
           snapshot.mountpoint=<MOUNT_POINT> \
           init=/usr/local/bin/snapshot-restore   # NOTE: uses /usr/local/bin copy
     initrd <relative-path>/boot/initrd.img

 [Restore Phase]
   restore.sh (from /usr/local/bin on root disk) starts as PID 1
     |
     v
   Parses snapshot.disk=<UUID> from /proc/cmdline
     |
     v
   blkid -U <UUID> -> finds /dev/sdX
     |
     v
   mount /dev/sdX <mountpoint>
     |
     v
   rsync from <mountpoint>/<snapshot_dir>/<name>/fs/ to /
     |
     v
   umount <mountpoint>
     |
     v
   Reboot
```

**Why two copies of restore.sh?**
- `<SNAPSHOT_DIR>/restore.sh` - Used by GRUB for local-disk scenarios. GRUB can access it because it is on the same partition as root. The `init=` parameter points here.
- `/usr/local/bin/snapshot-restore` - Used for external-disk scenarios. When snapshots are on an external disk, GRUB cannot use `init=` pointing to the external disk (the kernel hasn't mounted it yet). Instead, `init=` points to the copy on the root disk, which then mounts the external disk to access the snapshot data.

---

## File Layout

### Installed Files

```
/usr/local/bin/snapshot-manager           # Main CLI tool (bash)
/usr/local/bin/snapshot-restore           # Boot-time restore script (bash)
/usr/local/bin/snapshot-manager-gui       # GTK4 GUI (python3)
/usr/share/applications/snapshot-manager.desktop  # Desktop entry for GUI

/etc/snapshot-manager.conf                # Configuration file
/etc/grub.d/41_snapshots                  # GRUB menu generator script
/etc/apt/apt.conf.d/80snapshot-manager    # APT pre-upgrade hook
/etc/kernel/postinst.d/zz-snapshot-grub-update    # Kernel postinst hook
/etc/logrotate.d/snapshot-manager         # Log rotation config

/etc/systemd/system/snapshot-daily.service    # Daily snapshot service
/etc/systemd/system/snapshot-daily.timer     # Daily snapshot timer
/etc/systemd/system/snapshot-weekly.service   # Weekly snapshot service
/etc/systemd/system/snapshot-weekly.timer    # Weekly snapshot timer

/var/run/snapshot-manager.lock            # Runtime lock file (flock)
/var/log/snapshot-manager.log             # Log file (APT hook output)
```

### Snapshot Directory Structure

```
<SNAPSHOT_DIR>/                           # Default: /snapshots
  restore.sh                              # Immutable copy of snapshot-restore (chattr +i)
  system_2026-03-08_14-30-00/             # Snapshot directory
    fs/                                   # Complete filesystem copy (rsync)
      etc/
      usr/
      var/
      bin -> usr/bin                      # Symlinks preserved
      ...
    boot/
      vmlinuz                             # Kernel binary at time of snapshot
      initrd.img                          # initramfs at time of snapshot
    info.conf                             # Metadata file
    manifest.sha256                       # Optional SHA256 integrity manifest
  full_2026-03-07_10-00-00/
    fs/
      etc/
      usr/
      home/                              # Full snapshots include /home
      ...
    boot/
      vmlinuz
      initrd.img
    info.conf
```

### Metadata File Format (`info.conf`)

```ini
NAME=system_2026-03-08_14-30-00
TYPE=system
DATE=2026-03-08_14-30-00
KERNEL=6.17.0-14-generic
DESCRIPTION=System backup - 08 March 2026 14:30
LOCKED=false
```

### Configuration File (`/etc/snapshot-manager.conf`)

```bash
SNAPSHOT_DIR="/snapshots"         # Where snapshots are stored
LANGUAGE=en                       # Display language: en or tr
MAX_SYSTEM_SNAPSHOTS=0            # Max system snapshots (0 = unlimited)
MAX_FULL_SNAPSHOTS=0              # Max full snapshots (0 = unlimited)
KEEP_DAILY=0                      # Keep latest per day for N days (0 = disabled)
KEEP_WEEKLY=0                     # Keep latest per week for N weeks (0 = disabled)
KEEP_MONTHLY=0                    # Keep latest per month for N months (0 = disabled)
LOW_PRIORITY=true                 # Run rsync with ionice -c3 + nice -n 19
GENERATE_MANIFEST=false           # Generate SHA256 manifest after snapshot

# Borg archival settings
ARCHIVE_MODE=borg                 # none = rsync only, borg = rsync + borg archival
BORG_REPO=""                      # Borg repo path (empty = SNAPSHOT_DIR/.borg-repo)
BORG_COMPRESSION="zstd,3"        # Compression: none, lz4, zstd,N, zlib,N
BORG_KEEP_DAILY=7                 # Borg retention: daily archives
BORG_KEEP_WEEKLY=4                # Borg retention: weekly archives
BORG_KEEP_MONTHLY=6              # Borg retention: monthly archives
MAX_RECENT_RSYNC=3                # Recent rsync snapshots for GRUB (borg mode only)
```

**Retention logic:** If any `KEEP_*` values are non-zero, the policy-based cleanup is used instead of `MAX_*_SNAPSHOTS`. Locked snapshots are always preserved regardless of retention policy.

**Borg archival:** When `ARCHIVE_MODE=borg`, snapshots are archived into a Borg repository after creation. Only `MAX_RECENT_RSYNC` rsync snapshots are kept on disk for GRUB; older ones are pruned after archival. Borg provides chunk-level deduplication and compression for space-efficient long-term storage.

---

## Design Decisions

### Why no `set -e` in the PID 1 restore script

The restore script (`snapshot-restore`) deliberately does **not** use `set -e` (exit on error). When running as PID 1, if the script exits for any reason, the kernel panics because init died. Instead, every critical operation checks its return code explicitly and falls back to `exec /sbin/init "$@"` on failure, allowing the system to boot normally even if the restore fails.

```bash
# Example: if root can't be remounted rw, fall back to normal boot
if ! mount -o remount,rw /; then
    echo "ERROR: Could not remount root filesystem as read-write!"
    sleep 10
    umount /proc /sys /dev 2>/dev/null
    exec /sbin/init "$@"    # <-- graceful fallback, not exit
fi
```

### Why `/proc/cmdline` parsing with a `for` loop is safe

The script parses kernel command-line parameters with:
```bash
for param in $(cat /proc/cmdline); do
    case "$param" in
        snapshot.restore=*) SNAPSHOT_NAME="${param#snapshot.restore=}" ;;
    esac
done
```

This is safe because:
- Kernel parameters are space-delimited tokens with no shell metacharacters
- This is standard Ubuntu/Debian practice (used in initramfs scripts)
- `case` pattern matching does not invoke subshells or external commands
- No word splitting issues because each `$param` is a single token

### Why the immutable flag on `restore.sh`

The file `<SNAPSHOT_DIR>/restore.sh` has the ext4 immutable attribute (`chattr +i`) set. This prevents:
- Accidental deletion by the user (e.g., `rm -rf /snapshots/*`)
- Accidental deletion by cleanup scripts
- Modification by malware or misconfigured scripts

If this file is missing and a user selects a snapshot restore from GRUB, the kernel would fail to find the init process, resulting in a kernel panic. The immutable flag is a safeguard against this critical failure mode.

The installer and kernel postinst hook both handle the immutable flag correctly:
```bash
chattr -i "${SNAPSHOT_DIR}/restore.sh" 2>/dev/null    # Remove for update
cp /usr/local/bin/snapshot-restore "${SNAPSHOT_DIR}/restore.sh"
chmod +x "${SNAPSHOT_DIR}/restore.sh"
chattr +i "${SNAPSHOT_DIR}/restore.sh" 2>/dev/null    # Re-apply
```

### Why two copies of the restore script

| Copy | Path | Purpose |
|------|------|---------|
| 1 | `<SNAPSHOT_DIR>/restore.sh` | Used by GRUB's `init=` for **local disk** scenarios. GRUB can reference this path directly because it is on the root partition. |
| 2 | `/usr/local/bin/snapshot-restore` | Used by GRUB's `init=` for **external disk** scenarios. When snapshots are on an external disk, the kernel cannot access `<SNAPSHOT_DIR>/restore.sh` at init time (the external disk isn't mounted yet). So `init=` points to this copy on the root filesystem, and the script itself handles mounting the external disk. |

### Hardlink deduplication via `rsync --link-dest`

Each new snapshot uses `--link-dest=<previous_snapshot>/fs/` to hardlink files that haven't changed since the last snapshot. This means:

- The first snapshot uses disk space roughly equal to the system size
- Subsequent snapshots only consume space for files that actually changed
- Each snapshot is a complete, independent directory tree (not incremental -- any snapshot can be deleted without affecting others)
- Hardlinks are transparent: every snapshot looks like a full copy

Example space usage:
```
system_2026-03-01  12GB   (first snapshot, full copy)
system_2026-03-02  340MB  (only changed files consume new blocks)
system_2026-03-03  280MB  (even less changed)
```

### rsync exit codes 23 and 24 are tolerated

On a live running system, files can change or disappear during the rsync transfer:
- **Exit code 24**: "Vanished source files" -- a file existed when rsync listed it but was gone when rsync tried to copy it. Common with temp files, lock files, PID files.
- **Exit code 23**: "Partial transfer due to error" -- some files couldn't be read (e.g., running database files with exclusive locks).

Both are expected on a live system and do not invalidate the snapshot. Any other non-zero exit code causes the snapshot to be aborted and cleaned up.

```bash
rsync_cmd "${rsync_args[@]}" || rsync_exit=$?
if [[ $rsync_exit -ne 0 && $rsync_exit -ne 24 && $rsync_exit -ne 23 ]]; then
    # Real error: abort and clean up
    rm -rf "${snap_path}"
    exit 1
fi
```

### Default excludes

The following paths are always excluded from snapshots (both creation and restore):

| Path | Reason |
|------|--------|
| `<SNAPSHOT_DIR>` | Prevent recursive snapshots |
| `/proc/*`, `/sys/*`, `/dev/*`, `/run/*` | Virtual filesystems (kernel-generated) |
| `/tmp/*`, `/var/tmp/*` | Temporary files |
| `/var/cache/*` | Package cache (regenerable) |
| `/var/log/*` | Log files (not worth restoring) |
| `/var/lib/docker/*` | Docker storage (separate lifecycle) |
| `/var/lib/machines/*` | systemd-nspawn containers |
| `/mnt/*`, `/media/*` | Mount points for other disks |
| `/snap/*` | Snap packages (managed by snapd) |
| `/boot/efi/*` | EFI System Partition (separate filesystem, critical) |
| `/lost+found` | fsck recovery directory |
| `/swap.img`, `/swapfile` | Swap files |

For `system` type snapshots, `/home/*` is additionally excluded.

### Graceful reboot from PID 1

The restore script cannot call `reboot` or `systemctl reboot` because systemd is not running. Instead, it uses the kernel's SysRq mechanism:

```bash
echo s > /proc/sysrq-trigger    # Sync all filesystems
sleep 1
echo u > /proc/sysrq-trigger    # Remount all filesystems read-only
sleep 1
echo b > /proc/sysrq-trigger    # Immediately reboot
```

This ensures all data is flushed to disk before the reboot.

### Post-restore GRUB update

After a restore, the GRUB configuration may be stale (it was overwritten from the snapshot). The restore script creates a oneshot systemd service that runs on the next normal boot:

```ini
[Service]
Type=oneshot
ExecStart=/usr/sbin/grub-mkconfig -o /boot/grub/grub.cfg
ExecStartPost=/bin/rm -f /etc/systemd/system/snapshot-post-restore.service
ExecStartPost=/bin/systemctl daemon-reload
```

This service updates GRUB and then self-destructs.

---

## Security Considerations

- **Root-only operations**: All mutation operations require root. The CLI checks `EUID` at entry.
- **Path traversal protection**: Snapshot names are validated to reject `/` and `..` characters, preventing directory traversal attacks.
- **Description sanitization**: Metadata descriptions are stripped of newlines/carriage returns to prevent injection into `info.conf`.
- **GUI privilege escalation**: The GUI uses `pkexec` (polkit) for controlled root access, not raw `sudo`.
- **Immutable restore.sh**: The critical boot-time script is protected against accidental deletion.
- **Flock-based locking**: Prevents race conditions from concurrent snapshot operations.
- **EFI partition excluded**: `/boot/efi` is never touched, preventing potential bricking of UEFI boot.

---

## Interaction Diagram

```
                    +-------------------+
                    |      User         |
                    +-------------------+
                     /        |         \
                    v         v          v
            +-------+  +-----------+  +----------+
            |  CLI  |  |    GUI    |  |   GRUB   |
            +-------+  +-----------+  +----------+
                |            |              |
                |     (calls CLI via        |
                |      subprocess)          |
                v                           v
         +-------------+          +----------------+
         |  snapshot-   |          |  41_snapshots  |
         |  manager     |          |  (grub script) |
         +-------------+          +----------------+
                |                        |
                |  (calls update-grub    |  (generates menu
                |   after create/delete) |   entries at
                |         |              |   grub-mkconfig
                |         +------>-------+   time)
                |
                v
         +-------------+
         |    rsync     |  (with --link-dest for dedup)
         +-------------+
                |
                v
         +------------------+
         |  <SNAPSHOT_DIR>  |
         |  /snapshots/     |
         +------------------+
                |
                |  (boot-time selection)
                v
         +-------------------+
         |  snapshot-restore |  (runs as PID 1)
         |  rsync restore   |
         |  -> reboot       |
         +-------------------+

    +-------------------+     +---------------------------+
    |  APT Hook         |---->| snapshot-manager create   |
    |  (pre-upgrade)    |     | (automatic, low priority) |
    +-------------------+     +---------------------------+

    +-------------------+     +---------------------------+
    |  Systemd Timers   |---->| snapshot-manager create   |
    |  (daily/weekly)   |     | (scheduled)               |
    +-------------------+     +---------------------------+

    +---------------------+   +---------------------------+
    |  Kernel Postinst    |-->| Updates restore.sh in     |
    |  Hook               |   | SNAPSHOT_DIR              |
    +---------------------+   +---------------------------+
```
