"""Shell profiles and tools deployment module."""

import shlex

from pyinfra.context import host
from pyinfra.facts.files import Block, Directory, File
from pyinfra.operations import files, git, server

from nullforge.models.profiles import NerdFont
from nullforge.molds import FeaturesMold, ProfilesMold, UserMold
from nullforge.smithy.github import sha256_for_download_url
from nullforge.smithy.http import CURL_ARGS
from nullforge.smithy.install import install_release_binary
from nullforge.smithy.packages import get_pm
from nullforge.smithy.versions import STATIC_URLS, ZSH_PLUGINS, Versions, get_versions, is_pinned_version_installed
from nullforge.templates import get_template_path, render_template


ZSHRC_MARKER = "# {mark} NULLFORGE MANAGED BLOCK"
"""Marker around the generated part of ``.zshrc``; anything outside it survives a re-deploy."""


def deploy_shell_profiles() -> None:
    """Deploy shell profiles and tools configuration."""

    features: FeaturesMold = host.data.features
    profiles_opts: ProfilesMold = features.profiles
    reinstall = profiles_opts.reinstall

    _install_eza(reinstall)

    _install_tmux(reinstall)

    _install_nvim(reinstall)

    _install_zoxide(reinstall)

    _install_direnv(reinstall)

    _install_starship(reinstall)

    for user, home_dir in host.loop(_get_profile_targets(features)):
        _install_user_profiles(user, home_dir, reinstall, profiles_opts.font)


def _get_profile_targets(features: FeaturesMold) -> list[tuple[str, str]]:
    """Get list of users and home directories for profile installation."""

    user_opts: UserMold = features.users
    profiles_opts: ProfilesMold = features.profiles
    targets = []
    if profiles_opts.for_root:
        targets.append(("root", "/root"))

    if profiles_opts.for_user:
        user = user_opts.name
        targets.append((user, f"/home/{user}"))

    return targets


def _install_user_profiles(user: str, home_dir: str, reinstall: bool, font: NerdFont | None) -> None:
    """Configure user profile."""

    _configure_user_oh_my_zsh(user, home_dir, reinstall)
    _configure_user_shell_profiles(user, home_dir)
    if font:
        _install_nerd_font(user, home_dir, font, reinstall)
    _install_user_tmux(user, home_dir, reinstall)
    _install_user_nvim(user, home_dir, reinstall)
    _install_atuin(user, home_dir, reinstall)


def _configure_user_oh_my_zsh(user: str, home_dir: str, reinstall: bool) -> None:
    """Install oh-my-zsh and its plugins for a specific user."""

    oh_my_zsh_dir = f"{home_dir}/.oh-my-zsh"
    plugins_dir = f"{oh_my_zsh_dir}/custom/plugins"
    fact_kwargs = {"_sudo": True, "_sudo_user": user}

    if reinstall:
        files.directory(
            name=f"Remove existing oh-my-zsh for {user}",
            path=oh_my_zsh_dir,
            present=False,
            _sudo=True,
            _sudo_user=user,
        )

    if not host.get_fact(Directory, oh_my_zsh_dir, **fact_kwargs):
        git.repo(
            name=f"Install oh-my-zsh for {user}",
            src="https://github.com/ohmyzsh/ohmyzsh",
            dest=oh_my_zsh_dir,
            _sudo=True,
            _sudo_user=user,
        )

    for plugin_name, plugin_src in host.loop(ZSH_PLUGINS.items()):
        plugin_dir = f"{plugins_dir}/{plugin_name}"
        if reinstall:
            files.directory(
                name=f"Remove existing {plugin_name} plugin for {user}",
                path=plugin_dir,
                present=False,
                _sudo=True,
                _sudo_user=user,
            )
        if not host.get_fact(Directory, plugin_dir, **fact_kwargs):
            git.repo(
                name=f"Install {plugin_name} plugin for {user}",
                src=plugin_src,
                dest=plugin_dir,
                _sudo=True,
                _sudo_user=user,
            )


def _configure_user_shell_profiles(user: str, home_dir: str) -> None:
    """Configure shell profiles (.zshrc, starship, direnv) for a specific user."""

    _configure_user_zshrc(user, home_dir)

    files.put(
        name=f"Configure starship prompt for {user}",
        src=get_template_path("profiles/starship.toml"),
        dest=f"{home_dir}/.config/starship.toml",
        mode="0644",
        _sudo=True,
        _sudo_user=user,
    )

    files.put(
        name=f"Configure direnv for {user}",
        src=get_template_path("profiles/direnv.toml"),
        dest=f"{home_dir}/.config/direnv/direnv.toml",
        mode="0644",
        create_remote_dir=True,
        _sudo=True,
        _sudo_user=user,
    )


