"""
Stripe Analytics pipeline.

Loads data from all Stripe API endpoints. Incremental endpoints use the
`append` write disposition; all other endpoints use `replace`.

Requires: the `stripe_analytics` dlt source package (bundled in this repo
under ./stripe_analytics/).
"""

import logging

logger = logging.getLogger(__name__)


def run() -> bool:
    """
    Runs the Stripe Analytics pipeline.

    Returns:
        True on success.
    """
    # Lazy imports so that a missing dependency only fails this pipeline,
    # not the entire orchestrator.
    import dlt
    from stripe_analytics import ENDPOINTS, INCREMENTAL_ENDPOINTS, stripe_source

    logger.info("Stripe pipeline started...")
    pipeline = dlt.pipeline(
        pipeline_name="stripe_analytics",
        destination="motherduck",
        dataset_name="stripe_data",
    )
    source = stripe_source(endpoints=ENDPOINTS + INCREMENTAL_ENDPOINTS)
    load_info = pipeline.run(source)
    logger.info("Stripe pipeline finished: %s", load_info)
    return True
