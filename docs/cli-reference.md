# CLI Reference

snapshot-manager is a command-line tool for creating and managing rsync-based
system snapshots with GRUB boot integration.

## Synopsis

```
sudo snapshot-manager <command> [arguments]
```

All commands require root privileges. The tool uses `flock` to prevent
concurrent execution.

---

## Commands

### create

Create a new snapshot of the running system.

```
sudo snapshot-manager create [system|full] [description]
```

**Types:**

| Type     | Description                                      |
|----------|--------------------------------------------------|
| `system` | Backs up the root filesystem, excluding `/home`. |
| `full`   | Backs up the root filesystem, including `/home`. |

If no type is specified, `full` is the default.

**What it does:**

1. Runs `rsync -aAXH --one-file-system --delete --link-dest=<previous>` to
   create a deduplicated, hard-linked snapshot.
2. Copies the current kernel (`vmlinuz`) and initrd (`initrd.img`) into the
   snapshot's `boot/` directory.
3. Regenerates GRUB menu entries so the snapshot is bootable.
4. Runs the retention policy to clean up old snapshots if configured.

**Examples:**

```bash
# Create a system snapshot (no /home) with a description
sudo snapshot-manager create system "before kernel upgrade"

# Create a full snapshot (includes /home)
sudo snapshot-manager create full "weekly full backup"

# Create a snapshot with default type (full)
sudo snapshot-manager create
```

---

### list

List all existing snapshots.

```
sudo snapshot-manager list
```

Displays a table with the following columns:

- **Name** -- Snapshot directory name (timestamp-based)
- **Type** -- `system` or `full`
- **Size** -- Disk space used (unique data, not counting hard links)
- **Storage** -- `local` (on disk), `archived` (in borg), or `local+arch` (both)
- **Lock** -- Whether the snapshot is locked (protected from auto-cleanup)
- **Description** -- User-provided description

**Example:**

```bash
sudo snapshot-manager list
```

```
Name                    Type    Size    Storage      Lock  Description
full_2026-03-08_14-30   full    8.4G    local+arch   *     weekly full backup
full_2026-03-07_10-00   full    -       archived           daily backup
system_2026-03-06_02    system  2.1G    local              before kernel upgrade
```

---

### delete

Delete a snapshot from local disk and/or archive.

```
sudo snapshot-manager delete <name>
```

Removes the snapshot from wherever it exists (local rsync directory, borg
archive, or both). Refuses to delete locked snapshots. After deletion, the
GRUB menu is updated.

**Example:**

```bash
sudo snapshot-manager delete full_2026-03-07_10-00-00
```

---

### lock

Lock a snapshot to protect it from automatic cleanup by the retention policy.

```
sudo snapshot-manager lock <name>
```

Locked snapshots are never deleted by the retention policy. They can only be
removed by explicitly unlocking and then deleting them.

**Example:**

```bash
sudo snapshot-manager lock 20260308-090000
```

---

### unlock

Remove the lock from a snapshot.

```
sudo snapshot-manager unlock <name>
```

**Example:**

```bash
sudo snapshot-manager unlock 20260308-090000
```

---

### diff

Compare two snapshots and show what changed between them.

```
sudo snapshot-manager diff <snap1> <snap2>
```

Uses rsync in dry-run mode with itemize-changes (`--itemize-changes -n`) to
produce a detailed list of file differences.

**Example:**

```bash
sudo snapshot-manager diff 20260307-143022 20260308-090000
```

---

### restore-file

Restore a single file (or directory) from a snapshot.

```
sudo snapshot-manager restore-file <snapshot> <path> [destination]
```

**Arguments:**

| Argument      | Description                                                              |
|---------------|--------------------------------------------------------------------------|
| `<snapshot>`  | Name of the snapshot to restore from.                                    |
| `<path>`      | Absolute path of the file to restore (as it exists within the snapshot). |
| `[destination]` | Optional. Where to place the restored file. Defaults to the original path. |

Before overwriting the current file, the tool creates a backup with a
`.pre-restore-<timestamp>` suffix.

**Examples:**

```bash
# Restore /etc/fstab from a snapshot (overwrites current, backs up original)
sudo snapshot-manager restore-file 20260307-143022 /etc/fstab

# Restore to a different location
sudo snapshot-manager restore-file 20260307-143022 /etc/fstab /tmp/fstab.old
```

---

### verify

Verify the integrity of a snapshot.

```
sudo snapshot-manager verify <name>
```

Checks the following:

- Directory structure is intact.
- Boot files (kernel, initrd) are present.
- Essential system directories exist (`/etc`, `/usr`, `/var`, etc.).
- If a SHA256 manifest exists (`GENERATE_MANIFEST=true` was active during
  creation), checksums are verified against it.

**Example:**

```bash
sudo snapshot-manager verify 20260308-090000
```

---

### status

Show an overview of the snapshot system.

```
sudo snapshot-manager status
```

Displays:

- Disk usage of the snapshot directory (total, used, available).
- Number of system and full snapshots.
- Current configuration summary.
- Systemd timer status (if a scheduled snapshot timer is active).

**Example:**

```bash
sudo snapshot-manager status
```

---

### restore

Restore an archived snapshot back to local disk for GRUB boot restore.

```
sudo snapshot-manager restore <name>
```

Extracts a snapshot from the borg archive to the local snapshot directory,
making it available in the GRUB boot menu. If the snapshot is already local,
it informs you that no action is needed.

**Example:**

```bash
sudo snapshot-manager restore full_2026-03-07_10-00-00
```

---

### check

Run integrity check on all snapshots and the archive repository.

```
sudo snapshot-manager check
```

Checks:
- Local snapshots for essential files (boot/vmlinuz, boot/initrd.img, info.conf, fs/).
- Borg repository integrity (if `ARCHIVE_MODE=borg`).

**Example:**

```bash
sudo snapshot-manager check
```

---

### archive

Manually archive a local snapshot to the borg repository.

```
sudo snapshot-manager archive <name>
```

Archives the specified snapshot into the borg repository for space-efficient
long-term storage. Only available when `ARCHIVE_MODE=borg`.

**Example:**

```bash
sudo snapshot-manager archive full_2026-03-08_14-30-00
```

---

### help

Show usage information and a list of available commands.

```
sudo snapshot-manager help
```

---

## Exit Codes

| Code | Meaning                                                                 |
|------|-------------------------------------------------------------------------|
| 0    | Success.                                                                |
| 1    | Error (invalid arguments, missing snapshot, locked snapshot, etc.).      |

During snapshot creation, the following rsync exit codes are tolerated and do
not cause the command to fail:

| rsync Code | Meaning                                                          |
|------------|------------------------------------------------------------------|
| 23         | Partial transfer -- some files could not be transferred.         |
| 24         | Files vanished during transfer (common on a live system).        |

---

## Environment

### Root Requirement

All commands must be run as root (typically via `sudo`). The tool exits
immediately if it detects a non-root user.

### Concurrency Protection

The tool uses `flock` to acquire an exclusive lock before performing any
operation. If another instance is already running, the command will wait or
fail depending on the lock state.

### Configuration File

```
/etc/snapshot-manager.conf
```

See [configuration.md](configuration.md) for all available options.

### Log File

```
/var/log/snapshot-manager.log
```

All operations are logged with timestamps. Useful for debugging and auditing
scheduled snapshot jobs.