def _configure_user_zshrc(user: str, home_dir: str) -> None:
    """Write the generated part of ``.zshrc`` into a marked block, leaving host-specific edits untouched."""

    zshrc_path = f"{home_dir}/.zshrc"
    fact_kwargs = {"_sudo": True, "_sudo_user": user}

    # an empty list means the file exists without markers: a pre-marker deploy templated the whole
    # file, so drop every line once - otherwise the block gets prepended to a stale copy of itself
    if host.get_fact(Block, path=zshrc_path, marker=ZSHRC_MARKER, **fact_kwargs) == []:
        files.line(
            name=f"Clear unmarked .zshrc for {user}",
            path=zshrc_path,
            line=".*",
            present=False,
            backup=True,
            _sudo=True,
            _sudo_user=user,
        )

    files.block(
        name=f"Configure .zshrc for {user}",
        path=zshrc_path,
        content=render_template("profiles/zshrc.j2", home=home_dir).rstrip("\n"),
        marker=ZSHRC_MARKER,
        before=True,
        after=True,
        _sudo=True,
        _sudo_user=user,
    )

    # files.block writes through a mktemp file, so a freshly created .zshrc would keep its 0600
    files.file(
        name=f"Set .zshrc permissions for {user}",
        path=zshrc_path,
        mode="0644",
        _sudo=True,
        _sudo_user=user,
    )


def _install_nerd_font(user: str, home_dir: str, family: NerdFont, reinstall: bool = False) -> None:
    """Install a Nerd Font family for a user straight from its release archive."""

    versions = get_versions()
    version = versions.versions["nerd_fonts"]
    fonts_root = f"{home_dir}/.local/share/fonts"
    # the version is part of the directory name, so bumping the pin re-triggers the install
    font_dir = f"{fonts_root}/{family}-{version}"

    if not reinstall and host.get_fact(Directory, font_dir, _sudo=True, _sudo_user=user):
        return

    url = versions.nerd_font_tar(family)
    # kept in the user's own cache so the two profile targets never fight over one /tmp path
    cache_dir = f"{home_dir}/.cache/nullforge"
    archive_path = f"{cache_dir}/{family}-{version}.tar.xz"

    files.directory(
        name=f"Create nullforge cache directory for {user}",
        path=cache_dir,
        mode="0755",
        _sudo=True,
        _sudo_user=user,
    )

    files.download(
        name=f"Download {family} Nerd Font for {user}",
        src=url,
        dest=archive_path,
        force=True,
        sha256sum=sha256_for_download_url(url),
        extra_curl_args=Versions.release_curl_args(),
        _sudo=True,
        _sudo_user=user,
        _retries=3,
        _retry_delay=10,
    )

    server.shell(
        name=f"Install {family} Nerd Font for {user}",
        commands=[
            f"rm -rf {shlex.quote(f'{fonts_root}/{family}')}-*",
            f"mkdir -p {shlex.quote(font_dir)}",
            f"tar -xJf {shlex.quote(archive_path)} -C {shlex.quote(font_dir)}",
            f"fc-cache -f {shlex.quote(fonts_root)}",
            f"rm -f {shlex.quote(archive_path)}",
        ],
        _sudo=True,
        _sudo_user=user,
    )


def _install_user_tmux(user: str, home_dir: str, reinstall: bool = False) -> None:
    """Install and configure tmux for a specific user."""

    tpm_dir = f"{home_dir}/.tmux/plugins/tpm"
    config_dir = f"{home_dir}/.config/tmux"
    fact_kwargs = {"_sudo": True, "_sudo_user": user}

    if reinstall or not host.get_fact(Directory, tpm_dir, **fact_kwargs):
        files.directory(
            name=f"Remove existing tmux plugins dir for {user}",
            path=f"{home_dir}/.tmux",
            present=False,
            _sudo=True,
            _sudo_user=user,
        )

        files.directory(
            name=f"Remove existing tmux config dir for {user}",
            path=config_dir,
            present=False,
            _sudo=True,
            _sudo_user=user,
        )

        git.repo(
            name=f"Install TPM (Tmux Plugin Manager) for {user}",
            src="https://github.com/tmux-plugins/tpm",
            dest=tpm_dir,
            _sudo=True,
            _sudo_user=user,
        )

    files.directory(
        name=f"Create tmux config directory for {user}",
        path=config_dir,
        mode="0755",
        _sudo=True,
        _sudo_user=user,
    )

    files.put(
        name=f"Setup tmux config for {user}",
        src=get_template_path("profiles/tmux.conf"),
        dest=f"{config_dir}/tmux.conf",
        mode="0644",
        _sudo=True,
        _sudo_user=user,
    )


