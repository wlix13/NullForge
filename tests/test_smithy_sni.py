import struct
from unittest.mock import patch

import pytest

from nullforge.smithy import sni
from nullforge.smithy.sni import (
    CLASSICAL_GROUPS,
    GROUP_SECP256R1,
    GROUP_X25519,
    GROUP_X25519MLKEM768,
    KeyExchangeReport,
    group_name,
    inspect_group,
)


HRR_RANDOM = bytes.fromhex("cf21ad74e59a6111be1d8c021e65b891c2a211167abb8c5e079e09e2c8a8339c")
"""RFC 8446 sentinel marking a ServerHello as a HelloRetryRequest."""


def _server_hello(group: int | None, *, hrr: bool = True, version: bytes = b"\x03\x04") -> bytes:
    """Build a ServerHello/HelloRetryRequest record naming `group` in its key_share."""

    extensions = struct.pack(">HH", 0x002B, len(version)) + version
    if group is not None:
        # An HRR names the group alone; a real ServerHello follows it with a key_exchange.
        share = struct.pack(">H", group) if hrr else struct.pack(">HH", group, 32) + bytes(32)
        extensions += struct.pack(">HH", 0x0033, len(share)) + share

    body = (
        b"\x03\x03"
        + (HRR_RANDOM if hrr else bytes(32))
        + b"\x00"  # empty legacy_session_id_echo
        + b"\x13\x01"  # cipher_suite
        + b"\x00"  # compression
        + struct.pack(">H", len(extensions))
        + extensions
    )
    handshake = b"\x02" + len(body).to_bytes(3, "big") + body
    return b"\x16\x03\x03" + struct.pack(">H", len(handshake)) + handshake


def _alert(desc: int) -> bytes:
    return b"\x15\x03\x03\x00\x02" + bytes([2, desc])


class FakeSocket:
    """Socket stub that replays a canned server flight and records what was sent."""

    def __init__(self, response: bytes) -> None:
        self.response = response
        self.sent = b""
        self.pos = 0

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def recv(self, count: int) -> bytes:
        chunk = self.response[self.pos : self.pos + count]
        self.pos += len(chunk)
        return chunk

    def settimeout(self, timeout: float) -> None:
        pass

    def __enter__(self) -> "FakeSocket":
        return self

    def __exit__(self, *args: object) -> bool:
        return False


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    sni._cache.clear()


def _probe(domain: str, *responses: bytes) -> tuple[KeyExchangeReport, list[FakeSocket]]:
    """Probe for the PQ group against a scripted sequence of server responses."""

    sockets = [FakeSocket(r) for r in responses]
    with patch.object(sni.socket, "create_connection", side_effect=list(sockets)):
        return inspect_group(domain, GROUP_X25519MLKEM768), sockets


class TestGroupName:
    def test_unknown_group_falls_back_to_hex(self) -> None:
        assert group_name(0x1234) == "0x1234"

    def test_none(self) -> None:
        assert group_name(None) == "none"


class TestClientHello:
    def test_offers_requested_groups_and_empty_key_share(self) -> None:
        hello = sni._client_hello("example.com", (GROUP_X25519MLKEM768,))

        assert hello.startswith(b"\x16\x03\x01")
        # supported_groups carrying exactly the probed group...
        assert struct.pack(">HHH H", 0x000A, 4, 2, GROUP_X25519MLKEM768) in hello
        # ...and a key_share whose client_shares vector is empty, which is what
        # makes the server name its own choice instead of using ours.
        assert struct.pack(">HHH", 0x0033, 2, 0) in hello

    def test_key_share_group_sends_a_32_byte_guess(self) -> None:
        hello = sni._client_hello("example.com", CLASSICAL_GROUPS, key_share_group=GROUP_X25519)

        # key_share ext (38 body bytes) -> client_shares vector (36) -> x25519 entry (32).
        assert struct.pack(">HHHHH", 0x0033, 38, 36, GROUP_X25519, 32) in hello

    def test_includes_sni(self) -> None:
        hello = sni._client_hello("example.com", (GROUP_X25519,))
        assert b"example.com" in hello

    def test_encodes_idna_domain(self) -> None:
        hello = sni._client_hello("münchen.de", (GROUP_X25519,))
        assert b"xn--mnchen-3ya.de" in hello


