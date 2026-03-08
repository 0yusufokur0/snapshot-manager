# Snapshot Manager - Future Ideas

These are suggestions for future development. None of these are currently implemented.

## High Priority

### 1. Uninstall Script

Provide a clean removal script that deletes all installed files, systemd timer/service units, GRUB configuration entries, and optionally the snapshot storage directory.

### 2. Encryption Support

Encrypt snapshots at rest, especially important when using external disks. Could use LUKS for full-disk encryption or per-snapshot encryption with GPG/age.

### 3. Pre/Post Hooks

User-configurable scripts that run before and after snapshot creation. Practical use cases include:

- Dumping a database before snapshot
- Stopping a service during snapshot
- Sending a notification after completion

Hook scripts could be placed in `/etc/snapshot-manager/hooks.d/` with `pre-` and `post-` prefixes.

### 4. Email / Notification on Failure

Alert the user when a scheduled snapshot fails. Could support:

- Email (via sendmail/msmtp)
- Desktop notification (notify-send)
- Webhook (curl to Slack/Discord/Telegram)

## Medium Priority

### 5. Remote Backup

Sync snapshots to a remote SSH server using rsync over SSH. Since rsync is already the underlying tool, this is a natural extension. Would need:

- Remote host/path configuration
- SSH key management
- Bandwidth limiting options

### 6. Snapshot Notes / Tags

Allow adding and editing tags or notes on existing snapshots for better organization. For example: `pre-upgrade`, `stable`, `testing`.

### 7. Compression

Optional compression for snapshots to trade CPU time for disk space savings. Candidates:

- `zstd` (fast, good ratio)
- `gzip` (universal)
- Per-file or archive-level compression

### 8. Web UI

A lightweight web interface for managing snapshots on headless servers. Could be built with Flask or FastAPI, providing the same functionality as the GTK4 GUI without requiring a desktop environment.

### 9. Snapshot Browsing

Browse the contents of a snapshot from the GUI with a file-manager-like view. Allow viewing, comparing, and selectively restoring individual files without a full restore.

### 10. Automatic Disk Space Management

Auto-delete the oldest unlocked snapshots when available disk space falls below a configurable threshold. This would prevent snapshot creation from failing due to full disks.

## Low Priority / Nice to Have

### 11. Version Tracking

Track the installed version of snapshot-manager. Support `snapshot-manager --version` to display it. Useful for bug reports and upgrade management.

### 12. JSON Output

Add a `--json` flag to CLI commands (e.g., `snapshot-manager list --json`) to produce machine-readable output for scripting and integration with other tools.

### 13. Bash Completion

Tab completion for commands, options, and snapshot names. Install a completion script to `/usr/share/bash-completion/completions/`.

### 14. Man Page

Write and install a standard man page (`man snapshot-manager`) covering all CLI commands and options.

### 15. Package Distribution

Build a `.deb` package for easier installation and updates on Debian/Ubuntu systems. Could also explore Flatpak or Snap for the GUI component.

### 16. Multi-Disk Striping

Spread snapshots across multiple disks to increase available storage or improve throughput. Would require a disk pool abstraction layer.

### 17. Integrity Scheduler

Periodic automatic verification of snapshot integrity (checksums, file counts). Could run as a weekly systemd timer and report any corruption detected.

### 18. Migration Tool

Export and import snapshots between machines. Package a snapshot with its metadata into a portable archive that can be transferred and restored on a different system.

## Architecture Improvements

### 19. Modular Script Design

Split the monolithic `snapshot-manager` bash script into a library of source-able functions plus a thin CLI wrapper. This would improve testability and allow other scripts to reuse snapshot logic.

### 20. Unit Tests

Automated testing with mock filesystems (e.g., tmpfs or fakeroot). Cover core operations: create, delete, verify, restore, retention policy enforcement.

### 21. CI/CD Pipeline

GitHub Actions workflow for:

- `shellcheck` on all bash scripts
- Python linting (flake8/ruff) on the GUI
- Automated test execution
- Release artifact building

### 22. Plugin System

Allow third-party extensions through a plugin architecture. Example plugin types:

- **Notification backends** (email, Slack, Telegram)
- **Storage backends** (local, SSH, S3)
- **Scheduling backends** (systemd, cron, custom)
