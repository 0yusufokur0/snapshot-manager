# Snapshot Manager - GTK4 GUI Application

## Overview

The GUI is a single-file GTK4 application (`snapshot-manager-gui.py`) built with **GTK4 + libadwaita**, the modern GNOME toolkit. It provides a graphical interface for all snapshot management operations.

Key design points:

- Auto-elevates to root via `pkexec` on startup (required for rsync/mount operations).
- Preserves the user's theme preference (dark/light) across privilege elevation.
- All long-running operations run in background threads with real-time progress feedback.

## Features

### Main Screen

Lists all existing snapshots in a table showing:

- Snapshot name
- Date created
- Type (System / Full)
- Description

A banner at the top displays **disk usage** and the current **storage location**.

### Create Snapshot

- Select snapshot type: **System** or **Full**.
- Enter a free-text description.
- Real-time **progress bar** that parses rsync `--info=progress2` output.
- **Cancel button** to abort an in-progress snapshot.

### Snapshot Details

Click any snapshot in the list to view its full details:

- Name, type, date, kernel version, description, size, lock status.

Available actions:

- **Delete** the snapshot.
- **Verify** snapshot integrity.
- **Lock / Unlock** to protect against automatic retention cleanup.

### Settings Dialog

| Section | Options |
|---|---|
| **Language** | Language selector (English / Turkish) — applies to GUI and GRUB menu entries |
| **Storage location** | Disk selection with available drives listed via `lsblk` |
| **Retention limits** | Maximum number of system and full snapshots |
| **Retention policy** | Daily / weekly / monthly keep counts |
| **Performance** | Low priority toggle (ionice/nice), SHA256 manifest toggle |
| **Scheduled backups** | Enable/disable daily and weekly systemd timers |

Changing the language updates the `LANGUAGE` setting in `/etc/snapshot-manager.conf`. The GUI reloads all labels immediately. GRUB menu entries update on the next `update-grub` run (which happens automatically when creating or deleting snapshots).

### Disk Migration

When the storage location is changed in settings, existing snapshots are **automatically moved** to the new location. A space check is performed before migration starts.

### Disk Space Warning

A warning banner appears on the main screen when storage disk usage exceeds **85%**.

### Dark / Light Theme

The GUI detects the user's GNOME `color-scheme` setting and applies the matching theme. This preference is passed through the `pkexec` elevation so root-level execution still uses the correct theme.

## Technical Details

### Progress Parsing

The progress bar parses rsync `--info=progress2` output. Two formats are handled:

- `xfr#N, to-chk=R/T` - Stable total; R (remaining) and T (total) are reliable.
- `ir-chk=R/T` - Incremental scan; total may change as rsync discovers more files.

The **byte percentage** from rsync output is used as the main progress indicator because it is always monotonically increasing, providing a smooth progress bar experience.

### Thread Safety

Background operations (snapshot creation, deletion, verification) run in `threading.Thread`. All GTK widget updates are dispatched back to the main thread via `GLib.idle_add()` to avoid race conditions.

### Root Elevation

On startup, if not already root, the application re-launches itself through `pkexec` using `os.execvp("pkexec", ...)`. The following environment variables are forwarded to preserve display and theme access:

- `DISPLAY`
- `XAUTHORITY`
- `XDG_RUNTIME_DIR`
- `DBUS_SESSION_BUS_ADDRESS`
- `HOME`
- Color-scheme preference (as a custom variable)

### Configuration

Reads and writes `/etc/snapshot-manager.conf` directly, using the same INI-style format as the CLI tool. Changes made in the GUI are immediately reflected for CLI usage and vice versa.

### Drive Listing

Available drives and partitions are enumerated using `lsblk --json`. The output is parsed with device tree traversal to present a structured list of available storage targets in the settings dialog.

## Dependencies

| Package | Purpose |
|---|---|
| `python3` | Python runtime |
| `python3-gi` | PyGObject bindings |
| `gir1.2-gtk-4.0` | GTK4 introspection data |
| `gir1.2-adw-1` | libadwaita introspection data |

Install on Ubuntu/Debian:

```bash
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
```
