#!/usr/bin/env bash
#
# Per-uid policy routing that steers a service user's Telegram-bound traffic
# through the Cloudflare WARP interface, leaving all other egress untouched.
#
# Usage: teleproxy-warp.sh {up|down} [svc_user] [iface] [table] [tid] [prio]
#
# Routing is scoped to the service uid and to Telegram's published CIDRs, so the
# proxy reaches Telegram over WARP while clients still connect to it directly.
# IPv4 fails closed for the service user when WARP has no v4 address; IPv6 is
# optional and skipped entirely when absent.
#

set -euo pipefail

cmd=${1:?up|down}
SVC_USER=${2:-telemt}         # daemon's systemd User=
IFACE=${3:-warp}              # WARP interface (usque -n <iface>)
TABLE=${4:-tpwarp}            # dedicated routing table, separate from WARP's own
TID=${5:-124}
PRIO=${6:-11900}              # rule priority (below the WARP policy band, above main)
WAIT_SECS=15

CIDR_URLS=(
  "https://core.telegram.org/resources/cidr.txt"
)

# Embedded fallback (core.telegram.org/resources/cidr.txt, verified 2026-05)
FB_V4="91.108.56.0/22 91.108.4.0/22 91.108.8.0/22 91.108.16.0/22 91.108.12.0/22 149.154.160.0/20 91.105.192.0/23 91.108.20.0/22 185.76.151.0/24"
FB_V6="2001:b28:f23d::/48 2001:b28:f23f::/48 2001:67c:4e8::/48 2001:b28:f23c::/48 2a0a:f280::/32"

V4=""
V6=""

log() { logger -t telemt-warp -- "$*"; }

ensure_table() {
  grep -qE "^[[:space:]]*$TID[[:space:]]+$TABLE$" /etc/iproute2/rt_tables \
    || echo "$TID $TABLE" >> /etc/iproute2/rt_tables
}

get_warp6() { ip -6 -o addr show dev "$IFACE" scope global 2>/dev/null | awk '{print $4}' | head -n1 | cut -d/ -f1; }
get_warp4() { ip -4 -o addr show dev "$IFACE" scope global 2>/dev/null | awk '{print $4}' | head -n1 | cut -d/ -f1; }

wait_for_warp6() {
  local i=0 a
  while [ $i -lt "$WAIT_SECS" ]; do
    a=$(get_warp6 || true); [ -n "$a" ] && { echo "$a"; return 0; }
    sleep 1; i=$((i+1))
  done
  return 1
}

fetch_cidrs() {   # tries all CIDR_URLS; merges + deduplicates; falls back to embedded list
  local raw url new_v4 new_v6
  for url in "${CIDR_URLS[@]}"; do
    raw=$(curl --interface "$IFACE" --connect-timeout 3 --max-time 8 -fsSL "$url" 2>/dev/null || true)
    if [ -n "$raw" ]; then
      new_v4=$(echo "$raw" | tr ' ' '\n' | grep -E '^[0-9]+\.' | tr '\n' ' ' || true)
      new_v6=$(echo "$raw" | tr ' ' '\n' | grep -E ':'          | tr '\n' ' ' || true)
      V4=$(printf '%s %s' "$V4" "$new_v4" | tr ' ' '\n' | sort -u | awk 'NF' | tr '\n' ' ')
      V6=$(printf '%s %s' "$V6" "$new_v6" | tr ' ' '\n' | sort -u | awk 'NF' | tr '\n' ' ')
      log "fetched CIDRs from $url"
    else
      log "cidr fetch failed from $url (expected on a filtered uplink); skipping"
    fi
  done
  [ -n "${V4:-}" ] || V4="$FB_V4"
  [ -n "${V6:-}" ] || V6="$FB_V6"
}

del_rules() {
  while ip    rule del pref "$PRIO" 2>/dev/null; do :; done
  while ip -6 rule del pref "$PRIO" 2>/dev/null; do :; done
}

case "$cmd" in
  up)
    UID_N=$(id -u "$SVC_USER" 2>/dev/null) && [ -n "$UID_N" ] || { log "user $SVC_USER not found"; exit 1; }
    ensure_table

    # IPv6 is optional: non-fatal if absent; routes/rules skipped entirely when missing.
    WARP6=$(wait_for_warp6 || true)
    [ -n "$WARP6" ] || log "no IPv6 on $IFACE after ${WAIT_SECS}s; IPv6 routing skipped"

    del_rules
    ip -6 route flush table "$TABLE" 2>/dev/null || true
    ip -4 route flush table "$TABLE" 2>/dev/null || true

    if [ -n "$WARP6" ]; then
      ip -6 route replace default     dev "$IFACE" src "$WARP6" metric 100  table "$TABLE"
      ip -6 route replace unreachable default                   metric 1024 table "$TABLE"
    fi

    WARP4=$(get_warp4 || true)
    if [ -n "$WARP4" ]; then
      ip -4 route replace default     dev "$IFACE" src "$WARP4" metric 100  table "$TABLE"
      log "IPv4 egress via WARP src=$WARP4"
    else
      log "no IPv4 on $IFACE; IPv4-to-Telegram from $SVC_USER fails closed"
    fi
    ip -4 route replace unreachable default metric 1024 table "$TABLE"

    fetch_cidrs
    for p in $V4; do
      ip    rule add pref "$PRIO" to "$p" uidrange "${UID_N}-${UID_N}" lookup "$TABLE" || log "v4 rule add failed for $p"
    done
    if [ -n "$WARP6" ]; then
      for p in $V6; do
        ip -6 rule add pref "$PRIO" to "$p" uidrange "${UID_N}-${UID_N}" lookup "$TABLE" || log "v6 rule add failed for $p"
      done
    fi

    v6_count=0; [ -n "$WARP6" ] && v6_count=$(echo $V6 | wc -w) || true
    log "up: uid=$UID_N v6src=${WARP6:-none} table=$TABLE pref=$PRIO ($(echo $V4 | wc -w)v4 ${v6_count}v6)"
    ;;
  down)
    del_rules
    ip -6 route flush table "$TABLE" 2>/dev/null || true
    ip -4 route flush table "$TABLE" 2>/dev/null || true
    log "down: table=$TABLE pref=$PRIO cleaned"
    ;;
  *)
    echo "usage: $0 {up|down} [svc_user] [iface] [table] [tid] [prio]" >&2
    exit 1
    ;;
esac
