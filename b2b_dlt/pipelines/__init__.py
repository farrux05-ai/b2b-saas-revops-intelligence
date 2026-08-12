"""
Pipelines package.

Each module exposes a single `run() -> bool` function.
pg_replication uses lazy imports internally (requires psycopg2).
"""

from pipelines import hubspot, posthog, stripe, zendesk
from pipelines import pg_replication  # heavy deps are lazy-imported inside run()

__all__ = ["posthog", "hubspot", "zendesk", "stripe", "pg_replication"]
