#!/usr/bin/env bash
# Host-level operational monitoring for a JUVAl development/validation node
# (ADR-027). Read-only: never modifies system state, never requires sudo.
# Checks disk, RAM, load, temperature, failed systemd units, git-based
# source backup status, and journal log growth. Prints PASS/WARN/FAIL per
# check and exits 0 (all pass), 1 (warnings present) or 2 (a failure
# present), so it can be wired into a systemd timer or run interactively.
set -uo pipefail

STATUS=0
note_warn() { STATUS=$((STATUS < 1 ? 1 : STATUS)); }
note_fail() { STATUS=2; }

pass() { printf '[PASS] %-22s %s\n' "$1" "$2"; }
warn() { printf '[WARN] %-22s %s\n' "$1" "$2"; note_warn; }
fail() { printf '[FAIL] %-22s %s\n' "$1" "$2"; note_fail; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- disk ---
disk_pct=$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')
if [ "$disk_pct" -ge 90 ]; then
  fail "disk./" "${disk_pct}% used (>=90%)"
elif [ "$disk_pct" -ge 80 ]; then
  warn "disk./" "${disk_pct}% used (>=80%)"
else
  pass "disk./" "${disk_pct}% used"
fi

# --- RAM ---
mem_avail_pct=$(awk '/MemAvailable/{a=$2} /MemTotal/{t=$2} END{printf "%d", (a/t)*100}' /proc/meminfo)
if [ "$mem_avail_pct" -lt 5 ]; then
  fail "memory" "${mem_avail_pct}% available (<5%)"
elif [ "$mem_avail_pct" -lt 10 ]; then
  warn "memory" "${mem_avail_pct}% available (<10%)"
else
  pass "memory" "${mem_avail_pct}% available"
fi

# --- load average vs. core count ---
cores=$(nproc)
load1=$(awk '{print $1}' /proc/loadavg)
load_ratio=$(awk -v l="$load1" -v c="$cores" 'BEGIN{printf "%.2f", l/c}')
over=$(awk -v r="$load_ratio" 'BEGIN{print (r>=2.0)?1:0}')
high=$(awk -v r="$load_ratio" 'BEGIN{print (r>=1.0)?1:0}')
if [ "$over" -eq 1 ]; then
  fail "load" "1-min load ${load1} / ${cores} cores = ${load_ratio}x (>=2.0x)"
elif [ "$high" -eq 1 ]; then
  warn "load" "1-min load ${load1} / ${cores} cores = ${load_ratio}x (>=1.0x)"
else
  pass "load" "1-min load ${load1} / ${cores} cores = ${load_ratio}x"
fi

# --- CPU temperature (best-effort; not every host exposes thermal_zone0) ---
temp_file="/sys/class/thermal/thermal_zone0/temp"
if [ -r "$temp_file" ]; then
  temp_milli=$(cat "$temp_file")
  temp_c=$((temp_milli / 1000))
  if [ "$temp_c" -ge 90 ]; then
    fail "temperature" "${temp_c}C (>=90C)"
  elif [ "$temp_c" -ge 75 ]; then
    warn "temperature" "${temp_c}C (>=75C)"
  else
    pass "temperature" "${temp_c}C"
  fi
else
  warn "temperature" "no thermal_zone0 sensor exposed on this host"
fi

# --- failed systemd units (system-level query never needs root to read) ---
failed_system=$(systemctl --failed --no-legend 2>/dev/null | wc -l)
failed_user=$(systemctl --user --failed --no-legend 2>/dev/null | wc -l)
failed_total=$((failed_system + failed_user))
if [ "$failed_total" -gt 0 ]; then
  fail "systemd.failed" "${failed_system} system + ${failed_user} user unit(s) failed"
else
  pass "systemd.failed" "0 failed units (system + user)"
fi

# --- git-based source backup status (ADR-027: GitHub is the recovery path) ---
if git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  dirty=$(git -C "$REPO_DIR" status --porcelain | wc -l)
  ahead=$(git -C "$REPO_DIR" rev-list --count '@{u}..HEAD' 2>/dev/null || echo "?")
  behind=$(git -C "$REPO_DIR" rev-list --count 'HEAD..@{u}' 2>/dev/null || echo "?")
  if [ "$dirty" -gt 0 ]; then
    warn "git.backup" "${dirty} uncommitted change(s) in working tree -- not yet recoverable from GitHub"
  elif [ "$ahead" != "0" ] && [ "$ahead" != "?" ]; then
    warn "git.backup" "${ahead} commit(s) ahead of upstream -- not yet pushed"
  else
    pass "git.backup" "working tree clean, in sync with upstream (behind: ${behind})"
  fi
else
  warn "git.backup" "${REPO_DIR} is not a git working tree"
fi

# --- journal log growth (informational; journald self-limits by default) ---
if command -v journalctl >/dev/null 2>&1; then
  journal_size=$(journalctl --disk-usage 2>/dev/null | grep -oE '[0-9.]+[MG]' | tail -1)
  pass "log.growth" "journal disk usage: ${journal_size:-unknown}"
else
  warn "log.growth" "journalctl not available"
fi

echo
case "$STATUS" in
  0) echo "RESULT: ALL CHECKS PASS" ;;
  1) echo "RESULT: PASS WITH WARNINGS" ;;
  2) echo "RESULT: FAIL -- at least one check requires attention" ;;
esac

exit "$STATUS"
