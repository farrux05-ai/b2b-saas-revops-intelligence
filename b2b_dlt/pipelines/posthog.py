"""
PostHog pipeline.

PostHog is not listed in dlt's official verified-sources because its REST API
follows a straightforward, standard pattern (Bearer auth + cursor-based pagination).
Per dlt team guidance, this is best implemented via the declarative `rest_api`
configuration rather than a standalone package.

Event Export Strategy
─────────────────────
The GET /events/ endpoint is officially deprecated for bulk export.
Instead, we use the HogQL Query endpoint (POST /query/) which:
  - Supports full SQL via PostHog's columnar HogQL engine
  - Returns results in column-oriented format → zipped into dicts
  - Supports OFFSET-based pagination (hasMore field)
  - Allows incremental loading on the `timestamp` column
  - Has no row limit (unlike the deprecated endpoint's hard cap of 300)

Scopes required for the Personal API key:
  persons, feature_flags, cohorts, insights, dashboards, experiments,
  actions, annotations, query (for HogQL)
"""

import logging

import dlt
from dlt.sources.rest_api import RESTAPIConfig, rest_api_resources

logger = logging.getLogger(__name__)


# ── Metadata sources (persons, cohorts, flags, etc.) ─────────────────────────

@dlt.source(name="posthog")
def posthog_source(
    project_id: str = dlt.config.value,
    api_key: str = dlt.secrets.value,
    host: str = dlt.config.value,
):
    """
    PostHog REST API source for metadata resources.

    Args:
        project_id: Your PostHog project ID (Settings > Project > General).
        api_key: Personal API key (phx_ prefix). Required scopes:
            person:read, feature_flag:read, cohort:read, insight:read,
            dashboard:read, experiment:read, action:read, annotation:read.
        host: Region base URL. Use "https://us.posthog.com" for US Cloud,
            "https://eu.posthog.com" for EU Cloud.
    """
    config: RESTAPIConfig = {
        "client": {
            "base_url": f"{host}/api/projects/{project_id}/",
            "auth": {
                "type": "bearer",
                "token": api_key,
            },
            "paginator": {
                "type": "json_link",
                "next_url_path": "next",
            },
        },
        # All PostHog list endpoints return {"next": ..., "results": [...]}
        "resource_defaults": {
            "primary_key": "id",
            "write_disposition": "merge",
            "endpoint": {
                "data_selector": "results",
            },
        },
        "resources": [
            "persons",
            "feature_flags",
            "cohorts",
            "insights",
            "dashboards",
            "experiments",
            "actions",
            "annotations",
        ],
    }

    yield from rest_api_resources(config)


# ── Event export via HogQL Query API ─────────────────────────────────────────

@dlt.resource(
    name="events",
    write_disposition="append",
    primary_key="uuid",
)
def posthog_events_hogql(
    project_id: str = dlt.config.value,
    api_key: str = dlt.secrets.value,
    host: str = dlt.config.value,
    last_timestamp=dlt.sources.incremental(
        "timestamp",
        # First run fetches last 30 days; subsequent runs are incremental.
        initial_value="2024-01-01T00:00:00",
        last_value_func=max,
    ),
):
    """
    Incremental event export using PostHog's HogQL Query endpoint.

    GET /events/ is deprecated — this uses the HogQL SQL engine instead:
      POST /api/projects/{project_id}/query/

    Loads only events newer than `last_timestamp.last_value` on each run.
    Pagination via OFFSET + hasMore field (10 000 rows per batch).

    Columns exported:
        uuid, event, distinct_id, person_id, properties, timestamp,
        created_at, elements_chain, session_id
    """
    import requests

    BATCH_SIZE = 10_000
    url = f"{host}/api/projects/{project_id}/query/"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    since = last_timestamp.last_value
    offset = 0

    logger.info(
        "PostHog events: fetching from %s (batch_size=%d)",
        since,
        BATCH_SIZE,
    )

    while True:
        payload = {
            "query": {
                "kind": "HogQLQuery",
                "query": f"""
                    SELECT
                        uuid,
                        event,
                        distinct_id,
                        person_id,
                        properties,
                        timestamp,
                        created_at,
                        elements_chain,
                        $session_id AS session_id
                    FROM events
                    WHERE timestamp > '{since}'
                    ORDER BY timestamp ASC
                    LIMIT {BATCH_SIZE}
                    OFFSET {offset}
                """,
            }
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        body = resp.json()

        columns = body.get("columns", [])
        rows = body.get("results", [])

        if not rows:
            logger.info("PostHog events: no more rows at offset %d", offset)
            break

        for row in rows:
            yield dict(zip(columns, row))

        logger.info(
            "PostHog events: yielded %d rows (offset=%d)",
            len(rows),
            offset,
        )

        # PostHog returns hasMore=True when there are more pages
        if not body.get("hasMore", False):
            break

        offset += BATCH_SIZE


# ── Pipeline runner ───────────────────────────────────────────────────────────

def run() -> bool:
    """
    Runs the PostHog pipeline: metadata resources + incremental event export.

    Returns:
        True on success.
    """
    logger.info("PostHog pipeline started...")

    pipeline = dlt.pipeline(
        pipeline_name="posthog_pipeline",
        destination="snowflake",
        dataset_name="raw_posthog",
    )

    # 1. Load metadata resources (persons, flags, cohorts, etc.)
    load_info = pipeline.run(posthog_source())
    logger.info("PostHog metadata finished: %s", load_info)

    # 2. Load events incrementally via HogQL
    load_info = pipeline.run(posthog_events_hogql())
    logger.info("PostHog events finished: %s", load_info)

    return True
