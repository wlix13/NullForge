#!/usr/bin/env bash
#
# MEKO-style SYN rate-limiting fix for the telemt MTProto port.
# https://github.com/Mekotofeuka/MTPROTO_FIX_By_MEKO
#
# Non-iOS clients are throttled per source IP (default 54 SYN/minute, burst 1);
# excess connection attempts get a TCP reset so dead sockets are reaped in
# minutes. Small low-TTL SYNs (the iOS fingerprint) bypass limit for fast reconnects.
# Under-limit and iOS traffic RETURN to the normal INPUT path, so this coexists
# with UFW/firewalld (the port must still be  allowed there).
# Best-effort: failures are logged, never fatal to startup.
#

set -uo pipefail

cmd=${1:?up|down}
PORT=${2:-443}
RATE=${3:-54/minute}
BURST=${4:-1}
IOS_TTL=${5:-65}

CHAIN="MTPR_SYNFIX"
HL_NAME="mtpr${PORT}"

log() { logger -t telemt-synfix -- "$*"; }

up_family() {
  # $1 = iptables|ip6tables ; remaining args = iOS-bypass match (may be empty)
  local ipt=$1
  shift

  "$ipt" -N "$CHAIN" 2>/dev/null || "$ipt" -F "$CHAIN" || return 1

  if [ "$#" -gt 0 ]; then
    "$ipt" -A "$CHAIN" -p tcp --dport "$PORT" --syn "$@" -j RETURN || return 1
  fi

  "$ipt" -A "$CHAIN" -p tcp --dport "$PORT" --syn \
    -m hashlimit \
    --hashlimit-name "$HL_NAME" \
    --hashlimit-mode srcip \
    --hashlimit-upto "$RATE" \
    --hashlimit-burst "$BURST" \
    --hashlimit-htable-expire 60000 \
    --hashlimit-htable-size 32768 \
    -j RETURN || return 1

  "$ipt" -A "$CHAIN" -p tcp --dport "$PORT" --syn -j REJECT --reject-with tcp-reset || return 1

  # Ensure exactly one jump from INPUT, evaluated before other allow rules.
  while "$ipt" -D INPUT -p tcp --dport "$PORT" --syn -j "$CHAIN" 2>/dev/null; do :; done
  "$ipt" -I INPUT 1 -p tcp --dport "$PORT" --syn -j "$CHAIN" || return 1
}

down_family() {
  local ipt=$1
  while "$ipt" -D INPUT -p tcp --dport "$PORT" --syn -j "$CHAIN" 2>/dev/null; do :; done
  "$ipt" -F "$CHAIN" 2>/dev/null || true
  "$ipt" -X "$CHAIN" 2>/dev/null || true
}

case "$cmd" in
  up)
    if up_family iptables -m length --length 64 -m ttl --ttl-lt "$IOS_TTL"; then
      log "up: ipv4 chain=$CHAIN port=$PORT rate=$RATE burst=$BURST ios_ttl<$IOS_TTL"
    else
      log "up: ipv4 synfix not applied (missing iptables modules?)"
    fi

    if command -v ip6tables >/dev/null 2>&1; then
      if up_family ip6tables -m hl --hl-lt "$IOS_TTL"; then
        log "up: ipv6 chain=$CHAIN port=$PORT rate=$RATE burst=$BURST"
      else
        log "up: ipv6 synfix not applied"
      fi
    fi
    ;;
  down)
    down_family iptables
    command -v ip6tables >/dev/null 2>&1 && down_family ip6tables
    log "down: chain=$CHAIN port=$PORT cleaned"
    ;;
  *)
    echo "usage: $0 {up|down} [port] [rate] [burst] [ios_ttl]" >&2
    exit 1
    ;;
esac

exit 0
