#!/bin/bash
# Snapshot Manager Installer
# Installs the snapshot manager system with GRUB integration

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}This script must be run as root.${NC}"
    echo "Usage: sudo bash install.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Snapshot Manager Installation${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking requirements...${NC}"

# Check filesystem
ROOT_FS=$(findmnt -n -o FSTYPE /)
if [[ "$ROOT_FS" != "ext4" && "$ROOT_FS" != "ext3" && "$ROOT_FS" != "xfs" ]]; then
    echo -e "${RED}Warning: Root filesystem is '${ROOT_FS}'. This tool is designed for ext4/ext3/xfs.${NC}"
    read -rp "Do you want to continue? (y/n): " confirm
    [[ "$confirm" != "y" ]] && exit 1
fi
echo -e "  Filesystem: ${GREEN}${ROOT_FS}${NC}"

# Check rsync
if ! command -v rsync &>/dev/null; then
    echo -e "${YELLOW}rsync not found, installing...${NC}"
    apt-get update -qq && apt-get install -y -qq rsync
fi
echo -e "  rsync: ${GREEN}OK${NC}"

# Check borg (optional but recommended)
if ! command -v borg &>/dev/null; then
    echo -e "${YELLOW}borgbackup not found. Installing for borg archival support...${NC}"
    apt-get update -qq && apt-get install -y -qq borgbackup
fi
if command -v borg &>/dev/null; then
    echo -e "  borg: ${GREEN}OK ($(borg --version))${NC}"
else
    echo -e "  borg: ${YELLOW}not installed (borg archival disabled)${NC}"
fi

# Check GRUB
if [[ ! -d /etc/grub.d ]]; then
    echo -e "${RED}Error: GRUB not found. This tool requires GRUB2.${NC}"
    exit 1
fi
echo -e "  GRUB: ${GREEN}OK${NC}"

# Check available disk space
ROOT_AVAIL=$(df --output=avail / | tail -1)
ROOT_AVAIL_GB=$((ROOT_AVAIL / 1024 / 1024))
ROOT_USED=$(df --output=used / | tail -1)
ROOT_USED_GB=$((ROOT_USED / 1024 / 1024))

echo -e "  Disk usage: ${GREEN}${ROOT_USED_GB}GB used, ${ROOT_AVAIL_GB}GB free${NC}"

if [[ $ROOT_AVAIL_GB -lt $((ROOT_USED_GB * 2)) ]]; then
    echo -e "${YELLOW}Warning: There may not be enough space for snapshots.${NC}"
    echo -e "${YELLOW}At least ${ROOT_USED_GB}GB of additional space is recommended.${NC}"
    read -rp "Do you want to continue? (y/n): " confirm
    [[ "$confirm" != "y" ]] && exit 1
fi

echo ""
echo -e "${YELLOW}Installing files...${NC}"

