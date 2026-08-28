from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from nullforge.molds import FeaturesMold, WarpMold
from nullforge.smithy.http import (
    CURL_ARGS,
    WARP_TRACE_URL,
    Egress,
    curl_args,
    curl_args_str,
    egress_for,
    fetch_github_keys,
    fetch_text,
    reachable_address,
    warp_interface,
)


URL = "https://github.com/o/r/releases/download/v1/tool.tar.gz"
PIN = "release-assets.githubusercontent.com:443:1.2.3.4"


class _FakeData:
    def __init__(self, features: FeaturesMold | None = None) -> None:
        if features is not None:
            self.features = features


def _make_host(features: FeaturesMold | None = None, facts: Callable[[str], object] = lambda c: "") -> MagicMock:
    host = MagicMock()
    host.name = "node"
    host.data = _FakeData(features)
    host.get_fact.side_effect = lambda fact, command: facts(command)
    return host


def _warp_features(iface: str = "warp") -> FeaturesMold:
    return FeaturesMold(warp=WarpMold(install=True, iface=iface))


def _facts(*, direct: bool = True, warp: bool = False, trace: str = "warp=on") -> Callable[[str], str]:
    def facts(command: str) -> str:
        if WARP_TRACE_URL in command:
            return trace
        if "-r 0-0" in command:
            return (
                "reachable" if ("--interface" in command and warp) or ("--interface" not in command and direct) else ""
            )
        raise AssertionError(f"unexpected fact: {command}")

    return facts


def _fact_commands(host: MagicMock) -> list[str]:
    return [call.args[1] for call in host.get_fact.call_args_list]


class TestEgress:
    def test_curl_args_render_only_what_is_set(self) -> None:
        assert Egress().curl_args() == {}
        assert Egress(interface="warp").curl_args() == {"--interface": "warp"}
        assert Egress(resolve=PIN).curl_args() == {"--resolve": PIN}
        assert Egress(interface="warp", resolve=PIN).curl_args() == {"--interface": "warp", "--resolve": PIN}


class TestWarpInterface:
    def test_none_when_warp_inactive(self) -> None:
        host = _make_host(FeaturesMold(), _facts())
        with patch("nullforge.smithy.http.host", host):
            assert warp_interface() is None
        host.get_fact.assert_not_called()

    def test_none_without_features_data(self) -> None:
        host = _make_host(None, _facts())
        with patch("nullforge.smithy.http.host", host):
            assert warp_interface() is None
        host.get_fact.assert_not_called()

    @pytest.mark.parametrize("trace", ["", "  \n"])
    def test_none_when_cloudflare_does_not_confirm_warp(self, trace: str) -> None:
        host = _make_host(_warp_features(), _facts(trace=trace))
        with patch("nullforge.smithy.http.host", host):
            assert warp_interface() is None

    @pytest.mark.parametrize("trace", ["warp=on", "warp=plus"])
    def test_iface_when_cloudflare_confirms_warp(self, trace: str) -> None:
        host = _make_host(_warp_features(iface="warp-x"), _facts(trace=trace))
        with patch("nullforge.smithy.http.host", host):
            assert warp_interface() == "warp-x"

        (probe,) = _fact_commands(host)
        assert probe.startswith("curl -sS --interface warp-x --connect-timeout 5 --max-time 10 ")
        assert WARP_TRACE_URL in probe
        assert probe.endswith("| grep -E '^warp=(on|plus)$' || true")

    def test_interface_is_shell_quoted(self) -> None:
        host = _make_host(_warp_features(iface="warp$x"), _facts())
        with patch("nullforge.smithy.http.host", host):
            warp_interface()
        assert "--interface 'warp$x' " in _fact_commands(host)[0]

    @pytest.mark.parametrize("trace", ["warp=on", ""])
    def test_cached_per_host(self, trace: str) -> None:
        host = _make_host(_warp_features(), _facts(trace=trace))
        with patch("nullforge.smithy.http.host", host):
            first = warp_interface()
            assert warp_interface() == first
        assert host.get_fact.call_count == 1


