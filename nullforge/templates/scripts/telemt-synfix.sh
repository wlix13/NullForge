#!/usr/bin/env bash
#
# MEKO-style MTProto fix for telemt port.
# https://github.com/Mekotofeuka/MTPROTO_FIX_By_MEKO
#
# Variants (arg 3, default v2):
#   v2  iOS bypass by TTL+Length (IPv4) / hop-limit (IPv6), then per-source-IP
#       hashlimit on SYNs. Excess SYNs get TCP reset so dead sockets are reaped
#       in minutes.
#   v3  same limit, but iOS matched by full TCP fingerprint via u32 in
#       mangle/PREROUTING (mark 0x400, nftables @nh fallback when xt_u32 missing)
#       instead of TTL+Length, which misclassifies clients behind
#       load balancers.
#   v4  zapret2 nfqws2 server-side desync instead of any SYN limit: clamps
#       server TCP window and disorders/badsums first client data packet.
#       Needs nfqws2 + lua libs under /opt/telemt-synfix and nftables.
# v2/v3 rules RETURN to normal INPUT path, so they coexist with UFW/firewalld
# (port must still be allowed there). v4 mutually exclusive with v2/v3:
# each `up` tears down other variants' leftovers, `down` removes everything.
# Best-effort: failures logged, never fatal to startup.

set -uo pipefail

cmd=${1:?up|down}
PORT=${2:-443}
TYPE=${3:-v2}
RATE=${4:-54/minute}
BURST=${5:-1}
IOS_TTL=${6:-65}

CHAIN="MTPR_SYNFIX"
HL_NAME="mtpr${PORT}"
MARK="0x400"

# iOS TCP fingerprint as u32 offsets in bytes from IP header start.
# IPv4 header is 20 bytes, IPv6 is 40, so v6 offsets are v4 ones + 8.
U32_V4="32 & 0x000FFFFF = 0x0002FFFF && 40 & 0xFF000000 = 0x02000000 && 44 & 0xFFFF0000 = 0x01030000 && 48 & 0xFFFFFF00 = 0x01010800 && 60 & 0xFFFFFFFF = 0x04020000"
U32_V6="40 & 0x000FFFFF = 0x0002FFFF && 48 & 0xFF000000 = 0x02000000 && 52 & 0xFFFF0000 = 0x01030000 && 56 & 0xFFFFFF00 = 0x01010800 && 68 & 0xFFFFFFFF = 0x04020000"
NFT_U32_TABLE="mtpr_synfix_u32"

ZAPRET2_DIR="/opt/telemt-synfix"
NFQWS2_BIN="${ZAPRET2_DIR}/bin/nfqws2"
NFQWS2_LUA_DIR="${ZAPRET2_DIR}/lua"
NFQWS2_CONF="${ZAPRET2_DIR}/etc/nfqws2-mtproto.conf"
NFQWS2_LOG="/var/log/telemt-synfix-nfqws2.log"
NFQWS2_PID="/run/telemt-synfix-nfqws2.pid"
NFT_ZAPRET2_TABLE="mtpr_zapret2"
ZAPRET2_QNUM="200"
ZAPRET2_FWMARK="0x40000000"
ZAPRET2_CT_MARK="0x00040000"

log() { logger -t telemt-synfix -- "$*"; }

# -- v2/v3 teardown: chain jump, chain, mangle marks, nft u32 fallback --
synlimiter_down_family() {
  local ipt=$1
  while "$ipt" -D INPUT -p tcp --dport "$PORT" --syn -j "$CHAIN" 2>/dev/null; do :; done
  "$ipt" -F "$CHAIN" 2>/dev/null || true
  "$ipt" -X "$CHAIN" 2>/dev/null || true
  while "$ipt" -t mangle -D PREROUTING -p tcp --dport "$PORT" -m u32 --u32 "$U32_V4" -j MARK --set-mark "$MARK" 2>/dev/null; do :; done
  while "$ipt" -t mangle -D PREROUTING -p tcp --dport "$PORT" -m u32 --u32 "$U32_V6" -j MARK --set-mark "$MARK" 2>/dev/null; do :; done
}

synlimiter_down() {
  synlimiter_down_family iptables
  command -v ip6tables >/dev/null 2>&1 && synlimiter_down_family ip6tables
  command -v nft >/dev/null 2>&1 && nft delete table inet "$NFT_U32_TABLE" 2>/dev/null || true
}

# -- v4 teardown: nfqws2 daemon + nft queue table --
zapret2_down() {
  if [ -f "$NFQWS2_PID" ]; then
    local pid
    pid=$(cat "$NFQWS2_PID" 2>/dev/null || true)
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
    rm -f "$NFQWS2_PID"
  fi
  pkill -f "$NFQWS2_BIN" 2>/dev/null || true
  command -v nft >/dev/null 2>&1 && nft delete table ip "$NFT_ZAPRET2_TABLE" 2>/dev/null || true
}

