-- Zapret2 MTProto fix (MEKO v4), run by nfqws2 as --lua-desync=lets_resend.
-- Server-side desync: clamp the server TCP window so the client fragments its
-- ClientHello, then split the first client data packet into 3 parts and resend
-- the middle one with a bad checksum (disorder). iOS SYN+ACKs are fingerprinted
-- by TCP options and bypassed untouched via fwmark 0x40000.
-- Window clamp: 1400 on SYN+ACK, 10 on empty ACKs; split length: 400.

function lets_resend(ctx, desync)
    -- iOS fingerprint bypass: pass through with fwmark, no manipulation
    if bitand(desync.dis.tcp.th_flags, TH_SYN + TH_ACK) == TH_SYN then
        -- newer nfqws2 strips the trailing EOL option, older keeps it;
        -- count eight options with a kind-0 last one as seven without it
        local o = desync.dis.tcp.options
        local n = #o
        if n == 8 and o[8].kind == 0 then n = 7 end
        if desync.dis.tcp.th_win == 65535 and n == 7 and
           o[1].kind == 2 and o[2].kind == 1 and o[3].kind == 3 and
           o[4].kind == 1 and o[5].kind == 1 and o[6].kind == 8 and o[7].kind == 4 then
            instance_cutoff(ctx, nil)
            desync.arg.fwmark = 0x40000
            rawsend_dissect_segmented(desync)
            return VERDICT_DROP
        end
    end

    -- SYN+ACK: remember ack, clamp window so the client fragments ClientHello
    if bitand(desync.dis.tcp.th_flags, TH_SYN + TH_ACK) == (TH_SYN + TH_ACK) then
        desync.track.lua_state["ack0"] = desync.dis.tcp.th_ack
        desync.dis.tcp.th_win = 1400
        return VERDICT_MODIFY
    end

    -- empty server ACKs: keep the window clamped, release after 1400 client bytes
    if direction_check(desync) and bitand(desync.dis.tcp.th_flags, TH_SYN + TH_ACK) == (TH_ACK) then
        if desync.track and desync.dis.tcp.th_ack - desync.track.lua_state["ack0"] >= 1400 then
            instance_cutoff(ctx, true)
            desync.arg.fwmark = 0x40000
            rawsend_dissect_segmented(desync)
            return VERDICT_DROP
        end
        desync.dis.tcp.th_win = 10
        return VERDICT_MODIFY
    end

    -- only the first client data packet
    if #desync.dis.payload == 0 or desync.track == nil or desync.track.pos.client.tcp.rseq ~= 1 then
        return VERDICT_PASS
    end

    -- split into 3 parts, send first + third, then the middle one with badsum
    local len = 400
    local first  = string.sub(desync.dis.payload, 1, len)
    local second = string.sub(desync.dis.payload, len + 1, 2 * len)
    local third  = string.sub(desync.dis.payload, 2 * len + 1)
    rawsend_payload_segmented(desync, first)
    rawsend_payload_segmented(desync, third, 2 * len)
    desync.arg["badsum"] = true
    rawsend_payload_segmented(desync, second, len)
    instance_cutoff(ctx, false)
    return VERDICT_DROP
end