class TestEgressFor:
    def test_direct_when_default_route_answers(self) -> None:
        host = _make_host(_warp_features(), _facts(direct=True, warp=True))
        with patch("nullforge.smithy.http.host", host):
            assert egress_for(URL) == Egress()
        assert len(_fact_commands(host)) == 1

    def test_direct_probe_carries_the_pin(self) -> None:
        host = _make_host(FeaturesMold(), _facts(direct=True))
        with patch("nullforge.smithy.http.host", host):
            assert egress_for(URL, resolve=PIN) == Egress(resolve=PIN)
        (probe,) = _fact_commands(host)
        assert probe.startswith("curl -sS -o /dev/null -L -r 0-0 --connect-timeout 5 --max-time 15 --proto =https ")
        assert f"--resolve {PIN} {URL}" in probe
        assert probe.endswith(">/dev/null 2>&1 && echo reachable || true")

    def test_url_is_shell_quoted(self) -> None:
        host = _make_host(FeaturesMold(), _facts(direct=True))
        with patch("nullforge.smithy.http.host", host):
            egress_for("https://example.test/a?b=1&c=2")
        assert "'https://example.test/a?b=1&c=2'" in _fact_commands(host)[0]

    def test_falls_back_to_warp_when_direct_is_filtered(self) -> None:
        host = _make_host(_warp_features(), _facts(direct=False, warp=True))
        with patch("nullforge.smithy.http.host", host), patch("nullforge.smithy.http.LOG") as log:
            assert egress_for(URL, resolve=PIN) == Egress(interface="warp")

        direct, trace, warp = _fact_commands(host)
        assert "--resolve" in direct and "--interface" not in direct
        assert WARP_TRACE_URL in trace
        assert "--interface warp " in warp and "--resolve" not in warp
        log.info.assert_called_once()
        log.warning.assert_not_called()

    def test_stays_direct_when_warp_inactive(self) -> None:
        host = _make_host(FeaturesMold(), _facts(direct=False))
        with patch("nullforge.smithy.http.host", host), patch("nullforge.smithy.http.LOG") as log:
            assert egress_for(URL, resolve=PIN) == Egress(resolve=PIN)
        assert len(_fact_commands(host)) == 1
        assert log.warning.call_args.args[0].endswith("is unreachable directly")

    def test_stays_direct_when_warp_does_not_reach_either(self) -> None:
        host = _make_host(_warp_features(), _facts(direct=False, warp=False))
        with patch("nullforge.smithy.http.host", host), patch("nullforge.smithy.http.LOG") as log:
            assert egress_for(URL) == Egress()
        assert len(_fact_commands(host)) == 3
        assert log.warning.call_args.args[0].endswith("is unreachable directly and via WARP")

    def test_stays_direct_when_warp_interface_is_dead(self) -> None:
        host = _make_host(_warp_features(), _facts(direct=False, warp=True, trace=""))
        with patch("nullforge.smithy.http.host", host):
            assert egress_for(URL) == Egress()
        assert len(_fact_commands(host)) == 2

    def test_cached_per_url(self) -> None:
        host = _make_host(_warp_features(), _facts(direct=False, warp=True))
        with patch("nullforge.smithy.http.host", host):
            assert egress_for(URL) == Egress(interface="warp")
            assert egress_for(URL) == Egress(interface="warp")
            assert egress_for("https://example.test/other") == Egress(interface="warp")
        assert host.get_fact.call_count == 5


class TestCurlArgs:
    def test_plain_copy_on_direct_route(self) -> None:
        host = _make_host(FeaturesMold(), _facts(direct=True))
        with patch("nullforge.smithy.http.host", host):
            args = curl_args(URL)
        assert args == CURL_ARGS
        assert args is not CURL_ARGS

    def test_binds_interface_on_fallback(self) -> None:
        host = _make_host(_warp_features(iface="warp0"), _facts(direct=False, warp=True))
        with patch("nullforge.smithy.http.host", host):
            assert curl_args(URL) == {**CURL_ARGS, "--interface": "warp0"}
        assert "--interface" not in CURL_ARGS

    def test_str_renders_flags_and_binding(self) -> None:
        host = _make_host(_warp_features(iface="warp0"), _facts(direct=False, warp=True))
        with patch("nullforge.smithy.http.host", host):
            rendered = curl_args_str(URL)
        assert rendered.startswith("--compressed --fail --retry-connrefused --tlsv1.2 --retry 3 ")
        assert "--proto =https" in rendered
        assert rendered.endswith("--interface warp0")


def _pin_facts(reachable: str) -> Callable[[str], str]:
    def facts(command: str) -> str:
        if command.startswith("getent"):
            return "1.2.3.4\n5.6.7.8\n"
        return "reachable" if f":{reachable} " in command else ""

    return facts


class TestReachableAddress:
    def test_first_reachable_candidate_wins(self) -> None:
        host = _make_host(FeaturesMold(), _pin_facts("5.6.7.8"))
        with patch("nullforge.smithy.http.host", host):
            assert reachable_address("example.test") == "5.6.7.8"
            assert reachable_address("example.test") == "5.6.7.8"
        assert host.get_fact.call_count == 3

    def test_none_when_nothing_reachable(self) -> None:
        host = _make_host(FeaturesMold(), _pin_facts("9.9.9.9"))
        with patch("nullforge.smithy.http.host", host):
            assert reachable_address("example.test") is None

    def test_probe_pins_resolution(self) -> None:
        host = _make_host(FeaturesMold(), _pin_facts("1.2.3.4"))
        with patch("nullforge.smithy.http.host", host):
            reachable_address("example.test", port=8443)
        probe = _fact_commands(host)[1]
        assert probe.startswith("curl -sS -o /dev/null --connect-timeout 5 ")
        assert "--resolve example.test:8443:1.2.3.4 https://example.test/" in probe


class TestFetchText:
    def test_rejects_non_https_url(self) -> None:
        with pytest.raises(ValueError, match="Refusing non-HTTPS URL"):
            fetch_text("http://github.com/octocat.keys")


class TestFetchGithubKeys:
    def test_none_returns_empty(self) -> None:
        assert fetch_github_keys(None) == []

    def test_returns_lines(self) -> None:
        with patch(
            "nullforge.smithy.http.fetch_text",
            return_value="ssh-ed25519 AAA a\nssh-rsa BBB b\n",
        ):
            assert fetch_github_keys("octocat") == ["ssh-ed25519 AAA a", "ssh-rsa BBB b"]

    def test_fetch_failure_warns_and_returns_empty(self) -> None:
        with patch(
            "nullforge.smithy.http.fetch_text",
            side_effect=RuntimeError("404"),
        ):
            assert fetch_github_keys("bad") == []
