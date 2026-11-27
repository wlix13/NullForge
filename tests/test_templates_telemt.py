import tomllib
from pathlib import Path

import pytest
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


def _render_config(**overrides: object) -> str:
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
        "ROUTE_VIA_WARP": False,
        "WARP_IFACE": "warp",
        "WEB_ENABLED": False,
        "WEB_PORT": 18080,
        "WEB_HOST": "",
        "WEB_BASE_PATH": "",
        "WEB_PUBLIC_ADDR": "",
        "WEB_CARRIER": "https",
        "WEB_USERS": [],
    }
    context.update(overrides)
    return _render("telemt/telemt.toml.j2", **context)


def _config(**overrides: object) -> dict:
    return tomllib.loads(_render_config(**overrides))


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

    def test_web_disabled_by_default(self) -> None:
        rendered = _render_config()
        assert "[web]" not in rendered
        assert 'transport = "web"' not in rendered

    def test_web_mode_renders_web_sections(self) -> None:
        data = _config(
            WEB_ENABLED=True,
            WEB_PORT=18080,
            WEB_HOST="pulsar.example.com",
            WEB_BASE_PATH="telegram/web",
            WEB_PUBLIC_ADDR="203.0.113.10:443",
            WEB_CARRIER="https",
            WEB_USERS=["personal", "guests"],
        )
        web = data["web"]
        assert web["enabled"] is True
        assert web["carrier"] == "https"
        vhost = web["vhosts"][0]
        assert vhost["host"] == "pulsar.example.com"
        assert vhost["public_addr"] == "203.0.113.10:443"
        assert vhost["decoy"] == {
            "mode": "static_directory",
            "directory": "/var/www/telemt-decoy",
            "index": "index.html",
        }
        profiles = vhost["profiles"]
        assert [p["user"] for p in profiles] == ["personal", "guests"]
        assert all(p["secret_mode"] == "dd" for p in profiles)
        assert all(
            p["max_sessions"] == 8 and p["max_streams"] == 512 and p["max_streams_per_session"] == 64 for p in profiles
        )
        listeners = data["server"]["listeners"]
        assert listeners[0]["transport"] == "web"
        assert listeners[0]["ip"] == "127.0.0.1"
        assert listeners[0]["port"] == 18080
        assert listeners[0]["web_client_ip_source"] == "x_forwarded_for"
        assert data["general"]["links"]["show"] == "*"

    @pytest.mark.parametrize("base_path,expect_present", [("telegram/web", True), ("", False)])
    def test_web_base_path_handling(self, base_path: str, expect_present: bool) -> None:
        data = _config(
            WEB_ENABLED=True,
            WEB_PORT=18080,
            WEB_HOST="pulsar.example.com",
            WEB_BASE_PATH=base_path,
            WEB_PUBLIC_ADDR="203.0.113.10:443",
            WEB_CARRIER="https",
            WEB_USERS=["personal"],
        )
        vhost = data["web"]["vhosts"][0]
        if expect_present:
            assert vhost["base_path"] == base_path
        else:
            assert "base_path" not in vhost


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
        "SYNFIX_TYPE": "v2",
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

    @pytest.mark.parametrize("synfix_type", ["v2", "v3", "v4"])
    def test_synfix_wiring_present_with_type(self, synfix_type: str) -> None:
        unit = _service(SYNFIX_ENABLED=True, SYNFIX_TYPE=synfix_type, PORT=8443)
        assert f"ExecStartPre=+/usr/local/sbin/telemt-synfix.sh up 8443 {synfix_type}" in unit
        assert f"ExecStopPost=+/usr/local/sbin/telemt-synfix.sh down 8443 {synfix_type}" in unit

    def test_synfix_wiring_absent_when_disabled(self) -> None:
        unit = _service(SYNFIX_ENABLED=False)
        assert "telemt-synfix.sh" not in unit


class TestCaddyTemplates:
    def test_caddyfile_renders_public_site_no_decoy(self) -> None:
        caddyfile = _render(
            "caddy/Caddyfile.j2",
            WEB_HOST="pulsar.example.com",
            WEB_PORT=18080,
        )
        assert "pulsar.example.com {" in caddyfile
        assert "reverse_proxy 127.0.0.1:18080" in caddyfile
        assert "header_up X-Forwarded-For {remote_host}" in caddyfile
        assert "http://127.0.0.1:" not in caddyfile
        assert "file_server" not in caddyfile

    def test_caddy_service_unit(self) -> None:
        unit = _render(
            "systemd/telemt-caddy.service.j2",
            CADDY_BIN="/usr/local/bin/caddy",
            CADDYFILE="/etc/caddy/Caddyfile",
        )
        assert "ExecStart=/usr/local/bin/caddy run --config /etc/caddy/Caddyfile --adapter caddyfile" in unit
        assert "StateDirectory=caddy" in unit
        assert "Environment=XDG_DATA_HOME=/var/lib/caddy" in unit
        assert "WantedBy=multi-user.target" in unit