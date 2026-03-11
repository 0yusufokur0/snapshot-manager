# Snapshot Manager

An rsync-based snapshot and restore system for Linux with GRUB boot menu integration. Supports ext4, ext3, and xfs filesystems.

Unlike BTRFS/ZFS snapshots, this tool works on any standard Linux filesystem by using rsync with hardlink deduplication. Snapshots appear directly in the GRUB boot menu, allowing you to restore your system without booting into the OS first.

## Features

- **rsync + hardlink snapshots** — Incremental backups with minimal disk usage via `--link-dest`
- **Borg archival backend** — Chunk-level deduplication and zstd compression for long-term storage
- **GRUB boot menu integration** — All snapshots appear in GRUB for one-click restore at boot time
- **4 restore modes** — Full, System only, User data only, Kernel only
- **Boot-time restore** — Selected snapshot is automatically restored before the OS boots
- **Two snapshot types** — `system` (excluding /home) and `full` (including /home, default)
- **External disk support** — Store snapshots on a separate disk; GRUB and restore handle it automatically
- **GTK4 GUI** — Modern graphical interface with dark/light theme support
- **APT hook** — Automatic snapshot before every package install/upgrade/remove
- **Scheduled backups** — Daily and weekly systemd timers
- **Retention policies** — Automatic cleanup with daily/weekly/monthly keep rules
- **Snapshot locking** — Protect important snapshots from auto-cleanup
- **Integrity checking** — Verify all snapshots and archive repository integrity
- **Single file restore** — Extract individual files without full system restore
- **Snapshot diff** — Compare two snapshots to see what changed
- **SHA256 verification** — Optional integrity manifests for snapshot validation
- **Polkit integration** — GUI launches with proper privilege escalation via pkexec
- **Multi-language support** — English (default) and Turkish, configurable from GUI Settings or config file

## Quick Start

```bash
# Install
git clone https://github.com/0yusufokur0/snapshot-manager.git
cd snapshot-manager
sudo bash install.sh

# Create your first snapshot (full = includes /home)
sudo snapshot-manager create full "Initial backup"

# List snapshots
sudo snapshot-manager list

# Restore from GRUB: reboot and select "Snapshot Restore >" from the boot menu
```

## Usage

### Creating Snapshots

```bash
# Full backup (includes /home) — default
sudo snapshot-manager create

# System backup (excludes /home)
sudo snapshot-manager create system

# With a description
sudo snapshot-manager create full "Before major update"
```

### Managing Snapshots

```bash
# List all snapshots (local and archived)
sudo snapshot-manager list

# Delete a snapshot (from local and/or archive)
sudo snapshot-manager delete full_2026-03-08_14-30-00

# Restore an archived snapshot for GRUB boot restore
sudo snapshot-manager restore full_2026-03-01_02-00-00

# Run integrity check on all snapshots and archives
sudo snapshot-manager check

# Manually archive a local snapshot
sudo snapshot-manager archive full_2026-03-08_14-30-00

# Lock (protect from auto-cleanup)
sudo snapshot-manager lock full_2026-03-08_14-30-00

# Compare two snapshots
sudo snapshot-manager diff full_2026-03-01_02-00-00 full_2026-03-08_02-00-00

# Restore a single file
sudo snapshot-manager restore-file full_2026-03-08_14-30-00 /etc/nginx/nginx.conf

# Verify snapshot integrity
sudo snapshot-manager verify full_2026-03-08_14-30-00

# Show system status
sudo snapshot-manager status
```

### Restoring from GRUB

1. Reboot your computer
2. In the GRUB menu, select **"Snapshot Restore >"**
3. Choose the snapshot you want to restore
4. Select the restore mode:
   - **Full Restore** — System + user data (requires full snapshot)
   - **System Only** — System files only (excludes /home)
   - **User Data Only** — Only /home (requires full snapshot)
   - **Kernel Only** — Only /boot (kernel + initramfs)
5. Wait for the 5-second countdown (power off to cancel)
6. System restores automatically and reboots

### GUI

```bash
snapshot-manager-gui
```

The GUI provides a graphical interface for all operations including snapshot creation with real-time progress, archived snapshot restore, integrity checking, settings management, and disk migration.

### Scheduled Backups

