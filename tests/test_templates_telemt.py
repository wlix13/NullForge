import tomllib
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from nullforge.templates import BLOCK_TRIM_ENV, get_template_path


def _render(template_name: str, **context: object) -> str:
    source = Path(get_template_path(template_name)).read_text(encoding="utf-8")
    # autoescape stays off (TOML/systemd, not HTML) to mirror pyinfra's renderer.
    env = Environment(  # noqa: S701
        undefined=StrictUndefined,
        keep_trailing_newline=True,
        **BLOCK_TRIM_ENV,
    )
    return env.from_string(source).render(**context)


def _config(**overrides: object) -> dict:
    context: dict[str, object] = {
        "FAST_MODE": True,
        "USE_MIDDLE_PROXY": False,
        "MODE_CLASSIC": False,
        "MODE_SECURE": False,
        "MODE_TLS": True,
        "MAX_CONNECTIONS": 16384,
        "CLIENT_HANDSHAKE": 30,
        "PORT": 443,
        "API_ENABLED": False,
        "IPV6": True,
        "PREFER": 6,
        "TLS_DOMAIN": "wlix13.dev",
        "UNKNOWN_SNI_ACTION": None,
        "USERS": {"personal": "bf777cca8384a074a671460d51e4e31f"},
        "ROUTE_VIA_WARP": True,
        "WARP_IFACE": "warp",
    }
    context.update(overrides)
    rendered = _render("telemt/telemt.toml.j2", **context)
    return tomllib.loads(rendered)


class TestConfigTemplate:
    def test_renders_valid_toml(self) -> None:
        data = _config()
        assert data["general"]["fast_mode"] is True
        assert data["general"]["use_middle_proxy"] is False
        assert data["general"]["log_level"] == "silent"

    def test_modes_are_booleans(self) -> None:
        data = _config(MODE_CLASSIC=True, MODE_SECURE=False, MODE_TLS=True)
        assert data["general"]["modes"] == {"classic": True, "secure": False, "tls": True}

    def test_users_rendered(self) -> None:
        users = {"personal": "bf777cca8384a074a671460d51e4e31f", "guests": "fdca0c33825b644bb4f5b9740cf6538c"}
        data = _config(USERS=users)
        assert data["access"]["users"] == users

    def test_unknown_sni_commented_when_absent(self) -> None:
        data = _config(UNKNOWN_SNI_ACTION=None)
        assert "unknown_sni_action" not in data["censorship"]
        assert data["censorship"]["tls_domain"] == "wlix13.dev"

    def test_unknown_sni_emitted_when_set(self) -> None:
        data = _config(UNKNOWN_SNI_ACTION="mask")
        assert data["censorship"]["unknown_sni_action"] == "mask"


def _service(**overrides: object) -> str:
    context: dict[str, object] = {
        "USER": "telemt",
        "GROUP": "telemt",
        "BINARY_PATH": "/usr/local/bin/telemt",
        "CONFIG_PATH": "/etc/telemt/telemt.toml",
        "PORT": 443,
        "WARP_ENABLED": True,
        "WARP_SERVICE": "cloudflare-warp",
        "WARP_IFACE": "warp",
        "TELEPROXY_SCRIPT": "/usr/local/sbin/teleproxy-warp.sh",
        "SYNFIX_ENABLED": True,
        "SYNFIX_SCRIPT": "/usr/local/sbin/telemt-synfix.sh",
    }
    context.update(overrides)
    return _render("systemd/telemt.service.j2", **context)


class TestServiceTemplate:
    def test_warp_wiring_present_when_enabled(self) -> None:
        unit = _service(WARP_ENABLED=True)
        assert "Requires=cloudflare-warp.service" in unit
        assert "BindsTo=cloudflare-warp.service" in unit
        assert "ExecStartPre=+/usr/local/sbin/teleproxy-warp.sh up telemt warp" in unit
        assert "ExecStopPost=+/usr/local/sbin/teleproxy-warp.sh down telemt warp" in unit

    def test_warp_wiring_absent_when_disabled(self) -> None:
        unit = _service(WARP_ENABLED=False)
        assert "cloudflare-warp.service" not in unit
        assert "teleproxy-warp.sh" not in unit

    def test_synfix_wiring_present_when_enabled(self) -> None:
        unit = _service(SYNFIX_ENABLED=True, PORT=8443)
        assert "ExecStartPre=+/usr/local/sbin/telemt-synfix.sh up 8443" in unit
        assert "ExecStopPost=+/usr/local/sbin/telemt-synfix.sh down 8443" in unit

    def test_synfix_wiring_absent_when_disabled(self) -> None:
        unit = _service(SYNFIX_ENABLED=False)
        assert "telemt-synfix.sh" not in unit
