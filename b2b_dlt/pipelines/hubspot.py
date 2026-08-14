"""
HubSpot CRM pipeline.

Loads all CRM resources along with their full property change history:
contacts, companies, deals, and tickets, each with a corresponding
`{resource}_property_history` table.

Requires: the `hubspot` dlt source package (bundled in this repo under ./hubspot/).
"""

import logging

logger = logging.getLogger(__name__)


def run() -> bool:
    """
    Runs the HubSpot pipeline with property history enabled.

    Returns:
        True on success.
    """
    # Lazy imports so that a missing dependency only fails this pipeline,
    # not the entire orchestrator.
    import dlt
    from hubspot import hubspot

    logger.info("HubSpot pipeline started...")
    pipeline = dlt.pipeline(
        pipeline_name="hubspot",
        destination="snowflake",
        dataset_name="raw_hubspot",
    )
    # include_history=True loads property change history for each CRM entity
    # into separate tables: contacts_property_history, deals_property_history, etc.
    data = hubspot(include_history=True)
    load_info = pipeline.run(data)
    logger.info("HubSpot pipeline finished: %s", load_info)
    return True
