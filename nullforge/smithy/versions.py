"""Versions utilities for NullForge."""

import io

from pyinfra.context import host as _ctx_host
from pyinfra.facts.files import File, FileContents
from pyinfra.facts.server import Command
from pyinfra.operations import files

from nullforge.smithy.arch import arch_id
from nullforge.smithy.http import CURL_ARGS, pin_host_args


DEFAULT_VERSIONS = {
    "wgcf": "2.2.31",
    "usque": "4.2.1",
    "doggo": "1.1.7",
    "nvim": "v0.12.4",
    "tmux": "3.7b",
    "curl": "8.21.0",
    "eza": "v0.23.5",
    "cloudflared": "2026.7.2",
    "blocky": "v0.33.0",
    "direnv": "v2.37.1",
    "telemt": "3.4.23",
    "nerd_fonts": "v3.4.0",
}
"""Version pins (override per-host via inventory if needed)."""

RELEASE_ASSET_HOST = "release-assets.githubusercontent.com"
"""Host GitHub redirects `_release_url()` downloads to, and so the one serving the bytes."""

VERSION_COMMANDS: dict[str, str | None] = {
    "wgcf": None,  # wgcf has no version output; tracked via marker file
    "usque": "{bin} version",
    "doggo": "{bin} --version",
    "nvim": "{bin} --version",
    "tmux": "{bin} -V",
    "curl": "{bin} --version",
    "eza": "{bin} --version",
    "cloudflared": "{bin} --version",
    "blocky": "{bin} version",
    "direnv": "{bin} version",
    "telemt": "{bin} --version",
}
"""How each pinned tool reports its installed version (None = tracked via marker file)."""

VERSION_MARKER_DIR = "/var/lib/nullforge/versions"
"""Marker files recording installed versions of tools that cannot report their own."""

STATIC_URLS = {
    "starship_install": "https://starship.rs/install.sh",
    "docker_install": "https://get.docker.com",
    "xray_install": "https://github.com/XTLS/Xray-install/raw/main/install-release.sh",
    "nezha_agent_install": "https://raw.githubusercontent.com/nezhahq/scripts/main/agent/install.sh",
    "atuin_install": "https://setup.atuin.sh",
    "zoxide_install": "https://raw.githubusercontent.com/ajeetdsouza/zoxide/main/install.sh",
}
"""Static endpoints."""

ZSH_PLUGINS: dict[str, str] = {
    "zsh-autosuggestions": "https://github.com/zsh-users/zsh-autosuggestions",
    "zsh-syntax-highlighting": "https://github.com/zsh-users/zsh-syntax-highlighting",
    "ohmyzsh-full-autoupdate": "https://github.com/Pilaton/OhMyZsh-full-autoupdate",
}
"""Oh-my-zsh plugins to install (name → git URL)."""

GPG_KEYS = {
    "haproxy": "https://haproxy.debian.net/haproxy-archive-keyring.gpg",
    "gvisor": "https://gvisor.dev/archive.key",
}
"""GPG keys."""

KEYRING_DIR = "/etc/apt/keyrings"
"""Keyring directory."""


