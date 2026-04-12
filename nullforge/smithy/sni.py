"""TLS key-exchange probing for SNI masking domains.

Anything that hides behind someone else's domain - Fake-TLS, REALITY - is only as
convincing as the domain it borrows, and what matters is what a real client actually
negotiates with it: whether a given key-exchange group is on offer at all, and which
group is used when it is not.

The probe speaks TLS directly rather than shelling out to ``openssl s_client -groups
...``, which for post-quantum groups would require OpenSSL 3.5+ on the control node.
Offering a group and reading back the server's choice needs no implementation of that
group's math on our side, so this works on any control node and is testable offline.
No handshake is ever completed: the server names its choice in its first flight, so the
probe reads that and drops the connection.
"""

import os
import socket
import struct
import threading
from collections.abc import Sequence
from dataclasses import dataclass


TLS_PORT = 443
"""Port a masking domain is probed on; these protocols only ever impersonate HTTPS."""

PROBE_TIMEOUT = 10
"""Seconds to wait for connect and for the server's first flight."""

GROUP_X25519 = 0x001D
GROUP_SECP256R1 = 0x0017
GROUP_SECP384R1 = 0x0018
GROUP_X448 = 0x001E
GROUP_SECP521R1 = 0x0019
GROUP_X25519MLKEM768 = 0x11EC

GROUP_NAMES = {
    GROUP_X25519: "X25519",
    GROUP_SECP256R1: "secp256r1",
    GROUP_SECP384R1: "secp384r1",
    GROUP_X448: "x448",
    GROUP_SECP521R1: "secp521r1",
    GROUP_X25519MLKEM768: "X25519MLKEM768",
}
"""IANA TLS supported-group names, for rendering a report."""

CLASSICAL_GROUPS = (GROUP_X25519, GROUP_SECP256R1, GROUP_SECP384R1, GROUP_X448, GROUP_SECP521R1)
"""What a client with no post-quantum support offers, in the usual browser order."""

_KEY_EXCHANGE_SIZES = {GROUP_X25519: 32}
"""Public-key sizes for groups we can guess a key_share for."""

_CIPHER_SUITES = (0x1301, 0x1302, 0x1303)
"""TLS 1.3 suites; a server must accept one of these to be worth probing."""

_SIG_ALGS = (0x0403, 0x0503, 0x0603, 0x0804, 0x0805, 0x0806, 0x0401, 0x0501, 0x0601)
"""Servers pick a certificate from these, so omitting them draws spurious alerts."""

_EXT_SERVER_NAME = 0x0000
_EXT_SUPPORTED_GROUPS = 0x000A
_EXT_SIG_ALGS = 0x000D
_EXT_SUPPORTED_VERSIONS = 0x002B
_EXT_KEY_SHARE = 0x0033

_REC_ALERT = 0x15
_REC_HANDSHAKE = 0x16
_HS_SERVER_HELLO = 0x02

_ALERT_HANDSHAKE_FAILURE = 40
_ALERT_PROTOCOL_VERSION = 70
_ALERT_INSUFFICIENT_SECURITY = 71


def group_name(group: int | None) -> str:
    """Render a group code for humans, falling back to its hex code."""

    if group is None:
        return "none"
    return GROUP_NAMES.get(group, f"0x{group:04x}")


@dataclass(frozen=True)
class KeyExchangeReport:
    """What `domain` negotiates for the probed `group`, and for a client without it.

    When `error` is set the probe reached no conclusion and no other field carries
    information.
    """

    domain: str
    group: int
    error: str | None = None
    supported: bool = False
    """Whether `domain` negotiates `group`."""

    fallback: int | None = None
    """Group a client that cannot offer `group` negotiates instead.

    None when `supported` is true (no reason to ask), or when the domain turned out to
    negotiate nothing at all.
    """

    supports_tls13: bool = True
    """False only when the peer refuses TLS 1.3 outright, which rules out any TLS 1.3 group."""

    @property
    def conclusive(self) -> bool:
        """Whether the probe learned anything; check this before reading other fields."""

        return self.error is None


class SniProbeError(Exception):
    """The peer could not be probed, or answered with something that is not TLS."""


class NoTlsThirteen(SniProbeError):
    """The peer refuses TLS 1.3, so no TLS 1.3 key-exchange group is reachable on it."""


_cache: dict[tuple[str, int, int], KeyExchangeReport] = {}
_cache_lock = threading.Lock()


