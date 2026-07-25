from nullforge.models.dns import DnsMode
from nullforge.models.users import Shell
from nullforge.molds import DnsMold, MonitoringMold, TelemtMold, UserMold, WarpMold
from nullforge.molds.defaults import BASE_FEATURES, BASE_SYSTEM
from nullforge.molds.monitoring import NezhaBackend
from nullforge.molds.utils import merge_features, merge_system


users = UserMold(
    manage=True,
    name="example",
    shell=Shell.ZSH,
)
"""User configuration preset
with user management enabled and the user "example".
with shell set to ZSH (default behavior).
"""

warp = WarpMold(
    install=True,
    iface="warp-example",
)
"""WARP configuration preset
setup Cloudflare WARP
with default MASQUE engine and interface "warp-example".
"""

dns = DnsMold(
    mode=DnsMode.BLOCKY,
)
"""DNS configuration preset
with DNS over HTTPS Blocky mode.
"""

monitoring = MonitoringMold(
    install=True,
    backend=NezhaBackend(
        server="agent.status.example.com:443",
        client_secret="REPLACE_WITH_NZ_CLIENT_SECRET",  # noqa: S106 - example placeholder
        dashboard_url="https://dash.example.com",
        api_token="REPLACE_WITH_DASHBOARD_PAT",  # noqa: S106 - example placeholder
    ),
)
"""Monitoring configuration preset
installing Nezha agent and renaming dashboard entry to host hostname.
The dashboard_url/api_token are used on control node for rename API call.
"""

telemt = TelemtMold(
    install=True,
    tls_domain="example.com",
    users={
        "example": "bf777cca8384a074a671460d51e4e31f",
    },
    route_via_warp=True,
    synfix=True,
)
"""Telemt MTProto proxy preset with Fake-TLS masking.
Telegram-bound egress is routed through WARP (enabled above) via per-uid policy routing,
and the MEKO SYN rate-limiting fix is applied.
"""

overrides = (
    users,
    warp,
    dns,
    monitoring,
    telemt,
)
"""Wrappers for the features to be merged with the base features."""

hosts = [
    (
        "203.0.113.10",
        {
            "system": merge_system(BASE_SYSTEM, {"hostname": "example-node1.local"}),
            "features": merge_features(BASE_FEATURES, *overrides),
        },
    ),
    (
        "203.0.113.20",
        {
            "system": merge_system(BASE_SYSTEM, {"hostname": "example-node2.local"}),
            "features": merge_features(BASE_FEATURES, *overrides),
        },
    ),
]
