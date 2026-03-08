# Configuration

snapshot-manager is configured through a single file:

```
/etc/snapshot-manager.conf
```

The file uses bash variable syntax. Lines starting with `#` are comments.

---

## Options

### SNAPSHOT_DIR

```bash
SNAPSHOT_DIR="/snapshots"
```

The directory where all snapshots are stored. Each snapshot is created as a
subdirectory under this path.

This can be a local directory or a mount point for an external disk. The
directory must exist and be writable by root.

---

### LANGUAGE

```bash
LANGUAGE=en
```

Sets the display language for the GUI and GRUB boot menu entries.

| Value | Language |
|-------|----------|
| `en`  | English (default) |
| `tr`  | Turkish |

Can also be changed from the GUI Settings dialog. GRUB menu entries update on the next `update-grub` run (which happens automatically when creating/deleting snapshots).

---

### MAX_SYSTEM_SNAPSHOTS

```bash
MAX_SYSTEM_SNAPSHOTS=0
```

Maximum number of system-type snapshots to keep. When this limit is exceeded,
the oldest unlocked system snapshot is deleted after a new one is created.

Set to `0` to disable this limit (unlimited). This setting is ignored if any
of the `KEEP_*` retention policies are active (non-zero).

---

### MAX_FULL_SNAPSHOTS

```bash
MAX_FULL_SNAPSHOTS=0
```

Maximum number of full-type snapshots to keep. Behaves the same as
`MAX_SYSTEM_SNAPSHOTS` but applies to full snapshots.

Set to `0` to disable this limit (unlimited). This setting is ignored if any
of the `KEEP_*` retention policies are active (non-zero).

---

### KEEP_DAILY

```bash
KEEP_DAILY=0
```

Keep the latest snapshot from each of the last N days.

Set to `0` to disable daily retention.

For example, `KEEP_DAILY=7` keeps one snapshot per day for the last 7 days.
If multiple snapshots exist for the same day, only the most recent one is
retained.

---

### KEEP_WEEKLY

```bash
KEEP_WEEKLY=0
```

Keep the latest snapshot from each of the last N ISO weeks.

Set to `0` to disable weekly retention.

For example, `KEEP_WEEKLY=4` keeps one snapshot per ISO week for the last 4
weeks.

---

### KEEP_MONTHLY

```bash
KEEP_MONTHLY=0
```

Keep the latest snapshot from each of the last N months.

Set to `0` to disable monthly retention.

For example, `KEEP_MONTHLY=6` keeps one snapshot per month for the last 6
months.

---

### LOW_PRIORITY

```bash
LOW_PRIORITY=true
```

When set to `true`, rsync runs with reduced I/O and CPU priority:

- `ionice -c3` -- idle I/O scheduling class (only uses I/O when no other
  process needs it).
- `nice -n 19` -- lowest CPU scheduling priority.

This prevents snapshot creation from impacting system responsiveness. Set to
`false` if you want snapshots to complete as fast as possible.

---

### GENERATE_MANIFEST

```bash
GENERATE_MANIFEST=false
```

When set to `true`, a SHA256 checksum manifest is generated after snapshot
creation. This manifest is stored inside the snapshot directory and is used
by the `verify` command to check file integrity.

Generating manifests adds time to snapshot creation (proportional to the
amount of data), but enables reliable integrity verification later.

---

## Retention Policy Algorithm

When `KEEP_DAILY`, `KEEP_WEEKLY`, or `KEEP_MONTHLY` are set to non-zero
values, the retention policy runs automatically after each snapshot creation.
The algorithm works as follows:

1. **Locked snapshots are always kept.** They are excluded from retention
   evaluation entirely.

2. **Daily retention:** For each of the last N days (where N = `KEEP_DAILY`),
   the most recent snapshot from that day is marked as "keep."

3. **Weekly retention:** For each of the last N ISO weeks (where N =
   `KEEP_WEEKLY`), the most recent snapshot from that week is marked as
   "keep."

4. **Monthly retention:** For each of the last N months (where N =
   `KEEP_MONTHLY`), the most recent snapshot from that month is marked as
   "keep."

5. **Cleanup:** Any unlocked snapshot that was not marked as "keep" by any
   of the above policies is deleted. The GRUB menu is updated after
   deletions.

A single snapshot can satisfy multiple policies simultaneously. For example,
today's latest snapshot might count as both the daily and the weekly keeper.

When all `KEEP_*` values are `0`, the retention policy is inactive and
`MAX_SYSTEM_SNAPSHOTS` / `MAX_FULL_SNAPSHOTS` are used instead (simple
count-based limits).

---

## Example Configurations

### Server -- Conservative Retention

Keep a deep history with daily, weekly, and monthly snapshots. Manifests
enabled for integrity auditing.

```bash
# /etc/snapshot-manager.conf

SNAPSHOT_DIR="/snapshots"
MAX_SYSTEM_SNAPSHOTS=0
MAX_FULL_SNAPSHOTS=0

KEEP_DAILY=7
KEEP_WEEKLY=4
KEEP_MONTHLY=12

LOW_PRIORITY=true
GENERATE_MANIFEST=true
```

This keeps:
- 1 snapshot per day for the last 7 days
- 1 snapshot per week for the last 4 weeks
- 1 snapshot per month for the last 12 months

Combined with a daily systemd timer, this provides roughly 7 + 4 + 12 = 23
snapshots at most (fewer in practice due to overlap).

---

### Desktop -- Simple Count Limit

Keep a fixed number of recent snapshots. No time-based retention, no
manifests. Prioritizes low system impact.

```bash
# /etc/snapshot-manager.conf

SNAPSHOT_DIR="/snapshots"
MAX_SYSTEM_SNAPSHOTS=5
MAX_FULL_SNAPSHOTS=3

KEEP_DAILY=0
KEEP_WEEKLY=0
KEEP_MONTHLY=0

LOW_PRIORITY=true
GENERATE_MANIFEST=false
```

This keeps up to 5 system snapshots and 3 full snapshots. The oldest unlocked
snapshot is deleted when the limit is exceeded.

---

### Minimal -- External Disk, No Auto-Cleanup

Store snapshots on an external disk. No automatic cleanup -- the user manages
deletion manually.

```bash
# /etc/snapshot-manager.conf

SNAPSHOT_DIR="/mnt/backup-disk/snapshots"
MAX_SYSTEM_SNAPSHOTS=0
MAX_FULL_SNAPSHOTS=0

KEEP_DAILY=0
KEEP_WEEKLY=0
KEEP_MONTHLY=0

LOW_PRIORITY=false
GENERATE_MANIFEST=false
```

All limits are set to `0` (unlimited) and all `KEEP_*` policies are disabled.
Snapshots accumulate until the user explicitly deletes them. `LOW_PRIORITY` is
set to `false` to complete backups quickly on the external disk.