def inspect_group(
    domain: str,
    group: int,
    *,
    port: int = TLS_PORT,
    timeout: int = PROBE_TIMEOUT,
) -> KeyExchangeReport:
    """Report whether `domain` negotiates `group`, and what it falls back to if not.

    Never raises: a probe that reaches no conclusion comes back with `error` set, so
    callers vetting a domain cannot be broken by a network blip. Results are cached per
    (domain, port, group) so a domain shared by several hosts is probed once per run.
    """

    key = (domain, port, group)
    with _cache_lock:
        cached = _cache.get(key)
    if cached is not None:
        return cached

    try:
        report = _inspect(domain, group, port, timeout)
    except Exception as e:
        report = KeyExchangeReport(domain=domain, group=group, error=f"probe failed: {e!r}")

    with _cache_lock:
        _cache.setdefault(key, report)
    return report


def _inspect(domain: str, group: int, port: int, timeout: int) -> KeyExchangeReport:
    """Probe for `group`, then probe the classical fallback only if `group` is refused."""

    try:
        selected = _negotiated_group(domain, port, (group,), timeout)
    except NoTlsThirteen:
        # Conclusive rather than inconclusive: no TLS 1.3 means no TLS 1.3 group.
        return KeyExchangeReport(domain=domain, group=group, supports_tls13=False, supported=False)
    except SniProbeError as e:
        return KeyExchangeReport(domain=domain, group=group, error=str(e))

    if selected == group:
        return KeyExchangeReport(domain=domain, group=group, supported=True)

    # The server refused the only group we offered. Ask again as a real client would, to
    # learn what it actually falls back to. This probe *does* guess a key_share, because
    # servers accept a usable guess rather than pay for a retry - an empty key_share
    # would report the server's own preference instead, which is not what a client gets.
    offer = tuple(g for g in CLASSICAL_GROUPS if g != group)
    try:
        fallback = _negotiated_group(domain, port, offer, timeout, key_share_group=GROUP_X25519)
    except SniProbeError as e:
        detail = f"{group_name(group)} refused, fallback probe failed: {e}"
        return KeyExchangeReport(domain=domain, group=group, error=detail)

    return KeyExchangeReport(domain=domain, group=group, supported=False, fallback=fallback)


