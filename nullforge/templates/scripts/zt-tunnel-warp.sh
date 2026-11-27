#!/usr/bin/env bash

set -euo pipefail

cmd=${1:?up|down}
IFACE=${2:-warp}

log(){ logger -t zt-tunnel-warp -- "$*"; }

CIDRS="198.41.200.0/24 104.16.0.0/12"

case "$cmd" in
  up)
    for cidr in $CIDRS; do
      ip route replace "$cidr" dev "$IFACE"
      log "Added route for $cidr via $IFACE"
    done
    ;;
  down)
    for cidr in $CIDRS; do
      ip route del "$cidr" dev "$IFACE" 2>/dev/null || true
      log "Removed route for $cidr via $IFACE"
    done
    ;;
  *)
    log "Invalid command: $cmd"
    exit 1
esac
