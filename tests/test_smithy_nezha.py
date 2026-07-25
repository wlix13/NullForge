import uuid
from typing import Any

from nullforge.smithy.monitoring.nezha import agent as nezha


class TestAgentUuidForHostname:
    def test_is_valid_uuid(self) -> None:
        value = nezha.agent_uuid_for_hostname("nl120.aphelion")
        assert str(uuid.UUID(value)) == value

    def test_namespace_changes_result(self) -> None:
        default = nezha.agent_uuid_for_hostname("host")
        other = nezha.agent_uuid_for_hostname("host", namespace=str(uuid.uuid4()))
        assert default != other

    def test_namespace_accepts_uuid_object(self) -> None:
        ns = uuid.uuid4()
        one = nezha.agent_uuid_for_hostname("host", namespace=ns)
        other = nezha.agent_uuid_for_hostname("host", namespace=str(ns))
        assert one == other


class TestBuildNezhaInstallCommand:
    def _build(self, **overrides: object) -> str:
        kwargs: dict[str, Any] = {
            "install_url": "https://example.com/install.sh",
            "curl_args": "--retry 3",
            "server": "agent.status.example.com:443",
            "tls": True,
            "client_secret": "s3cr3t",
            "agent_uuid": "39bdee03-5773-eb88-97d9-f1ebd46bf3f1",
        }
        kwargs.update(overrides)
        return nezha.build_nezha_install_command(**kwargs)

    def test_tls_flag(self) -> None:
        assert "NZ_TLS=true" in self._build(tls=True)
        assert "NZ_TLS=false" in self._build(tls=False)

    def test_shell_metacharacters_are_quoted(self) -> None:
        cmd = self._build(client_secret="a b; rm -rf /")
        # the dangerous value must be single-quoted, not bare
        assert "a b; rm -rf /" not in cmd.replace("'a b; rm -rf /'", "")
