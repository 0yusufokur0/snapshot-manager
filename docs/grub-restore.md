# GRUB Integration and Boot-Time Restore

This document describes how snapshot-manager integrates with GRUB to offer
boot-time snapshot restoration and how the restore process works when
running as PID 1.

---

## GRUB Menu Generation (41_snapshots)

The script at `/etc/grub.d/41_snapshots` is responsible for generating
snapshot restore entries in the GRUB boot menu.

### How It Works

1. Reads `SNAPSHOT_DIR` from the snapshot-manager configuration file.
2. Scans the snapshot directory for valid snapshots. A snapshot is considered
   valid only if it contains all three of these:
   - `info.conf`
   - `boot/vmlinuz`
   - `boot/initrd.img`
3. Generates a GRUB submenu titled **"Snapshot Restore >"** containing a
   sub-entry for each valid snapshot.

### Restore Modes by Snapshot Type

Each snapshot entry offers restore modes based on the snapshot type recorded
in `info.conf`:

| Snapshot Type | Available Restore Modes                              |
|---------------|------------------------------------------------------|
| **full**      | Full restore, System only, User data only, Kernel only |
| **system**    | System restore, Kernel only                          |

---

## External Disk Detection

The script uses `findmnt` to compare the device that holds `SNAPSHOT_DIR`
against the device that holds the root filesystem (`/`).

### External Disk (different device)

When the snapshot directory lives on a different device than root:

- Obtains the external disk UUID via `blkid`.
- Strips the mount point prefix from snapshot paths to produce
  GRUB-relative paths.
- Uses `search --set=root EXTERNAL_UUID` in the generated menu entry so
  GRUB can locate the kernel on the external disk.
- Sets `init=/usr/local/bin/snapshot-restore` (located on the root
  filesystem) as the init process.
- Passes two extra kernel parameters:
  - `snapshot.disk=UUID` -- UUID of the external disk holding the snapshot.
  - `snapshot.dir=PATH` -- path to the snapshot directory relative to the
    external disk mount point.

### Local Disk (same device)

When the snapshot directory lives on the same device as root:

- Uses the root filesystem UUID for the GRUB `search` command.
- Sets `init=<SNAPSHOT_DIR>/restore.sh` directly as the init process.

---

## Boot-Time Restore Process (snapshot-restore as PID 1)

When the system boots with `init=` pointing to the restore script, the
following steps are executed as PID 1:

1. **Mount virtual filesystems** -- `/proc`, `/sys`, `/dev`.
2. **Parse kernel command line** -- extracts four parameters:
   - `snapshot.restore` -- which snapshot to restore.
   - `snapshot.mode` -- restore mode (full, system, userdata, kernel).
   - `snapshot.disk` -- UUID of the external disk (if applicable).
   - `snapshot.dir` -- path to snapshot directory (if applicable).
3. **Mount external disk** -- if `snapshot.disk` is set, mounts the
   external disk by UUID to `/mnt/snapshot-disk`.
4. **Validate snapshot** -- confirms the specified snapshot exists and
   contains the expected files.
5. **Validate restore mode** -- checks that the requested mode is
   compatible with the snapshot type.
6. **Remount root read-write** -- remounts `/` as read-write so files can
   be written.
7. **Run rsync** -- restores files with appropriate exclude lists based on
   the selected mode:

   | Mode       | What Gets Restored                          |
   |------------|---------------------------------------------|
   | `full`     | Everything except virtual/temp directories   |
   | `system`   | Everything except `/home` and virtual/temp   |
   | `userdata` | Only `/home`                                 |
   | `kernel`   | Only `/boot` (excluding `/boot/efi`)         |

8. **Unmount external disk** -- if it was mounted in step 3.
9. **Create oneshot systemd service** -- writes a transient systemd unit
   that will run a GRUB update on the next normal boot, ensuring menu
   entries stay consistent with the restored system.
10. **Graceful reboot** -- triggers reboot via sysrq-trigger with the
    sequence: sync, remount-ro, reboot.

---

## Why No `set -e` in PID 1

The restore script deliberately avoids `set -e` (exit on error) because:

- **PID 1 exit causes a kernel panic.** If the init process terminates for
  any reason, the kernel has no recovery path and panics immediately.
- The script must **never exit unexpectedly**, regardless of what errors
  occur during the restore process.
- All errors are handled manually with explicit checks. On any failure, the
  script falls back to `exec /sbin/init` to boot the system normally.

---

## Safety Measures

- **5-second countdown** -- before the restore begins, a countdown is
  displayed on screen. The user can power off the machine to cancel.
- **Tolerant rsync exit codes** -- exit codes 23 and 24 (partial transfer
  due to vanished files or minor errors) are tolerated and do not abort
  the restore.
- **Graceful fallback** -- on any error, the script attempts to boot
  normally via `exec /sbin/init` rather than halting or panicking.
- **Immutable restore.sh** -- the restore script is protected with
  `chattr +i` (immutable flag) to prevent accidental deletion or
  modification.
- **Post-restore GRUB update** -- a oneshot systemd service ensures that
  GRUB menu entries are regenerated after restore, preventing stale or
  invalid entries from persisting.
