"""Network security domain types."""

from enum import StrEnum


class SshHostKeyType(StrEnum):
    """Host key type sshd offers."""

    ED25519 = "ed25519"
    ECDSA = "ecdsa"
    RSA = "rsa"


PQ_KEX_ALGORITHMS = (
    "mlkem768x25519-sha256",
    "sntrup761x25519-sha512@openssh.com",
)
"""Post-quantum hybrid key exchange algorithms, most preferred first."""

CLASSICAL_KEX_ALGORITHMS = (
    "curve25519-sha256",
    "curve25519-sha256@libssh.org",
    "diffie-hellman-group-exchange-sha256",
    "diffie-hellman-group16-sha512",
    "diffie-hellman-group18-sha512",
)
"""Strong classical key exchange in default-preference order, offered after the PQ hybrids."""

WEAK_KEX_PATTERNS = "ecdh-sha2-*,diffie-hellman-group14-*,diffie-hellman-group-exchange-sha1"
"""Key exchanges removed from default set."""

WEAK_MAC_PATTERNS = "hmac-sha1*,umac-64*,hmac-sha2-256,hmac-sha2-512,umac-128@openssh.com"
"""MACs removed from default set."""

MIN_DH_MODULUS_SIZE = 3071
"""Minimum size kept in /etc/ssh/moduli; the file's size column is bits-1, so 3071 keeps >=3072-bit groups."""

HOST_KEY_ALGORITHMS: dict[SshHostKeyType, tuple[str, ...]] = {
    SshHostKeyType.ED25519: ("ssh-ed25519",),
    SshHostKeyType.ECDSA: ("ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521"),
    SshHostKeyType.RSA: ("rsa-sha2-512", "rsa-sha2-256"),
}
"""Signature algorithms sshd may use per host key type."""