# -- v3: mark iOS packets in mangle/PREROUTING; prints "mark" or "fallback" --
mark_apply() {
  local ipt=$1 filter=$2
  while "$ipt" -t mangle -C PREROUTING -p tcp --dport "$PORT" -m u32 --u32 "$filter" -j MARK --set-mark "$MARK" 2>/dev/null; do
    "$ipt" -t mangle -D PREROUTING -p tcp --dport "$PORT" -m u32 --u32 "$filter" -j MARK --set-mark "$MARK" 2>/dev/null || break
  done
  if "$ipt" -t mangle -A PREROUTING -p tcp --dport "$PORT" -m u32 --u32 "$filter" -j MARK --set-mark "$MARK" 2>/dev/null; then
    echo mark
  else
    echo fallback
  fi
}

# -- v3 fallback when xt_u32 missing: same offsets in bits via nft @nh (IPv4) --
nft_u32_fallback() {
  command -v nft >/dev/null 2>&1 || return 1
  nft delete table inet "$NFT_U32_TABLE" 2>/dev/null || true
  nft add table inet "$NFT_U32_TABLE" || return 1
  nft add chain inet "$NFT_U32_TABLE" pre '{ type filter hook prerouting priority mangle; policy accept; }' || return 1
  nft add rule inet "$NFT_U32_TABLE" pre meta nfproto ipv4 tcp dport "$PORT" \
    '@nh,256,32 & 0x000FFFFF == 0x0002FFFF' \
    '@nh,320,32 & 0xFF000000 == 0x02000000' \
    '@nh,352,32 & 0xFFFF0000 == 0x01030000' \
    '@nh,384,32 & 0xFFFFFF00 == 0x01010800' \
    '@nh,480,32 & 0xFFFFFFFF == 0x04020000' \
    meta mark set "$MARK"
}

# -- v2/v3: build chain and jump to it from INPUT position 1 --
# $1=iptables|ip6tables $2=mode(v2|v3); remaining args = iOS-bypass match (may be empty)
chain_up_family() {
  local ipt=$1 mode=$2
  shift 2

  "$ipt" -N "$CHAIN" 2>/dev/null || "$ipt" -F "$CHAIN" || return 1

  if [ "$mode" = "v3" ]; then
    "$ipt" -A "$CHAIN" -p tcp --dport "$PORT" --syn -m mark --mark "$MARK" -j RETURN || return 1
  fi

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

  while "$ipt" -D INPUT -p tcp --dport "$PORT" --syn -j "$CHAIN" 2>/dev/null; do :; done
  "$ipt" -I INPUT 1 -p tcp --dport "$PORT" --syn -j "$CHAIN" || return 1
}

synfix_up() {
  local mode=$1
  synlimiter_down
  zapret2_down

  if [ "$mode" = "v3" ]; then
    local m4
    m4=$(mark_apply iptables "$U32_V4")
    if [ "$m4" = "mark" ]; then
      chain_up_family iptables v3 \
        && log "up: ipv4 v3 chain=$CHAIN port=$PORT rate=$RATE burst=$BURST ios=u32-mark" \
        || log "up: ipv4 v3 chain not applied"
    elif nft_u32_fallback; then
      chain_up_family iptables v3 \
        && log "up: ipv4 v3 chain=$CHAIN port=$PORT rate=$RATE burst=$BURST ios=nft-nh (xt_u32 missing)" \
        || log "up: ipv4 v3 chain not applied"
    else
      chain_up_family iptables v2 -m length --length 64 -m ttl --ttl-lt "$IOS_TTL" \
        && log "up: ipv4 v3 degraded to ttl/length bypass (no xt_u32, no nft) chain=$CHAIN port=$PORT" \
        || log "up: ipv4 synfix not applied"
    fi

    if command -v ip6tables >/dev/null 2>&1; then
      local m6
      m6=$(mark_apply ip6tables "$U32_V6")
      if [ "$m6" = "mark" ]; then
        chain_up_family ip6tables v3 \
          && log "up: ipv6 v3 chain=$CHAIN port=$PORT rate=$RATE burst=$BURST ios=u32-mark" \
          || log "up: ipv6 v3 chain not applied"
      else
        chain_up_family ip6tables v2 -m hl --hl-lt "$IOS_TTL" \
          && log "up: ipv6 v3 degraded to hop-limit bypass (no xt_u32) chain=$CHAIN port=$PORT" \
          || log "up: ipv6 synfix not applied"
      fi
    fi
    return 0
  fi

  if chain_up_family iptables v2 -m length --length 64 -m ttl --ttl-lt "$IOS_TTL"; then
    log "up: ipv4 chain=$CHAIN port=$PORT rate=$RATE burst=$BURST ios_ttl<$IOS_TTL"
  else
    log "up: ipv4 synfix not applied (missing iptables modules?)"
  fi

  if command -v ip6tables >/dev/null 2>&1; then
    if chain_up_family ip6tables v2 -m hl --hl-lt "$IOS_TTL"; then
      log "up: ipv6 chain=$CHAIN port=$PORT rate=$RATE burst=$BURST"
    else
      log "up: ipv6 synfix not applied"
    fi
  fi
}

