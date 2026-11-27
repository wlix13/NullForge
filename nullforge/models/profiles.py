"""Profiles domain models."""

from enum import StrEnum


class NerdFont(StrEnum):
    """Nerd Font family, valued as its base asset name in a `ryanoasis/nerd-fonts` release.

    A curated subset of the ~70 published families; add a member to offer another one.
    """

    CASCADIA_CODE = "CascadiaCode"
    COMMIT_MONO = "CommitMono"
    DEJAVU_SANS_MONO = "DejaVuSansMono"
    FIRA_CODE = "FiraCode"
    FIRA_MONO = "FiraMono"
    GEIST_MONO = "GeistMono"
    HACK = "Hack"
    IBM_PLEX_MONO = "IBMPlexMono"
    INCONSOLATA = "Inconsolata"
    INTEL_ONE_MONO = "IntelOneMono"
    IOSEVKA = "Iosevka"
    JETBRAINS_MONO = "JetBrainsMono"
    MESLO = "Meslo"
    MONASPACE = "Monaspace"
    MONONOKI = "Mononoki"
    ROBOTO_MONO = "RobotoMono"
    SOURCE_CODE_PRO = "SourceCodePro"
    SPACE_MONO = "SpaceMono"
    SYMBOLS_ONLY = "NerdFontsSymbolsOnly"
    UBUNTU_MONO = "UbuntuMono"
    VICTOR_MONO = "VictorMono"
    ZED_MONO = "ZedMono"
