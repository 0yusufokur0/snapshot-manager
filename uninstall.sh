#!/bin/bash
# Snapshot Manager Uninstaller

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}This script must be run as root.${NC}"
    echo "Usage: sudo bash uninstall.sh"
    exit 1
fi

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  Snapshot Manager Uninstall${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Read SNAPSHOT_DIR from config
SNAPSHOT_DIR="/snapshots"
if [[ -f /etc/snapshot-manager.conf ]]; then
    _conf_dir=$(grep "^SNAPSHOT_DIR=" /etc/snapshot-manager.conf 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'")
    [[ -n "$_conf_dir" ]] && SNAPSHOT_DIR="$_conf_dir"
fi

# Disable timers
echo -e "${YELLOW}Disabling timers...${NC}"
systemctl disable --now snapshot-daily.timer 2>/dev/null || true
systemctl disable --now snapshot-weekly.timer 2>/dev/null || true

# Remove installed files
echo -e "${YELLOW}Removing files...${NC}"

rm -f /usr/local/bin/snapshot-manager
rm -f /usr/local/bin/snapshot-restore
rm -f /usr/local/bin/snapshot-manager-gui
rm -f /usr/share/applications/snapshot-manager.desktop
rm -f /usr/share/polkit-1/actions/com.snapshot-manager.gui.policy
rm -f /etc/apt/apt.conf.d/80snapshot-manager
rm -f /etc/kernel/postinst.d/zz-snapshot-grub-update
rm -f /etc/grub.d/41_snapshots
rm -f /etc/logrotate.d/snapshot-manager
rm -f /etc/systemd/system/snapshot-daily.service
rm -f /etc/systemd/system/snapshot-daily.timer
rm -f /etc/systemd/system/snapshot-weekly.service
rm -f /etc/systemd/system/snapshot-weekly.timer
rm -f /etc/systemd/system/snapshot-post-restore.service
rm -f /etc/systemd/system/multi-user.target.wants/snapshot-post-restore.service

systemctl daemon-reload

echo -e "  ${GREEN}All program files removed${NC}"

# Remove restore.sh from snapshot dir (immutable flag)
if [[ -f "${SNAPSHOT_DIR}/restore.sh" ]]; then
    chattr -i "${SNAPSHOT_DIR}/restore.sh" 2>/dev/null || true
    rm -f "${SNAPSHOT_DIR}/restore.sh"
    echo -e "  ${GREEN}${SNAPSHOT_DIR}/restore.sh removed${NC}"
fi

# Remove config
rm -f /etc/snapshot-manager.conf
echo -e "  ${GREEN}/etc/snapshot-manager.conf removed${NC}"

# Update GRUB (remove snapshot entries)
echo ""
echo -e "${YELLOW}Updating GRUB menu...${NC}"
if command -v update-grub &>/dev/null; then
    update-grub 2>&1 | tail -3
elif command -v grub-mkconfig &>/dev/null; then
    grub-mkconfig -o /boot/grub/grub.cfg 2>&1 | tail -3
fi
echo -e "${GREEN}GRUB menu updated.${NC}"

# Ask about snapshots
echo ""
SNAP_COUNT=$(find "$SNAPSHOT_DIR" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l)
if [[ "$SNAP_COUNT" -gt 0 ]]; then
    echo -e "${YELLOW}Found ${SNAP_COUNT} snapshot(s) in ${SNAPSHOT_DIR}${NC}"
    read -rp "Delete all snapshots? This cannot be undone! (y/n): " del_snaps
    if [[ "$del_snaps" == "y" ]]; then
        rm -rf "${SNAPSHOT_DIR}"
        echo -e "  ${GREEN}Snapshots deleted${NC}"
    else
        echo -e "  ${YELLOW}Snapshots preserved at ${SNAPSHOT_DIR}${NC}"
    fi
else
    rmdir "${SNAPSHOT_DIR}" 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Uninstall complete!${NC}"
echo -e "${GREEN}============================================${NC}"