# -- v4: zapret2 nfqws2 desync, packets queued via nftables --
zapret2_up() {
  synlimiter_down

  if [ ! -x "$NFQWS2_BIN" ]; then
    log "up: v4 requested but $NFQWS2_BIN is missing"
    return 1
  fi
  if ! command -v nft >/dev/null 2>&1; then
    log "up: v4 needs nftables"
    return 1
  fi

  mkdir -p "$(dirname "$NFQWS2_CONF")"
  cat > "$NFQWS2_CONF" <<EOF
--qnum ${ZAPRET2_QNUM}
--fwmark=${ZAPRET2_FWMARK}
--server
--lua-init=@${NFQWS2_LUA_DIR}/zapret-lib.lua
--lua-init=@${NFQWS2_LUA_DIR}/zapret-antidpi.lua
--lua-init=@${NFQWS2_LUA_DIR}/mtproto.lua
--filter-tcp=${PORT}
--out-range=a
--in-range=a
--payload-disable=all
--lua-desync=lets_resend
--new
EOF

  local combined
  printf -v combined '0x%08x' $(( ZAPRET2_FWMARK | ZAPRET2_CT_MARK ))

  nft delete table ip "$NFT_ZAPRET2_TABLE" 2>/dev/null || true
  nft add table ip "$NFT_ZAPRET2_TABLE" || return 1
  nft "add chain ip $NFT_ZAPRET2_TABLE predefrag { type filter hook output priority -401; policy accept; }" || return 1
  nft "add rule ip $NFT_ZAPRET2_TABLE predefrag meta mark $combined counter accept" || return 1
  nft "add rule ip $NFT_ZAPRET2_TABLE predefrag meta mark and $ZAPRET2_FWMARK != 0x00000000 counter notrack" || return 1
  nft "add chain ip $NFT_ZAPRET2_TABLE output { type route hook output priority mangle; policy accept; }" || return 1
  nft "add rule ip $NFT_ZAPRET2_TABLE output meta mark and $combined == $combined ct mark set $ZAPRET2_CT_MARK counter accept" || return 1
  nft "add chain ip $NFT_ZAPRET2_TABLE postrouting { type filter hook postrouting priority srcnat + 1; policy accept; }" || return 1
  nft "add rule ip $NFT_ZAPRET2_TABLE postrouting ct mark $ZAPRET2_CT_MARK counter accept" || return 1
  nft "add rule ip $NFT_ZAPRET2_TABLE postrouting meta mark and $ZAPRET2_FWMARK == 0x00000000 tcp sport $PORT counter queue num $ZAPRET2_QNUM bypass" || return 1
  nft "add chain ip $NFT_ZAPRET2_TABLE prerouting { type filter hook prerouting priority mangle; policy accept; }" || return 1
  nft "add rule ip $NFT_ZAPRET2_TABLE prerouting ct state invalid counter drop" || return 1
  nft "add rule ip $NFT_ZAPRET2_TABLE prerouting ct mark $ZAPRET2_CT_MARK counter accept" || return 1
  nft "add rule ip $NFT_ZAPRET2_TABLE prerouting meta mark and $ZAPRET2_FWMARK == 0x00000000 tcp dport $PORT counter queue num $ZAPRET2_QNUM bypass" || return 1

  if [ -f "$NFQWS2_PID" ] && kill -0 "$(cat "$NFQWS2_PID")" 2>/dev/null; then
    log "up: v4 nfqws2 already running (pid $(cat "$NFQWS2_PID")) port=$PORT qnum=$ZAPRET2_QNUM"
  else
    setsid "$NFQWS2_BIN" @"$NFQWS2_CONF" >>"$NFQWS2_LOG" 2>&1 &
    echo $! > "$NFQWS2_PID"
    sleep 1
    if kill -0 "$(cat "$NFQWS2_PID")" 2>/dev/null; then
      log "up: v4 zapret2 nfqws2 started port=$PORT qnum=$ZAPRET2_QNUM table=$NFT_ZAPRET2_TABLE"
    else
      log "up: v4 nfqws2 failed to start, see $NFQWS2_LOG"
    fi
  fi
}

case "$cmd" in
  up)
    case "$TYPE" in
      v2) synfix_up v2 ;;
      v3) synfix_up v3 ;;
      v4) zapret2_up ;;
      *)
        echo "usage: $0 {up|down} [port] [v2|v3|v4] [rate] [burst] [ios_ttl]" >&2
        exit 1
        ;;
    esac
    ;;
  down)
    synlimiter_down
    zapret2_down
    log "down: chain=$CHAIN port=$PORT type=$TYPE cleaned"
    ;;
  *)
    echo "usage: $0 {up|down} [port] [v2|v3|v4] [rate] [burst] [ios_ttl]" >&2
    exit 1
    ;;
esac

exit 0