# Read SNAPSHOT_DIR from config if it already exists, otherwise default
SNAPSHOT_DIR="/snapshots"
if [[ -f /etc/snapshot-manager.conf ]]; then
    _conf_dir=$(grep "^SNAPSHOT_DIR=" /etc/snapshot-manager.conf 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
    [[ -n "$_conf_dir" ]] && SNAPSHOT_DIR="$_conf_dir"
elif [[ -f "${SCRIPT_DIR}/etc/snapshot-manager.conf" ]]; then
    _conf_dir=$(grep "^SNAPSHOT_DIR=" "${SCRIPT_DIR}/etc/snapshot-manager.conf" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
    [[ -n "$_conf_dir" ]] && SNAPSHOT_DIR="$_conf_dir"
fi

# Create snapshot directory
mkdir -p "$SNAPSHOT_DIR"
echo -e "  ${GREEN}${SNAPSHOT_DIR} directory created${NC}"

# Install config
if [[ ! -f /etc/snapshot-manager.conf ]]; then
    cp "${SCRIPT_DIR}/etc/snapshot-manager.conf" /etc/snapshot-manager.conf
    echo -e "  ${GREEN}/etc/snapshot-manager.conf installed${NC}"
else
    echo -e "  ${YELLOW}/etc/snapshot-manager.conf already exists, skipping${NC}"
fi

# Install main script
cp "${SCRIPT_DIR}/usr/local/bin/snapshot-manager" /usr/local/bin/snapshot-manager
chmod +x /usr/local/bin/snapshot-manager
echo -e "  ${GREEN}/usr/local/bin/snapshot-manager installed${NC}"

# Install restore script
cp "${SCRIPT_DIR}/usr/local/bin/snapshot-restore" /usr/local/bin/snapshot-restore
chmod +x /usr/local/bin/snapshot-restore
echo -e "  ${GREEN}/usr/local/bin/snapshot-restore installed${NC}"

# Install apt hook (automatic pre-upgrade snapshot)
mkdir -p /etc/apt/apt.conf.d
cp "${SCRIPT_DIR}/etc/apt/apt.conf.d/80snapshot-manager" /etc/apt/apt.conf.d/80snapshot-manager
echo -e "  ${GREEN}/etc/apt/apt.conf.d/80snapshot-manager installed${NC}"

# Install kernel postinst hook (update restore.sh on new kernel)
mkdir -p /etc/kernel/postinst.d
cp "${SCRIPT_DIR}/etc/kernel/postinst.d/zz-snapshot-grub-update" /etc/kernel/postinst.d/zz-snapshot-grub-update
chmod +x /etc/kernel/postinst.d/zz-snapshot-grub-update
echo -e "  ${GREEN}/etc/kernel/postinst.d/zz-snapshot-grub-update installed${NC}"

# Install GRUB config
cp "${SCRIPT_DIR}/etc/grub.d/41_snapshots" /etc/grub.d/41_snapshots
chmod +x /etc/grub.d/41_snapshots
echo -e "  ${GREEN}/etc/grub.d/41_snapshots installed${NC}"

# Install GUI
cp "${SCRIPT_DIR}/snapshot-manager-gui.py" /usr/local/bin/snapshot-manager-gui
chmod +x /usr/local/bin/snapshot-manager-gui
echo -e "  ${GREEN}/usr/local/bin/snapshot-manager-gui installed${NC}"

# Install desktop file
mkdir -p /usr/share/applications
cp "${SCRIPT_DIR}/snapshot-manager.desktop" /usr/share/applications/snapshot-manager.desktop
echo -e "  ${GREEN}/usr/share/applications/snapshot-manager.desktop installed${NC}"

# Install polkit policy (required for pkexec GUI launch)
mkdir -p /usr/share/polkit-1/actions
cp "${SCRIPT_DIR}/etc/polkit-1/actions/com.snapshot-manager.gui.policy" /usr/share/polkit-1/actions/com.snapshot-manager.gui.policy
echo -e "  ${GREEN}/usr/share/polkit-1/actions/com.snapshot-manager.gui.policy installed${NC}"

# Update desktop database
update-desktop-database /usr/share/applications 2>/dev/null || true

# Install logrotate config (prevent log file growing indefinitely)
if [[ -d /etc/logrotate.d ]]; then
    cp "${SCRIPT_DIR}/etc/logrotate.d/snapshot-manager" /etc/logrotate.d/snapshot-manager
    echo -e "  ${GREEN}/etc/logrotate.d/snapshot-manager installed${NC}"
fi

# Install systemd timer units
cp "${SCRIPT_DIR}/etc/systemd/system/snapshot-daily.service" /etc/systemd/system/snapshot-daily.service
cp "${SCRIPT_DIR}/etc/systemd/system/snapshot-daily.timer" /etc/systemd/system/snapshot-daily.timer
cp "${SCRIPT_DIR}/etc/systemd/system/snapshot-weekly.service" /etc/systemd/system/snapshot-weekly.service
cp "${SCRIPT_DIR}/etc/systemd/system/snapshot-weekly.timer" /etc/systemd/system/snapshot-weekly.timer
systemctl daemon-reload
echo -e "  ${GREEN}Systemd timer files installed${NC}"
echo -e "  ${YELLOW}To enable timers:${NC}"
echo -e "    sudo systemctl enable --now snapshot-daily.timer"
echo -e "    sudo systemctl enable --now snapshot-weekly.timer"

# Configure GRUB timeout (menu must be visible for snapshot selection)
echo ""
echo -e "${YELLOW}Configuring GRUB settings...${NC}"
GRUB_CFG="/etc/default/grub"

# Set timeout to 5 seconds (only if currently 0 or hidden)
CURRENT_TIMEOUT=$(grep "^GRUB_TIMEOUT=" "$GRUB_CFG" 2>/dev/null | head -1 | cut -d= -f2 | tr -d '"' | tr -d "'")
if [[ -z "$CURRENT_TIMEOUT" ]]; then
    echo "GRUB_TIMEOUT=5" >> "$GRUB_CFG"
elif [[ "$CURRENT_TIMEOUT" -lt 3 ]]; then
    sed -i 's/^GRUB_TIMEOUT=.*/GRUB_TIMEOUT=5/' "$GRUB_CFG"
fi

# Make menu visible (required for snapshot selection)
if grep -q "^GRUB_TIMEOUT_STYLE=" "$GRUB_CFG"; then
    sed -i 's/^GRUB_TIMEOUT_STYLE=.*/GRUB_TIMEOUT_STYLE=menu/' "$GRUB_CFG"
else
    echo "GRUB_TIMEOUT_STYLE=menu" >> "$GRUB_CFG"
fi

echo -e "  ${GREEN}GRUB_TIMEOUT=5${NC}"
echo -e "  ${GREEN}GRUB_TIMEOUT_STYLE=menu${NC}"

# Update GRUB
echo ""
echo -e "${YELLOW}Updating GRUB menu...${NC}"
if command -v update-grub &>/dev/null; then
    update-grub
elif command -v grub-mkconfig &>/dev/null; then
    grub-mkconfig -o /boot/grub/grub.cfg
else
    echo -e "${RED}Warning: GRUB update command not found!${NC}"
fi
echo -e "${GREEN}GRUB menu updated.${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Installation complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "Usage:"
echo -e "  ${BLUE}sudo snapshot-manager create${NC}             - Full backup (default, includes home)"
echo -e "  ${BLUE}sudo snapshot-manager create system${NC}      - System backup (excludes home)"
echo -e "  ${BLUE}sudo snapshot-manager list${NC}               - List all snapshots"
echo -e "  ${BLUE}sudo snapshot-manager delete <name>${NC}      - Delete snapshot"
echo -e "  ${BLUE}sudo snapshot-manager restore <name>${NC}     - Restore archived snapshot"
echo -e "  ${BLUE}sudo snapshot-manager check${NC}              - Integrity check"
echo -e "  ${BLUE}sudo snapshot-manager status${NC}             - System status"
echo -e "  ${BLUE}sudo snapshot-manager help${NC}               - All commands"
echo ""
echo -e "Restore:"
echo -e "  Restart the computer and select"
echo -e "  ${YELLOW}'Snapshot Restore >'${NC} submenu in the GRUB menu."
echo ""
echo -e "${YELLOW}Would you like to create your first snapshot? (y/n):${NC}"
read -rp "" create_first

if [[ "$create_first" == "y" ]]; then
    echo ""
    echo "Which type? (1=Full, 2=System)"
    read -rp "> " snap_type
    if [[ "$snap_type" == "2" ]]; then
        snapshot-manager create system "Initial installation backup"
    else
        snapshot-manager create full "Initial installation backup"
    fi
fi
