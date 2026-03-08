# Installation Guide

## Prerequisites

- **Operating System**: Linux with GRUB2 bootloader (tested on Ubuntu 22.04+, Debian 12+)
- **Filesystem**: ext4, ext3, or xfs root filesystem
- **Packages**: rsync (auto-installed if missing)
- **Access**: Root privileges (sudo)

### GUI Prerequisites (optional)

```bash
# Ubuntu/Debian
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1

# Fedora
sudo dnf install python3-gobject gtk4 libadwaita

# Arch Linux
sudo pacman -S python-gobject gtk4 libadwaita
```

## Installation

### From GitHub

```bash
git clone https://github.com/0yusufokur0/snapshot-manager.git
cd snapshot-manager
sudo bash install.sh
```

### Manual Installation

If you prefer to install manually:

```bash
# Copy main scripts
sudo cp usr/local/bin/snapshot-manager /usr/local/bin/
sudo cp usr/local/bin/snapshot-restore /usr/local/bin/
sudo chmod +x /usr/local/bin/snapshot-manager /usr/local/bin/snapshot-restore

# Copy GUI (optional)
sudo cp snapshot-manager-gui.py /usr/local/bin/snapshot-manager-gui
sudo chmod +x /usr/local/bin/snapshot-manager-gui

# Copy configuration (don't overwrite existing)
sudo cp -n etc/snapshot-manager.conf /etc/snapshot-manager.conf

# Create snapshot directory
sudo mkdir -p /snapshots

# Copy restore script to snapshot directory (immutable)
sudo cp usr/local/bin/snapshot-restore /snapshots/restore.sh
sudo chmod +x /snapshots/restore.sh
sudo chattr +i /snapshots/restore.sh

# Copy GRUB script
sudo cp etc/grub.d/41_snapshots /etc/grub.d/
sudo chmod +x /etc/grub.d/41_snapshots

# Copy APT hook (Debian/Ubuntu only)
sudo cp etc/apt/apt.conf.d/80snapshot-manager /etc/apt/apt.conf.d/

# Copy kernel postinst hook
sudo cp etc/kernel/postinst.d/zz-snapshot-grub-update /etc/kernel/postinst.d/
sudo chmod +x /etc/kernel/postinst.d/zz-snapshot-grub-update

# Copy logrotate config
sudo cp etc/logrotate.d/snapshot-manager /etc/logrotate.d/

# Copy systemd timers
sudo cp etc/systemd/system/snapshot-daily.* /etc/systemd/system/
sudo cp etc/systemd/system/snapshot-weekly.* /etc/systemd/system/
sudo systemctl daemon-reload

# Copy desktop file (optional, for GUI)
sudo cp snapshot-manager.desktop /usr/share/applications/

# Configure GRUB (menu must be visible for snapshot selection)
# Set timeout to at least 5 seconds
sudo sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=5/' /etc/default/grub
sudo sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=menu/' /etc/default/grub

# Update GRUB
sudo update-grub  # or: sudo grub-mkconfig -o /boot/grub/grub.cfg
```

## What the Installer Does

1. **Checks prerequisites**: Verifies filesystem type, GRUB presence, disk space
2. **Installs rsync** if not present
3. **Copies all scripts** to their system locations
4. **Creates snapshot directory** (`/snapshots` by default)
5. **Copies restore script** to snapshot directory with immutable flag
6. **Configures GRUB**: Sets timeout to 5 seconds, makes menu visible
7. **Updates GRUB**: Runs `update-grub` to generate snapshot menu entries
8. **Optionally creates first snapshot**

## Post-Installation

### Verify Installation

```bash
# Check that the command works
sudo snapshot-manager status

# Verify GRUB entry exists
sudo grep -c "Snapshot Restore" /boot/grub/grub.cfg
```

### Create Your First Snapshot

```bash
sudo snapshot-manager create system "Initial backup"
```

### Enable Scheduled Backups (Optional)

```bash
# Daily system backup at 2:00 AM
sudo systemctl enable --now snapshot-daily.timer

# Weekly full backup on Sundays at 3:00 AM
sudo systemctl enable --now snapshot-weekly.timer
```

### External Disk Setup (Optional)

To store snapshots on an external disk:

1. Mount the external disk (e.g., `/mnt/backup-disk`)
2. Create a snapshots directory: `sudo mkdir -p /mnt/backup-disk/snapshots`
3. Edit `/etc/snapshot-manager.conf`:
   ```bash
   SNAPSHOT_DIR="/mnt/backup-disk/snapshots"
   ```
4. Update GRUB: `sudo update-grub`

The GRUB script automatically detects external disks and generates correct boot entries.

**Important**: The external disk must be mounted when creating snapshots and when running `update-grub`. It does NOT need to be mounted during normal boot — GRUB accesses it directly.

## Uninstallation

```bash
# Remove scripts
sudo rm -f /usr/local/bin/snapshot-manager
sudo rm -f /usr/local/bin/snapshot-restore
sudo rm -f /usr/local/bin/snapshot-manager-gui

# Remove configuration
sudo rm -f /etc/snapshot-manager.conf

# Remove GRUB script and update
sudo rm -f /etc/grub.d/41_snapshots
sudo update-grub

# Remove hooks
sudo rm -f /etc/apt/apt.conf.d/80snapshot-manager
sudo rm -f /etc/kernel/postinst.d/zz-snapshot-grub-update

# Remove systemd timers
sudo systemctl disable --now snapshot-daily.timer snapshot-weekly.timer 2>/dev/null
sudo rm -f /etc/systemd/system/snapshot-daily.*
sudo rm -f /etc/systemd/system/snapshot-weekly.*
sudo systemctl daemon-reload

# Remove other files
sudo rm -f /etc/logrotate.d/snapshot-manager
sudo rm -f /usr/share/applications/snapshot-manager.desktop

# Remove restore script (remove immutable flag first)
sudo chattr -i /snapshots/restore.sh 2>/dev/null
sudo rm -f /snapshots/restore.sh

# Optionally remove all snapshots (DESTRUCTIVE!)
# sudo rm -rf /snapshots
```

## Troubleshooting

### GRUB menu doesn't show "Snapshot Restore"
- Ensure GRUB_TIMEOUT >= 3 in `/etc/default/grub`
- Ensure GRUB_TIMEOUT_STYLE=menu in `/etc/default/grub`
- Run `sudo update-grub`
- Verify snapshots exist: `sudo snapshot-manager list`

### "Permission denied" errors
- All commands require root: use `sudo`
- GUI auto-elevates via pkexec

### Snapshot creation is slow
- First snapshot copies everything; subsequent ones use hardlinks
- Enable `LOW_PRIORITY=true` in config to avoid system slowdown
- Consider excluding large directories by customizing the exclude list

### External disk snapshots don't appear in GRUB
- Ensure the disk is mounted when running `sudo update-grub`
- Check config: `grep SNAPSHOT_DIR /etc/snapshot-manager.conf`
- Verify the disk has snapshots: `ls <SNAPSHOT_DIR>/*/info.conf`

### Restore fails with "Snapshot not found"
- The snapshot directory must be accessible at boot time
- For external disks: the restore script mounts the disk automatically using UUID
- Check kernel parameters in GRUB: `snapshot.disk=` and `snapshot.dir=` should be present
