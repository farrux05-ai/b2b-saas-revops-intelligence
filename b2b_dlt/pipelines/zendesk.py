"""
Zendesk pipeline.

Loads all resources from Zendesk Support, Chat, and Talk
using incremental loading (only new or updated records on each run).

Requires: the `zendesk` dlt source package (bundled in this repo under ./zendesk/).
"""

import logging

logger = logging.getLogger(__name__)


def run() -> bool:
    """
    Runs the Zendesk pipeline (Support + Chat + Talk, incremental mode).

    Returns:
        True on success.
    """
    # Lazy imports so that a missing dependency only fails this pipeline,
    # not the entire orchestrator.
    import dlt
    from zendesk import zendesk_chat, zendesk_talk, zendesk_support

    logger.info("Zendesk pipeline started...")
    pipeline = dlt.pipeline(
        pipeline_name="dlt_zendesk_pipeline",
        destination="motherduck",
        dev_mode=False,
        dataset_name="zendesk_data",
    )
    data_support = zendesk_support(load_all=True)
    data_chat = zendesk_chat()
    data_talk = zendesk_talk()
    load_info = pipeline.run(data=[data_support, data_chat, data_talk])
    logger.info("Zendesk pipeline finished: %s", load_info)
    return True