class Versions:
    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        if overrides is None:
            try:
                overrides = _ctx_host.data.get("versions", {}) or {}
            except AttributeError:
                overrides = {}
        self.versions: dict[str, str] = {**DEFAULT_VERSIONS, **overrides}

    def _arch_select(self, x86_64: str, arm64: str) -> str:
        arch = arch_id()
        match arch:
            case "x86_64":
                return x86_64
            case "arm64":
                return arm64
            case _:
                raise ValueError(f"Unsupported architecture: {arch}")

    @staticmethod
    def _release_url(repo: str, tag: str, asset: str) -> str:
        """Build a GitHub release asset URL."""

        if tag == "latest":
            return f"https://github.com/{repo}/releases/latest/download/{asset}"
        return f"https://github.com/{repo}/releases/download/{tag}/{asset}"

    @staticmethod
    def release_curl_args() -> dict[str, str]:
        return {**CURL_ARGS, **pin_host_args(RELEASE_ASSET_HOST)}

    def cloudflared_url(self) -> str:
        arch = self._arch_select("amd64", "arm64")
        return self._release_url(
            "cloudflare/cloudflared",
            self.versions["cloudflared"],
            f"cloudflared-linux-{arch}",
        )

    def blocky_tar(self) -> str:
        # asset embeds version, so `latest` version will 404
        version = self.versions["blocky"]
        arch = self._arch_select("x86_64", "arm64")
        return self._release_url(
            "0xERR0R/blocky",
            version,
            f"blocky_{version}_Linux_{arch}.tar.gz",
        )

    def eza_tar(self) -> str:
        version = self.versions["eza"]
        arch = self._arch_select("x86_64-unknown-linux-gnu", "aarch64-unknown-linux-gnu")
        return self._release_url(
            "eza-community/eza",
            version,
            f"eza_{arch}.tar.gz",
        )

    def direnv_url(self) -> str:
        arch = self._arch_select("amd64", "arm64")
        return self._release_url(
            "direnv/direnv",
            self.versions["direnv"],
            f"direnv.linux-{arch}",
        )

    def wgcf_url(self) -> str:
        # asset embeds version, so `latest` version will 404
        version = self.versions["wgcf"]
        arch = self._arch_select("amd64", "arm64")
        tag = "latest" if version == "latest" else f"v{version}"
        return self._release_url(
            "ViRb3/wgcf",
            tag,
            f"wgcf_{version}_linux_{arch}",
        )

    def usque_zip(self) -> str:
        # asset embeds version, so `latest` version will 404
        version = self.versions["usque"]
        arch = self._arch_select("amd64", "arm64")
        tag = "latest" if version == "latest" else f"v{version}"
        return self._release_url(
            "Diniboy1123/usque",
            tag,
            f"usque_{version}_linux_{arch}.zip",
        )

    def doggo_tar(self) -> str:
        # asset embeds version, so `latest` version will 404
        version = self.versions["doggo"]
        arch = self._arch_select("x86_64", "arm64")
        tag = "latest" if version == "latest" else f"v{version}"
        return self._release_url(
            "mr-karan/doggo",
            tag,
            f"doggo_{version}_Linux_{arch}.tar.gz",
        )

    def nvim_appimage(self) -> str:
        arch = self._arch_select("x86_64", "arm64")
        ext = "appimage" if arch == "x86_64" else "tar.gz"
        return self._release_url(
            "neovim/neovim",
            self.versions["nvim"],
            f"nvim-linux-{arch}.{ext}",
        )

    def tmux_tar(self) -> str:
        # asset embeds version, so `latest` version will 404
        version = self.versions["tmux"]
        return self._release_url(
            "tmux/tmux",
            version,
            f"tmux-{version}.tar.gz",
        )

    def curl_tar(self) -> str:
        # asset embeds version, so `latest` version will 404
        version = self.versions["curl"]
        arch = self._arch_select("x86_64-musl", "aarch64-musl")
        return self._release_url(
            "stunnel/static-curl",
            version,
            f"curl-linux-{arch}-{version}.tar.xz",
        )

    def nerd_font_tar(self, family: str) -> str:
        """Release archive for a single Nerd Font family, named as its base asset name.

        Assets are arch-independent, so there is nothing to select on here.
        """

        return self._release_url(
            "ryanoasis/nerd-fonts",
            self.versions["nerd_fonts"],
            f"{family}.tar.xz",
        )

    def telemt_tar(self) -> str:
        version = self.versions["telemt"]
        arch = self._arch_select("x86_64", "aarch64")
        tag = "latest" if version == "latest" else version
        return self._release_url(
            "telemt/telemt",
            tag,
            f"telemt-{arch}-linux-gnu.tar.gz",
        )


def get_versions() -> Versions:
    cache_key = "_nullforge_versions"
    try:
        if hasattr(_ctx_host.data, cache_key):
            return getattr(_ctx_host.data, cache_key)
        v = Versions()
        setattr(_ctx_host.data, cache_key, v)
        return v
    except AttributeError:
        return Versions()


def _marker_path(tool: str) -> str:
    return f"{VERSION_MARKER_DIR}/{tool}"


def _recorded_version(tool: str) -> str | None:
    """Check version via marker file."""

    lines = _ctx_host.get_fact(FileContents, path=_marker_path(tool))
    return lines[0].strip() if lines else None


def is_pinned_version_installed(tool: str, binary_path: str) -> bool:
    """Check that binary exists and matches pinned version."""

    if not _ctx_host.get_fact(File, binary_path):
        return False

    pinned = get_versions().versions[tool]
    if pinned == "latest":
        return True

    command = VERSION_COMMANDS[tool]
    if command is None:
        return _recorded_version(tool) == pinned

    output = _ctx_host.get_fact(Command, f"{command.format(bin=binary_path)} 2>&1 || true")
    if not output:
        return False

    return pinned.removeprefix("v") in output


def record_installed_version(tool: str) -> None:
    """Persist pinned version for tools without version output."""

    files.put(
        name=f"Record installed {tool} version",
        src=io.StringIO(f"{get_versions().versions[tool]}\n"),
        dest=_marker_path(tool),
        mode="0644",
        create_remote_dir=True,
        _sudo=True,
    )