def _install_user_nvim(user: str, home_dir: str, reinstall: bool = False) -> None:
    """Install and configure nvim/NvChad for a specific user."""

    fact_kwargs = {"_sudo": True, "_sudo_user": user}
    if not reinstall and host.get_fact(File, f"{home_dir}/.config/nvim/lua/chadrc.lua", **fact_kwargs):
        return

    for nvim_path in host.loop(
        (
            f"{home_dir}/.config/nvim",
            f"{home_dir}/.local/state/nvim",
            f"{home_dir}/.local/share/nvim",
        )
    ):
        files.directory(
            name=f"Remove existing nvim path {nvim_path} for {user}",
            path=nvim_path,
            present=False,
            _sudo=True,
            _sudo_user=user,
        )

    git.repo(
        name=f"Install NvChad for {user}",
        src="https://github.com/NvChad/starter",
        dest=f"{home_dir}/.config/nvim",
        _sudo=True,
        _sudo_user=user,
    )

    with open(get_template_path("nvim/nvim_patch.lua.j2"), encoding="utf-8") as f:
        nvim_patch = f.read()

    files.block(
        name=f"Apply nvim patch to init.lua for {user}",
        path=f"{home_dir}/.config/nvim/init.lua",
        content=nvim_patch,
        marker="-- {mark} Change cursor to original after exiting vim",
        _sudo=True,
        _sudo_user=user,
    )

    files.replace(
        name=f"Change theme to tokyo-night for {user}",
        path=f"{home_dir}/.config/nvim/lua/chadrc.lua",
        text="onedark",
        replace="tokyonight",
        _sudo=True,
        _sudo_user=user,
    )


def _install_starship(reinstall: bool = False) -> None:
    """Install starship prompt."""

    pm = get_pm()

    if pm.is_debian_based and pm.distro_major in [13, 25]:
        if reinstall or not host.get_fact(File, "/usr/bin/starship"):
            _install_starship_from_repo()
    else:
        if reinstall or not host.get_fact(File, "/usr/local/bin/starship"):
            _install_starship_from_script()


def _install_starship_from_repo() -> None:
    """Install starship prompt from repo."""

    pm = get_pm()
    pm.install(
        name="Install starship from repo",
        packages=["starship"],
        _sudo=True,
    )


def _install_starship_from_script() -> None:
    """Install starship prompt from script."""

    starship_install_path = "/tmp/starship.sh"
    files.download(
        name="Download starship installation script",
        src=STATIC_URLS["starship_install"],
        dest=starship_install_path,
        mode="0755",
        extra_curl_args=CURL_ARGS,
        _sudo=True,
        _retries=3,
        _retry_delay=10,
    )

    server.shell(
        name="Install starship prompt",
        commands=[f"sh {starship_install_path} --yes"],
        _sudo=True,
    )


def _install_atuin(user: str, home_dir: str, reinstall: bool = False) -> None:
    """Install atuin for better shell history."""

    fact_kwargs = {"_sudo": True, "_sudo_user": user}
    if not reinstall and host.get_fact(File, f"{home_dir}/.atuin/bin/atuin", **fact_kwargs):
        return

    atuin_install_path = "/tmp/atuin.sh"
    files.download(
        name=f"Download atuin installation script for {user}",
        src=STATIC_URLS["atuin_install"],
        dest=atuin_install_path,
        mode="0755",
        extra_curl_args=CURL_ARGS,
        _sudo=True,
        _retries=3,
        _retry_delay=10,
    )

    server.shell(
        name=f"Install atuin installation script for {user}",
        commands=[f"sh {atuin_install_path} -- --non-interactive"],
        _sudo=True,
        _sudo_user=user,
    )


