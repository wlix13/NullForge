from enum import StrEnum


class SwapType(StrEnum):
    """Type of swap configuration."""

    BASIC = "basic"
    ZRAM = "zram"


class SwapAlgo(StrEnum):
    """Algorithm for ZRAM compression."""

    ZSTD = "zstd"
    LZO = "lzo"
