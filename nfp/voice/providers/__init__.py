"""NFP Voice Engine - audio sources. Every provider writes ONE sentence as mono 16-bit PCM WAV at the target rate,
with the planned silence before / after inside the file (the format the unchanged Stage 2 core accepts)."""
from .base import FORMAT, ProviderError, write_wav  # noqa: F401
from .prepared import PreparedProvider  # noqa: F401
from .synthetic import SyntheticProvider  # noqa: F401

PROVIDERS = {"synthetic": SyntheticProvider, "prepared": PreparedProvider}
