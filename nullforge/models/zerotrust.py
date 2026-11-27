"""Zero Trust Tunnel configuration models."""

from enum import StrEnum


class ZeroTrustTunnelProtocol(StrEnum):
    HTTP2 = "http2"
    QUIC = "quic"
    AUTO = "auto"