def _negotiated_group(
    domain: str,
    port: int,
    groups: Sequence[int],
    timeout: int,
    *,
    key_share_group: int | None = None,
) -> int | None:
    """Return the group the server picks from `groups`, or None if it refuses them all.

    Raises SniProbeError when the peer cannot be reached or does not speak TLS 1.3.
    """

    hello = _client_hello(domain, groups, key_share_group=key_share_group)
    try:
        with socket.create_connection((domain, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(hello)
            return _read_selected_group(sock)
    except SniProbeError:
        raise
    except OSError as e:
        raise SniProbeError(f"connection to {domain}:{port} failed: {e}") from e


def _read_selected_group(sock: socket.socket) -> int | None:
    """Parse the server's first record and return its chosen group.

    The group is named in the key_share of either a HelloRetryRequest (when we sent no
    guess, RFC 8446 4.1.4) or a plain ServerHello (when the server took our guess), so
    it is readable without completing - or even being able to complete - a handshake.
    """

    header = _read_exactly(sock, 5)
    rec_type, _, length = struct.unpack(">BHH", header)
    payload = _read_exactly(sock, length)

    if rec_type == _REC_ALERT:
        desc = payload[1] if len(payload) > 1 else 0
        if desc in (_ALERT_HANDSHAKE_FAILURE, _ALERT_INSUFFICIENT_SECURITY):
            return None  # "none of the groups you offered"
        if desc == _ALERT_PROTOCOL_VERSION:
            raise NoTlsThirteen("server rejected TLS 1.3 (alert protocol_version)")
        raise SniProbeError(f"server sent TLS alert {desc}")
    if rec_type != _REC_HANDSHAKE:
        raise SniProbeError(f"expected a handshake record, got type 0x{rec_type:02x}")
    if not payload or payload[0] != _HS_SERVER_HELLO:
        raise SniProbeError("server did not answer with a ServerHello")

    body = payload[4 : 4 + int.from_bytes(payload[1:4], "big")]
    return _selected_group_from_server_hello(body)


def _selected_group_from_server_hello(body: bytes) -> int | None:
    """Pull key_share's group out of a ServerHello / HelloRetryRequest body."""

    try:
        pos = 2  # legacy_version
        pos += 32  # random; HRR-vs-ServerHello does not change where the group is read from
        pos += 1 + body[pos]  # legacy_session_id_echo
        pos += 2  # cipher_suite
        pos += 1  # legacy_compression_method
        ext_len = int.from_bytes(body[pos : pos + 2], "big")
        pos += 2
        extensions = body[pos : pos + ext_len]
    except IndexError as e:
        raise SniProbeError("malformed ServerHello") from e

    parsed = _parse_extensions(extensions)

    if parsed.get(_EXT_SUPPORTED_VERSIONS) != b"\x03\x04":
        # A TLS 1.2 ServerHello: same conclusion as alert 70, just stated politely.
        raise NoTlsThirteen("server negotiated a pre-TLS 1.3 version")

    key_share = parsed.get(_EXT_KEY_SHARE)
    if key_share is None or len(key_share) < 2:
        # A real ServerHello without key_share means PSK-only; a HelloRetryRequest
        # always carries one, so either way we learned nothing about groups.
        raise SniProbeError("ServerHello carried no key_share")

    return int.from_bytes(key_share[:2], "big")


def _parse_extensions(raw: bytes) -> dict[int, bytes]:
    """Walk a TLS extension block into {type: body}."""

    extensions: dict[int, bytes] = {}
    pos = 0
    while pos + 4 <= len(raw):
        kind, size = struct.unpack(">HH", raw[pos : pos + 4])
        pos += 4
        if pos + size > len(raw):
            raise SniProbeError("truncated TLS extension")
        extensions[kind] = raw[pos : pos + size]
        pos += size
    return extensions


def _read_exactly(sock: socket.socket, count: int) -> bytes:
    """Read exactly `count` bytes, or raise SniProbeError."""

    chunks: list[bytes] = []
    remaining = count
    while remaining > 0:
        try:
            chunk = sock.recv(remaining)
        except OSError as e:
            raise SniProbeError(f"read failed: {e}") from e
        if not chunk:
            raise SniProbeError("peer closed the connection mid-response")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _client_hello(domain: str, groups: Sequence[int], *, key_share_group: int | None = None) -> bytes:
    """Build a TLS 1.3 ClientHello offering `groups`, optionally guessing a key_share.

    With no `key_share_group` the client_shares vector is left empty, which makes the
    server name its own choice in a HelloRetryRequest - the only way to ask about a
    group whose share we cannot generate, such as X25519MLKEM768.
    """

    host = domain.encode("idna")
    sni = b"\x00" + struct.pack(">H", len(host)) + host

    extensions = b"".join(
        (
            _extension(_EXT_SERVER_NAME, struct.pack(">H", len(sni)) + sni),
            _extension(_EXT_SUPPORTED_GROUPS, _u16_vector(groups)),
            _extension(_EXT_SIG_ALGS, _u16_vector(_SIG_ALGS)),
            _extension(_EXT_SUPPORTED_VERSIONS, b"\x02\x03\x04"),
            _extension(_EXT_KEY_SHARE, _client_shares(key_share_group)),
        )
    )

    body = b"".join(
        (
            b"\x03\x03",
            os.urandom(32),
            b"\x20" + os.urandom(32),  # legacy_session_id, non-empty for middlebox compat
            _u16_vector(_CIPHER_SUITES),
            b"\x01\x00",  # legacy_compression_methods: null
            struct.pack(">H", len(extensions)) + extensions,
        )
    )

    handshake = b"\x01" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x01" + struct.pack(">H", len(handshake)) + handshake


def _client_shares(group: int | None) -> bytes:
    """Encode the key_share body: an empty vector, or one junk share for `group`.

    The share is random rather than a real keypair. Any 32 bytes is a well-formed X25519
    public key, so the server completes its side and reveals the negotiated group in the
    ServerHello; we never read far enough for the bogus shared secret to matter, and the
    connection is dropped immediately afterwards.
    """

    if group is None:
        return b"\x00\x00"

    size = _KEY_EXCHANGE_SIZES[group]
    entry = struct.pack(">HH", group, size) + os.urandom(size)
    return struct.pack(">H", len(entry)) + entry


def _extension(kind: int, body: bytes) -> bytes:
    return struct.pack(">HH", kind, len(body)) + body


def _u16_vector(values: Sequence[int]) -> bytes:
    """Encode `values` as a TLS vector of u16s prefixed with its byte length."""

    return struct.pack(">H", 2 * len(values)) + b"".join(struct.pack(">H", v) for v in values)
