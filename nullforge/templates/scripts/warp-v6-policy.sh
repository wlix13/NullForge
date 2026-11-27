#!/usr/bin/env bash
#
# IPv6 policy routing for Cloudflare WARP (usque nativetun).
#

set -euo pipefail

cmd=${1:?up|down}
IFACE=${2:-warp}
CFG=${3:-/etc/usque/config.json}

# If omitted, values are derived from IFACE.
EXPLICIT_TID=${4:-}
EXPLICIT_PRIO=${5:-}

# This lets multiple independent warp interfacescoexist
_slot() {
  printf '%s' "$1" | cksum | awk '{print $1 % 100}'
}

SLOT=$(_slot "$IFACE")

if [ -n "$EXPLICIT_TID" ]; then
  TID=$EXPLICIT_TID
else
  TID=$((200 + SLOT))  # 200-299: safe custom table ID range
fi

# Unique table name per interface
TABLE="warp_$(printf '%s' "$IFACE" | tr -c '[:alnum:]_.-' '_')"

if [ -n "$EXPLICIT_PRIO" ]; then
  PRIO=$EXPLICIT_PRIO
else
  PRIO=$((20000 + SLOT * 10))  # 20000-20990
fi

PRIO_OIF=$((PRIO + 5))
WAIT_SECS=8

log(){ logger -t warp-policy -- "$*"; }

get_warp6(){
  ip -6 -o addr show dev "$IFACE" scope global 2>/dev/null \
    | awk '{print $4}' | head -n1 | cut -d/ -f1
}

get_ep6(){
  jq -r '.endpoint_v6 // empty' "$CFG" 2>/dev/null || true
}

ensure_table(){
  grep -qE "^[[:space:]]*$TID[[:space:]]+$TABLE$" /etc/iproute2/rt_tables \
    || echo "$TID $TABLE" >> /etc/iproute2/rt_tables
}

wait_for_warp6(){
  local i=0
  while [ $i -lt "$WAIT_SECS" ]; do
    local a
    a=$(get_warp6 || true)
    if [ -n "$a" ]; then echo "$a"; return 0; fi
    sleep 1; i=$((i+1))
  done
  return 1
}

case "$cmd" in
  up)
    ensure_table

    if ! WARP6=$(wait_for_warp6); then
      log "No IPv6 on $IFACE after ${WAIT_SECS}s; leaving without rules"
      exit 0
    fi

    EP6=$(get_ep6)
    if [ -n "$EP6" ]; then
      # Ensure the WARP endpoint remains reachable outside the tunnel while
      # our default-via-warp is installed. Only possible if host has IPv6.
      route_info=$(ip -6 route get "${EP6}" 2>/dev/null || true)
      GW6=$(echo "$route_info" | awk '{for(i=1;i<NF;i++) if($i=="via"){print $(i+1); exit}}')
      DEV=$(echo "$route_info" | awk '{for(i=1;i<NF;i++) if($i=="dev"){print $(i+1); exit}}')
      if [ -n "${GW6}" ] && [ -n "${DEV}" ]; then
        ip -6 route replace "${EP6}/128" via "$GW6" dev "$DEV" onlink
      fi
    fi

    ip -6 route replace default dev "$IFACE" table "$TABLE"

    ip -6 rule del pref "$PRIO" 2>/dev/null || true
    ip -6 rule add pref "$PRIO" from "${WARP6}/128" lookup "$TABLE"
    ip -6 rule del pref "$PRIO_OIF" 2>/dev/null || true
    ip -6 rule add pref "$PRIO_OIF" oif "$IFACE" lookup "$TABLE"

    log "IPv6 policy up: src=${WARP6}/128 pref=$PRIO, oif=$IFACE pref=$PRIO_OIF table=$TABLE"
    ;;

  down)
    ip -6 rule del pref "$PRIO" 2>/dev/null || true
    ip -6 rule del pref "$PRIO_OIF" 2>/dev/null || true

    EP6=$(get_ep6 || true)
    if [ -n "${EP6:-}" ]; then
      ip -6 route del "${EP6}/128" 2>/dev/null || true
    fi

    ip -6 route flush table "$TABLE" 2>/dev/null || true

    log "IPv6 policy down: table=$TABLE prefs=$PRIO,$PRIO_OIF cleaned"
    ;;

  *)
    echo "usage: $0 {up|down} [iface] [config] [tid] [prio]" >&2
    echo "  tid/prio: optional explicit table id and rule priority base (advanced)" >&2
    exit 1
    ;;
esac