def _install_zoxide(reinstall: bool = False) -> None:
    """Install zoxide for better navigation."""

    if not reinstall and host.get_fact(File, "/usr/local/bin/zoxide"):
        return

    zoxide_install_path = "/tmp/zoxide.sh"
    files.download(
        name="Download zoxide installation script",
        src=STATIC_URLS["zoxide_install"],
        dest=zoxide_install_path,
        mode="0755",
        extra_curl_args=CURL_ARGS,
        _sudo=True,
        _retries=3,
        _retry_delay=10,
    )

    server.shell(
        name="Install zoxide",
        commands=[f"sh {zoxide_install_path} --bin-dir /usr/local/bin"],
        _sudo=True,
    )


def _install_direnv(reinstall: bool = False) -> None:
    """Install direnv for better env management."""

    direnv_exec_path = "/usr/local/bin/direnv"
    if not reinstall and is_pinned_version_installed("direnv", direnv_exec_path):
        return

    install_release_binary(
        name="Install direnv binary",
        url=get_versions().direnv_url(),
        dest=direnv_exec_path,
    )


def _install_eza(reinstall: bool = False) -> None:
    """Install eza binary for enhanced ls functionality."""

    eza_exec_path = "/usr/local/bin/eza"
    if not reinstall and is_pinned_version_installed("eza", eza_exec_path):
        return

    install_release_binary(
        name="Extract eza and install eza binary",
        url=get_versions().eza_tar(),
        dest=eza_exec_path,
        binary_name="eza",
    )


def _install_tmux(reinstall: bool = False) -> None:
    """Install tmux package."""

    if not reinstall and is_pinned_version_installed("tmux", "/usr/local/bin/tmux"):
        return

    versions = get_versions()
    tmux_tar_path = "/tmp/tmux.tar.gz"
    tmux_src_dir = f"/tmp/tmux-{versions.versions['tmux']}"

    files.download(
        name="Download tmux source",
        src=versions.tmux_tar(),
        dest=tmux_tar_path,
        force=True,
        extra_curl_args=get_versions().release_curl_args(),
        _retries=3,
        _retry_delay=10,
    )

    server.shell(
        name="Extract and build tmux",
        commands=[
            "rm -rf /tmp/tmux-*/",
            f"tar -zxf {tmux_tar_path} -C /tmp/ && rm -f {tmux_tar_path}",
            f"cd {tmux_src_dir} && ./configure",
            f"cd {tmux_src_dir} && make -j$(nproc) && make install",
            f"rm -rf {tmux_src_dir}",
        ],
        _sudo=True,
    )

    pm = get_pm()
    pm.install(
        name="Remove existing tmux package",
        packages=["tmux"],
        present=False,
        _sudo=True,
    )


def _install_nvim(reinstall: bool = False) -> None:
    """Install nvim package."""

    if not reinstall and is_pinned_version_installed("nvim", "/usr/bin/nvim-source/AppRun"):
        return

    # clean up any previous install so old and new extracted files never mix
    files.directory(
        name="Remove existing nvim-source directory",
        path="/usr/bin/nvim-source",
        present=False,
        _sudo=True,
    )

    files.file(
        name="Remove existing nvim binary",
        path="/usr/bin/nvim",
        present=False,
        force=True,
        force_backup=False,
        _sudo=True,
    )

    nvim_appimage_path = "/tmp/nvim.appimage"
    files.download(
        name="Download nvim appimage",
        src=get_versions().nvim_appimage(),
        dest=nvim_appimage_path,
        mode="0755",
        force=True,
        extra_curl_args=get_versions().release_curl_args(),
        _sudo=True,
        _retries=3,
        _retry_delay=10,
    )

    files.directory(
        name="Create nvim source directory",
        path="/usr/bin/nvim-source",
        mode="0755",
        _sudo=True,
    )

    server.shell(
        name="Extract nvim appimage to target directory",
        commands=[f"cd /usr/bin && {nvim_appimage_path} --appimage-extract"],
        _sudo=True,
    )

    server.shell(
        name="Move extracted contents to nvim-source",
        commands=["mv /usr/bin/squashfs-root/* /usr/bin/nvim-source/"],
        _sudo=True,
    )

    files.directory(
        name="Remove empty squashfs-root directory",
        path="/usr/bin/squashfs-root",
        present=False,
        _sudo=True,
    )

    files.link(
        name="Create symlink to nvim",
        path="/usr/bin/nvim",
        target="/usr/bin/nvim-source/AppRun",
        _sudo=True,
    )

    files.file(
        name="Remove nvim appimage file",
        path=nvim_appimage_path,
        present=False,
        _sudo=True,
    )


deploy_shell_profiles()
