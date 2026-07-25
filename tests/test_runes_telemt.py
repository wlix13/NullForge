from unittest.mock import patch

import pytest

from nullforge.molds import TelemtMold
from nullforge.runes import telemt
from nullforge.runes.telemt import _tls_domain_verdict, _vet_tls_domain
from nullforge.smithy.sni import GROUP_SECP256R1, GROUP_X25519, GROUP_X25519MLKEM768, KeyExchangeReport


VALID_SECRET = "bf777cca8384a074a671460d51e4e31f"
DOMAIN = "masking.example"


def _opts(*, pq_check: bool = True, mode_tls: bool = True, mode_secure: bool = False) -> TelemtMold:
    return TelemtMold(
        install=True,
        tls_domain=DOMAIN,
        users={"u": VALID_SECRET},
        pq_check=pq_check,
        mode_tls=mode_tls,
        mode_secure=mode_secure,
    )


def _report(
    *,
    error: str | None = None,
    supported: bool = False,
    fallback: int | None = None,
    supports_tls13: bool = True,
) -> KeyExchangeReport:
    return KeyExchangeReport(
        domain=DOMAIN,
        group=GROUP_X25519MLKEM768,
        error=error,
        supported=supported,
        fallback=fallback,
        supports_tls13=supports_tls13,
    )


class TestGating:
    def test_probes_when_fake_tls_is_configured(self) -> None:
        with patch.object(telemt, "inspect_group", return_value=_report(supported=True)) as probe:
            _vet_tls_domain(_opts())

        probe.assert_called_once_with(DOMAIN, GROUP_X25519MLKEM768)

    def test_pq_check_disabled_skips_the_probe(self) -> None:
        with patch.object(telemt, "inspect_group") as probe:
            _vet_tls_domain(_opts(pq_check=False))

        probe.assert_not_called()

    def test_no_probe_without_fake_tls(self) -> None:
        with patch.object(telemt, "inspect_group") as probe:
            _vet_tls_domain(_opts(mode_tls=False, mode_secure=True))

        probe.assert_not_called()

    def test_no_probe_without_a_domain(self) -> None:
        with patch.object(telemt, "inspect_group") as probe:
            _vet_tls_domain(TelemtMold())

        probe.assert_not_called()

    def test_supported_domain_is_reported_without_alarming(self) -> None:
        with patch.object(telemt, "inspect_group", return_value=_report(supported=True)):
            with patch.object(telemt, "LOG") as log:
                _vet_tls_domain(_opts())

        assert DOMAIN in log.info.call_args[0][0]
        log.warning.assert_not_called()

    @pytest.mark.parametrize(
        "report",
        [
            _report(fallback=GROUP_X25519),
            _report(fallback=GROUP_SECP256R1),
            _report(supports_tls13=False),
            _report(error="timed out"),
        ],
        ids=[
            "x25519-fallback",
            "other-fallback",
            "no-tls13",
            "inconclusive",
        ],
    )
    def test_anything_short_of_a_pass_warns(self, report: KeyExchangeReport) -> None:
        with patch.object(telemt, "inspect_group", return_value=report):
            with patch.object(telemt, "LOG") as log:
                _vet_tls_domain(_opts())

        assert DOMAIN in log.warning.call_args[0][0]


class TestVerdictWording:
    def test_inconclusive_probe_does_not_blame_the_domain(self) -> None:
        verdict = _tls_domain_verdict(DOMAIN, _report(error="timed out"))

        assert "could not be vetted" in verdict
        assert "timed out" in verdict
        assert "blocked" not in verdict
