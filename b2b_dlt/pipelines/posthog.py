"""
PostHog pipeline.

PostHog is not listed in dlt's official verified-sources because its REST API
follows a straightforward, standard pattern (Bearer auth + cursor-based pagination).
Per dlt team guidance, this is best implemented via the declarative `rest_api`
configuration rather than a standalone package.

Note: The `events` resource is intentionally excluded. PostHog's GET /events/
endpoint is officially deprecated for export purposes. For high-volume event
export, use the HogQL Query endpoint or Batch Exports instead.
"""

import logging

import dlt
from dlt.sources.rest_api import RESTAPIConfig, rest_api_resources

logger = logging.getLogger(__name__)


@dlt.source(name="posthog")
def posthog_source(
    project_id: str = dlt.config.value,
    api_key: str = dlt.secrets.value,
    host: str = dlt.config.value,
):
    """
    PostHog REST API source.

    Args:
        project_id: Your PostHog project ID (Settings > Project > General).
        api_key: Personal API key (Settings > Personal API keys). Requires
            at minimum the following scopes: person:read, feature_flag:read,
            cohort:read, insight:read, dashboard:read, experiment:read,
            action:read, annotation:read.
        host: Region base URL. Use "https://us.posthog.com" for US Cloud,
            "https://eu.posthog.com" for EU Cloud, or your own domain for
            self-hosted deployments.
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
        # resource_defaults apply to all resources below.
        # All PostHog list endpoints return {"next": ..., "results": [...]}
        # and each record has a stable "id" field suitable as a primary key.
        "resource_defaults": {
            "primary_key": "id",
            "write_disposition": "merge",  # upsert on re-run; no duplicates
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


def run() -> bool:
    """
    Runs the PostHog pipeline.

    Returns:
        True on success.
    """
    logger.info("PostHog pipeline started...")
    pipeline = dlt.pipeline(
        pipeline_name="posthog_pipeline",
        destination="motherduck",
        dataset_name="posthog_data",
    )
    load_info = pipeline.run(posthog_source())
    logger.info("PostHog pipeline finished: %s", load_info)
    return True