```bash
# Enable daily system backup (2:00 AM)
sudo systemctl enable --now snapshot-daily.timer

# Enable weekly full backup (Sunday 3:00 AM)
sudo systemctl enable --now snapshot-weekly.timer

# Check timer status
systemctl list-timers snapshot-*
```

## Configuration

Edit `/etc/snapshot-manager.conf`:

```bash
SNAPSHOT_DIR="/snapshots"       # Storage directory (local or external disk)
LANGUAGE=en                     # Display language: en (English) or tr (Turkish)
MAX_SYSTEM_SNAPSHOTS=0          # Max system snapshots (0=unlimited)
MAX_FULL_SNAPSHOTS=0            # Max full snapshots (0=unlimited)
KEEP_DAILY=7                    # Keep latest per day for 7 days
KEEP_WEEKLY=4                   # Keep latest per week for 4 weeks
KEEP_MONTHLY=6                  # Keep latest per month for 6 months
LOW_PRIORITY=true               # Run at low I/O priority
GENERATE_MANIFEST=false         # SHA256 integrity manifest

# Borg archival (optional, space-efficient long-term storage)
ARCHIVE_MODE=borg               # none = rsync only, borg = rsync + borg archival
BORG_COMPRESSION="zstd,3"      # Compression algorithm
BORG_KEEP_DAILY=7               # Borg retention: daily archives
BORG_KEEP_WEEKLY=4              # Borg retention: weekly archives
BORG_KEEP_MONTHLY=6             # Borg retention: monthly archives
MAX_RECENT_RSYNC=3              # Recent rsync snapshots to keep for GRUB
```

## Requirements

- Linux with GRUB2 bootloader
- ext4, ext3, or xfs root filesystem
- rsync (auto-installed if missing)
- borg (optional, for archive mode — `sudo apt install borgbackup`)
- Root access

### GUI Requirements

- python3, python3-gi (PyGObject)
- GTK4 (`gir1.2-gtk-4.0`)
- libadwaita (`gir1.2-adw-1`)

## Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/install.md) | Detailed installation and setup instructions |
| [Architecture](docs/architecture.md) | System design, components, and data flow |
| [CLI Reference](docs/cli-reference.md) | Complete command reference with examples |
| [Configuration](docs/configuration.md) | All configuration options explained |
| [GRUB & Restore](docs/grub-restore.md) | Boot-time restore mechanism details |
| [GUI](docs/gui.md) | Graphical interface documentation |
| [Security](docs/security.md) | Security model and considerations |
| [Future Ideas](docs/future-ideas.md) | Planned features and contribution ideas |

## How It Works

1. **Snapshot creation**: rsync copies the filesystem with `--link-dest` for hardlink deduplication against the previous snapshot. Kernel and initramfs are copied separately for GRUB access.

2. **Borg archival**: When `ARCHIVE_MODE=borg`, each new snapshot is also archived into a Borg repository for chunk-level deduplication and zstd compression. Only the most recent rsync snapshots are kept on disk for GRUB; older ones are stored space-efficiently in the Borg archive.

3. **GRUB integration**: `/etc/grub.d/41_snapshots` generates boot menu entries. For external disks, it automatically detects the disk UUID and generates correct GRUB paths.

4. **Boot-time restore**: When you select a snapshot from GRUB, the kernel boots with `init=/usr/local/bin/snapshot-restore`. The restore script runs as PID 1, reads the snapshot directory from config, runs rsync to restore, and reboots.

## Uninstall

```bash
cd snapshot-manager
sudo bash uninstall.sh
```

This removes all program files, configs, GRUB entries, and systemd timers. You will be asked whether to delete existing snapshots.

## Known Limitations

1. **Not atomic** — Unlike BTRFS/ZFS, rsync-based snapshots are not atomic. Files may change during the copy (rsync exit codes 23/24 are tolerated).
2. **Power loss risk** — Power loss during restore can leave the system in an inconsistent state.
3. **PID 1 dependency** — The restore script runs as PID 1. If bash or rsync is corrupted, a kernel panic may occur.
4. **Not instantaneous** — Snapshot creation takes time proportional to data size (unlike BTRFS which is instant).
5. **Disk space** — Each snapshot uses disk space proportional to changed files (hardlinks share unchanged files).

## License

MIT
