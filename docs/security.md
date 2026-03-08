# Security Considerations

This document covers the security model, input validation, filesystem
protections, and known risks of snapshot-manager.

---

## Access Control

- **Root required** -- every operation checks `EUID == 0` at startup and
  refuses to proceed without root privileges.
- **GUI privilege elevation** -- the graphical interface uses `pkexec` to
  elevate privileges with a single password prompt. No credentials are
  stored or cached by the application itself.
- **Exclusive locking** -- `flock`-based file locking prevents concurrent
  snapshot or restore operations. Only one instance of snapshot-manager can
  perform a destructive operation at a time.

---

## Input Validation

- **Path traversal protection** -- snapshot names are rejected if they
  contain `/` or `..`, preventing directory traversal attacks that could
  read or write outside the snapshot directory.
- **Description sanitization** -- newline (`\n`) and carriage return (`\r`)
  characters are stripped from user-provided snapshot descriptions to
  prevent injection into configuration files.
- **Name format enforcement** -- snapshot names must follow the pattern
  `type_YYYY-MM-DD_HH-MM-SS` (e.g., `full_2026-03-08_14-30-00`). Names
  that do not match this format are rejected.

---

## Filesystem Protection

- **Immutable restore.sh** -- the restore script is protected with
  `chattr +i` (the immutable flag). Even root cannot modify or delete it
  without first removing the flag, guarding against accidental removal.
- **Self-backup prevention** -- the snapshot directory (`SNAPSHOT_DIR`)
  is excluded from snapshots, preventing recursive self-inclusion that
  would waste space and cause confusion during restore.
- **Single filesystem boundary** -- the `--one-file-system` rsync flag
  prevents crossing mount boundaries, ensuring that only the root
  filesystem is captured without pulling in mounted network shares,
  tmpfs, or other partitions.
- **EFI partition excluded** -- `/boot/efi` is explicitly excluded from
  snapshots to avoid overwriting the EFI System Partition, which could
  render the system unbootable.
- **Boot files are copies** -- kernel and initrd files stored in snapshots
  are full copies, not symlinks. This ensures they remain valid even if
  the source files are later updated or removed.

---

## Restore Safety

- **Writable root verification** -- before any restore operation begins,
  the script confirms that the root filesystem has been successfully
  remounted read-write.
- **Delete-after strategy** -- rsync runs with `--delete-after`, which
  writes all new and updated files before deleting any obsolete ones.
  This reduces the window of inconsistency compared to `--delete-during`.
- **External disk cleanup** -- if an external snapshot disk was mounted
  for the restore, it is unmounted before the reboot to prevent filesystem
  corruption.
- **Graceful reboot** -- the reboot sequence uses sysrq-trigger
  (sync, remount-ro, reboot) to ensure buffers are flushed and
  filesystems are cleanly unmounted.
- **Post-restore GRUB update** -- a oneshot systemd service regenerates
  the GRUB configuration on the first normal boot after a restore,
  preventing stale snapshot entries from appearing in the boot menu.

---

## Known Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Not atomic** | Unlike BTRFS/ZFS snapshots, rsync-based restore is not an atomic operation. The filesystem is in a mixed state during the process. | Accept as a design limitation of ext4-based snapshots. |
| **Power loss during restore** | If power is lost while rsync is writing, the filesystem will be in an inconsistent state -- partially old, partially restored. | Use `--delete-after` to minimize the damage window. Consider UPS for critical systems. |
| **PID 1 failure** | If the restore script crashes or exits while running as PID 1, the kernel will panic. | Avoid `set -e`; handle all errors manually; fall back to `exec /sbin/init` on any failure. |
| **Live system changes during snapshot** | Files may change while rsync is reading them, leading to partial copies of individual files. | Tolerate rsync exit codes 23/24 (partial transfer). For database-heavy workloads, stop services before snapshotting. |
