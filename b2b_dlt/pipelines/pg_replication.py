"""
PostgreSQL Replication pipeline.

Replicates data from an existing PostgreSQL database into MotherDuck using
logical replication (CDC — Change Data Capture). On the first run it performs
an initial full load; subsequent runs pick up only INSERT/UPDATE/DELETE changes.

Requirements:
  - The Postgres user must have the REPLICATION attribute.
  - The Postgres user must own the tables to replicate, or be a superuser.
  - [sources.pg_replication.credentials] must be fully configured in
    .dlt/secrets.toml.
  - psycopg2 must be installed: uv add psycopg2-binary
"""

import logging

logger = logging.getLogger(__name__)

SLOT_NAME = "b2b_dlt_slot"
PUB_NAME = "b2b_dlt_pub"


def run(
    schema_name: str = "public",
    table_names: str = "test_table",
) -> bool:
    """
    Runs the PostgreSQL replication pipeline.

    Imports are deferred (lazy) so that a missing psycopg2 installation only
    fails this pipeline and does not crash the entire orchestrator.

    First run: creates a replication slot + publication and performs an initial
    full load of all existing rows.
    Subsequent runs: consume only the accumulated WAL changes (CDC).

    Args:
        schema_name: Name of the source schema to replicate (default: "public").
        table_names: Name or sequence of names of tables to replicate.

    Returns:
        True on success.
    """
    # Lazy imports — if psycopg2 is not installed only this pipeline fails
    import dlt
    from dlt.destinations.impl.postgres.configuration import PostgresCredentials
    from pg_replication import replication_resource
    from pg_replication.helpers import init_replication

    logger.info(
        "pg_replication pipeline started (schema=%s, tables=%s)...",
        schema_name,
        table_names,
    )

    pipeline = dlt.pipeline(
        pipeline_name="pg_replication_pipeline",
        destination="snowflake",
        dataset_name="raw_internal",
    )

    # Creates the replication slot and publication on first run.
    # With reset=False, an existing slot is reused and only new changes are
    # captured on subsequent runs.
    snapshot = init_replication(
        slot_name=SLOT_NAME,
        pub_name=PUB_NAME,
        table_names=table_names,
        schema_name=schema_name,
        persist_snapshots=True,
        reset=False,
    )

    if snapshot is not None:
        logger.info("Performing initial load...")
        load_info = pipeline.run(snapshot)
        logger.info("Initial load finished: %s", load_info)

    # Consume CDC changes accumulated since the last run
    changes = replication_resource(SLOT_NAME, PUB_NAME)
    load_info = pipeline.run(changes)
    logger.info("pg_replication pipeline finished: %s", load_info)
    return True
