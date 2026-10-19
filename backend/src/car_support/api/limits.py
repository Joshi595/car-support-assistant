"""Per-client rate limits (in memory; one API process per container in this setup)."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# ponytail: in-memory counters are per process; with several replicas use storage_uri="redis://...".
limiter = Limiter(key_func=get_remote_address)
