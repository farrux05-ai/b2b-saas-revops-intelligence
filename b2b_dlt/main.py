"""
B2B dlt Pipeline Orchestrator
==============================

Single entry point for running all data source pipelines.

Usage:
    # Run all pipelines sequentially (suitable for cron)
    python main.py

    # Run a single pipeline
    python main.py --pipeline posthog
    python main.py --pipeline hubspot
    python main.py --pipeline zendesk
    python main.py --pipeline stripe
    python main.py --pipeline pg_replication

    # Run multiple selected pipelines
    python main.py --pipeline posthog hubspot stripe

    # Change log verbosity
    python main.py --log-level DEBUG
"""

import argparse
import logging
import sys
import time
from typing import Callable

# ── Pipeline modules ────────────────────────────────────────────────────────
from pipelines import posthog, hubspot, zendesk, stripe, pg_replication

# ── Logging configuration ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


# ── Pipeline registry ────────────────────────────────────────────────────────
# Each entry maps a pipeline name to its (run_function, description) tuple.
PIPELINES: dict[str, tuple[Callable[[], bool], str]] = {
    "posthog": (
        posthog.run,
        "PostHog — persons, insights, dashboards, cohorts, and more",
    ),
    "hubspot": (
        hubspot.run,
        "HubSpot CRM — contacts, companies, deals, tickets (with property history)",
    ),
    "zendesk": (
        zendesk.run,
        "Zendesk — Support tickets, Chat, Talk (incremental)",
    ),
    "stripe": (
        stripe.run,
        "Stripe Analytics — all payment endpoints",
    ),
    "pg_replication": (
        pg_replication.run,
        "PostgreSQL CDC — logical replication (initial load + change capture)",
    ),
}


# ── CLI argument parsing ─────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="B2B dlt Pipeline Orchestrator — loads data from all sources into MotherDuck.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(
            f"  {name:<16} {desc}"
            for name, (_, desc) in PIPELINES.items()
        ),
    )
    parser.add_argument(
        "--pipeline",
        nargs="+",
        choices=list(PIPELINES.keys()),
        metavar="NAME",
        help=(
            "Pipeline(s) to run. "
            f"Choices: {', '.join(PIPELINES)}. "
            "If omitted, all pipelines are run."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level (default: INFO)",
    )
    return parser.parse_args()


# ── Pipeline orchestrator ─────────────────────────────────────────────────────
def run_pipelines(names: list[str]) -> dict[str, bool]:
    """
    Runs the specified pipelines sequentially.
    If one pipeline fails, the remaining ones still execute.

    Returns:
        dict mapping pipeline name to success status (True/False).
    """
    results: dict[str, bool] = {}

    for name in names:
        run_fn, description = PIPELINES[name]
        logger.info("=" * 60)
        logger.info("▶ Pipeline: %s", name)
        logger.info("  %s", description)
        logger.info("=" * 60)

        t_start = time.perf_counter()
        try:
            success = run_fn()
            elapsed = time.perf_counter() - t_start
            results[name] = success
            if success:
                logger.info("✅ %s completed successfully (%.1f s)", name, elapsed)
            else:
                logger.warning("⚠️  %s finished with a non-success return (%.1f s)", name, elapsed)
        except Exception as exc:  # noqa: BLE001
            elapsed = time.perf_counter() - t_start
            results[name] = False
            logger.error(
                "❌ %s failed with an exception (%.1f s): %s",
                name, elapsed, exc,
                exc_info=True,
            )

    return results


def print_summary(results: dict[str, bool]) -> None:
    """Prints a final summary table of all pipeline results."""
    logger.info("")
    logger.info("═" * 60)
    logger.info("  SUMMARY")
    logger.info("═" * 60)
    for name, success in results.items():
        status = "✅ OK   " if success else "❌ FAILED"
        logger.info("  %s  %s", status, name)
    logger.info("═" * 60)

    total = len(results)
    passed = sum(results.values())
    failed = total - passed
    logger.info("  Total: %d  |  Passed: %d  |  Failed: %d", total, passed, failed)
    logger.info("═" * 60)


def main() -> None:
    args = parse_args()

    # Apply log level from CLI argument
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Determine which pipelines to run
    selected = args.pipeline if args.pipeline else list(PIPELINES.keys())

    logger.info("B2B dlt Pipeline Orchestrator started")
    logger.info("Selected pipelines: %s", ", ".join(selected))

    results = run_pipelines(selected)
    print_summary(results)

    # Exit with code 1 if any pipeline failed
    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
