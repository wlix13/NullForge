"""DNS configuration models."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, IPvAnyAddress, field_validator


class DnsProtocol(StrEnum):
    DOU = "dou"
    DOT = "dot"
    DOH = "doh"


class DnsMode(StrEnum):
    DOU = "dou"
    DOT_RESOLVED = "dot_resolved"
    BLOCKY = "blocky"
    NONE = "none"


class DnsProvider(StrEnum):
    CLOUDFLARE = "cloudflare"
    GOOGLE = "google"
    QUAD9 = "quad9"


class _DnsServerBase(BaseModel):
    """Base for a DNS server."""

    protocol: DnsProtocol


class DnsServerDoU(_DnsServerBase):
    protocol: Literal[DnsProtocol.DOU] = DnsProtocol.DOU
    host: IPvAnyAddress | str = Field(description="Resolver hostname or IP")
    port: int = Field(default=53, ge=1, le=65535, description="UDP port")


class DnsServerDoH(_DnsServerBase):
    protocol: Literal[DnsProtocol.DOH] = DnsProtocol.DOH
    url: str = Field(description="HTTPS endpoint for DNS over HTTPS (RFC 8484).")

    @field_validator("url")
    @classmethod
    def _require_https(cls, v: str) -> str:
        """Enforce HTTPS."""

        if not v.startswith("https://"):
            raise ValueError("DoH endpoint must use HTTPS")
        return v


class DnsServerDoT(_DnsServerBase):
    protocol: Literal[DnsProtocol.DOT] = DnsProtocol.DOT
    host: IPvAnyAddress | str = Field(description="Resolver hostname or IP")
    port: int = Field(default=853, ge=1, le=65535, description="TLS port")
    sni: str | None = Field(default=None, description="Optional SNI/hostname for TLS verification")


DnsServer = Annotated[
    DnsServerDoH | DnsServerDoT | DnsServerDoU,
    Field(discriminator="protocol"),
]


class DnsProviders:
    """DNS providers."""

    @staticmethod
    def _cloudflare_doh(ipv6: bool) -> list[DnsServer]:
        ups: list[DnsServer] = [
            DnsServerDoH(url="https://1.1.1.1/dns-query"),
            DnsServerDoH(url="https://1.0.0.1/dns-query"),
        ]
        if ipv6:
            ups.extend(
                [
                    DnsServerDoH(url="https://[2606:4700:4700::1111]/dns-query"),
                    DnsServerDoH(url="https://[2606:4700:4700::1001]/dns-query"),
                ]
            )
        return ups

    @staticmethod
    def _cloudflare_dot(ipv6: bool) -> list[DnsServer]:
        ups: list[DnsServer] = [
            DnsServerDoT(host="1.1.1.1", sni="cloudflare-dns.com"),
            DnsServerDoT(host="1.0.0.1", sni="cloudflare-dns.com"),
        ]
        if ipv6:
            ups.extend(
                [
                    DnsServerDoT(host="2606:4700:4700::1111", sni="cloudflare-dns.com"),
                    DnsServerDoT(host="2606:4700:4700::1001", sni="cloudflare-dns.com"),
                ]
            )
        return ups

    @staticmethod
    def _google_doh(ipv6: bool) -> list[DnsServer]:
        ups: list[DnsServer] = [
            DnsServerDoH(url="https://8.8.8.8/dns-query"),
            DnsServerDoH(url="https://8.8.4.4/dns-query"),
        ]
        if ipv6:
            ups.extend(
                [
                    DnsServerDoH(url="https://[2001:4860:4860::8888]/dns-query"),
                    DnsServerDoH(url="https://[2001:4860:4860::8844]/dns-query"),
                ]
            )
        return ups

    @staticmethod
    def _google_dot(ipv6: bool) -> list[DnsServer]:
        ups: list[DnsServer] = [
            DnsServerDoT(host="8.8.8.8", sni="dns.google"),
            DnsServerDoT(host="8.8.4.4", sni="dns.google"),
        ]
        if ipv6:
            ups.extend(
                [
                    DnsServerDoT(host="2001:4860:4860::8888", sni="dns.google"),
                    DnsServerDoT(host="2001:4860:4860::8844", sni="dns.google"),
                ]
            )
        return ups

    @staticmethod
    def _quad9_doh(ipv6: bool, ecs: bool) -> list[DnsServer]:
        if ecs:
            primary_ipv4 = "https://9.9.9.12/dns-query"
            secondary_ipv4 = "https://149.112.112.12/dns-query"
            primary_ipv6 = "https://[2620:fe::12]/dns-query"
            secondary_ipv6 = "https://[2620:fe::fe:12]/dns-query"
        else:
            primary_ipv4 = "https://9.9.9.10/dns-query"
            secondary_ipv4 = "https://149.112.112.10/dns-query"
            primary_ipv6 = "https://[2620:fe::10]/dns-query"
            secondary_ipv6 = "https://[2620:fe::fe:10]/dns-query"

        ups: list[DnsServer] = [
            DnsServerDoH(url=primary_ipv4),
            DnsServerDoH(url=secondary_ipv4),
        ]
        if ipv6:
            ups.extend(
                [
                    DnsServerDoH(url=primary_ipv6),
                    DnsServerDoH(url=secondary_ipv6),
                ]
            )
        return ups

    @staticmethod
    def _quad9_dot(ipv6: bool, ecs: bool) -> list[DnsServer]:
        if ecs:
            sni = "dns11.quad9.net"
            primary_ipv4 = "9.9.9.12"
            secondary_ipv4 = "149.112.112.12"
            primary_ipv6 = "2620:fe::12"
            secondary_ipv6 = "2620:fe::fe:12"
        else:
            sni = "dns10.quad9.net"
            primary_ipv4 = "9.9.9.10"
            secondary_ipv4 = "149.112.112.10"
            primary_ipv6 = "2620:fe::10"
            secondary_ipv6 = "2620:fe::fe:10"

        ups: list[DnsServer] = [
            DnsServerDoT(host=primary_ipv4, sni=sni),
            DnsServerDoT(host=secondary_ipv4, sni=sni),
        ]
        if ipv6:
            ups.extend(
                [
                    DnsServerDoT(host=primary_ipv6, sni=sni),
                    DnsServerDoT(host=secondary_ipv6, sni=sni),
                ]
            )
        return ups

    @staticmethod
    def get_upstreams(
        provider: DnsProvider,
        protocol: DnsProtocol,
        ipv6: bool,
        ecs: bool = False,
    ) -> list[DnsServer]:
        """Get upstream DNS servers for a provider and protocol."""

        if ecs and provider != DnsProvider.QUAD9:
            raise ValueError(f"ECS is supported only with the Quad9 provider, not {provider}")

        match provider:
            case DnsProvider.CLOUDFLARE:
                if protocol == DnsProtocol.DOH:
                    return DnsProviders._cloudflare_doh(ipv6)
                elif protocol == DnsProtocol.DOT:
                    return DnsProviders._cloudflare_dot(ipv6)
                else:
                    raise ValueError(f"Unsupported protocol {protocol} for Cloudflare")
            case DnsProvider.GOOGLE:
                if protocol == DnsProtocol.DOH:
                    return DnsProviders._google_doh(ipv6)
                elif protocol == DnsProtocol.DOT:
                    return DnsProviders._google_dot(ipv6)
                else:
                    raise ValueError(f"Unsupported protocol {protocol} for Google")
            case DnsProvider.QUAD9:
                if protocol == DnsProtocol.DOH:
                    return DnsProviders._quad9_doh(ipv6, ecs)
                elif protocol == DnsProtocol.DOT:
                    return DnsProviders._quad9_dot(ipv6, ecs)
                else:
                    raise ValueError(f"Unsupported protocol {protocol} for Quad9")
            case _:
                raise ValueError(f"Unknown provider: {provider}")


dns_providers = DnsProviders()