class TestInspectGroup:
    def test_group_supported(self) -> None:
        report, sockets = _probe("good.example", _server_hello(GROUP_X25519MLKEM768))

        assert report.conclusive
        assert report.supported is True
        assert report.fallback is None
        # A positive answer must not cost a second round trip.
        assert len(sockets) == 1

    def test_refusal_reports_the_fallback_group(self) -> None:
        report, _ = _probe("bad.example", _alert(40), _server_hello(GROUP_X25519))

        assert report.conclusive
        assert report.supported is False
        assert report.fallback == GROUP_X25519

    def test_server_taking_the_x25519_guess_reports_x25519(self) -> None:
        report, sockets = _probe("msft.example", _alert(40), _server_hello(GROUP_X25519, hrr=False))

        assert report.fallback == GROUP_X25519
        # The fallback probe must guess, or it would have measured server preference.
        assert struct.pack(">HH", GROUP_X25519, 32) in sockets[1].sent

    def test_fallback_probe_does_not_reoffer_the_probed_group(self) -> None:
        report, sockets = _probe("bad.example", _alert(40), _server_hello(GROUP_SECP256R1))

        assert report.fallback == GROUP_SECP256R1
        assert struct.pack(">H", GROUP_X25519MLKEM768) not in sockets[1].sent

    def test_full_server_hello_is_accepted(self) -> None:
        report, _ = _probe("good.example", _server_hello(GROUP_X25519MLKEM768, hrr=False))
        assert report.supported is True

    def test_insufficient_security_alert_counts_as_refusal(self) -> None:
        report, _ = _probe("bad.example", _alert(71), _server_hello(GROUP_X25519))

        assert report.supported is False
        assert report.fallback == GROUP_X25519

    def test_tls12_only_peer_is_conclusive_not_an_error(self) -> None:
        report, sockets = _probe("old.example", _server_hello(GROUP_X25519, version=b"\x03\x03"))

        assert report.conclusive
        assert report.supports_tls13 is False
        assert report.supported is False
        # Settled by the first probe; there is nothing a fallback could add.
        assert len(sockets) == 1

    def test_protocol_version_alert_is_conclusive(self) -> None:
        report, _ = _probe("old.example", _alert(70))

        assert report.conclusive
        assert report.supports_tls13 is False

    def test_unexpected_alert_is_inconclusive(self) -> None:
        report, _ = _probe("weird.example", _alert(80))

        assert report.conclusive is False
        assert "alert 80" in str(report.error)

    def test_unreachable_host_is_inconclusive(self) -> None:
        with patch.object(sni.socket, "create_connection", side_effect=OSError("timed out")):
            report = inspect_group("nope.example", GROUP_X25519MLKEM768)

        assert report.conclusive is False
        assert "timed out" in str(report.error)

    def test_failed_fallback_probe_is_inconclusive(self) -> None:
        with patch.object(
            sni.socket,
            "create_connection",
            side_effect=[FakeSocket(_alert(40)), OSError("reset")],
        ):
            report = inspect_group("half.example", GROUP_X25519MLKEM768)

        assert report.conclusive is False
        assert "fallback probe failed" in str(report.error)

    def test_truncated_response_is_inconclusive(self) -> None:
        report, _ = _probe("cut.example", b"\x16\x03\x03\x00\x40")
        assert report.conclusive is False

    def test_never_raises_on_unexpected_errors(self) -> None:
        with patch.object(sni, "_inspect", side_effect=RuntimeError("boom")):
            report = inspect_group("boom.example", GROUP_X25519MLKEM768)

        assert report.conclusive is False
        assert "boom" in str(report.error)


class TestCaching:
    def test_domain_is_probed_once_per_group(self) -> None:
        response = _server_hello(GROUP_X25519MLKEM768)
        with patch.object(
            sni.socket,
            "create_connection",
            side_effect=[FakeSocket(response), FakeSocket(response)],
        ) as connect:
            first = inspect_group("cached.example", GROUP_X25519MLKEM768)
            second = inspect_group("cached.example", GROUP_X25519MLKEM768)

        assert first == second
        assert connect.call_count == 1
