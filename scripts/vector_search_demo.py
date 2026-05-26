"""
scripts/vector_search_demo.py
============================
Vector Engine — Semantic Search Demo & Verification Script

This script allows you to query the local LanceDB vector database to retrieve
semantically similar unstructured documents (sales notes, support tickets, and call transcripts)
and shows how they are enriched with structured metrics (MRR, health score).

USAGE:
  # Search all sources:
  python scripts/vector_search_demo.py "billing issues and customer complaints"

  # Search with a filter (e.g. only high MRR accounts):
  python scripts/vector_search_demo.py "at risk of churn" --min-mrr 5000
"""

import sys
import argparse
from pathlib import Path
import lancedb

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent.resolve()
LANCEDB_DIR = ROOT_DIR / "duckdb" / "lancedb"

# Model configuration (must match vector_ingest.py)
MODEL_NAME = "BAAI/bge-small-en-v1.5"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def get_embedding_model():
    """Loads BGE-small embedding model locally (uses cache)."""
    from sentence_transformers import SentenceTransformer
    print(f"Loading local embedding model ({MODEL_NAME})...")
    return SentenceTransformer(MODEL_NAME)


def search_table(table, query_vector, limit=3, min_mrr=None, source_name=""):
    """
    Queries a LanceDB table using a vector search.
    Supports optional metadata filtering (e.g. MRR).
    """
    # 1. Start building the vector search query
    search_query = table.search(query_vector).metric("cosine").limit(limit)

    # 2. Add SQL-like metadata filtering if requested
    if min_mrr is not None:
        # LanceDB supports SQL-like where clauses natively
        search_query = search_query.where(f"mrr >= {min_mrr}")

    results = search_query.to_list()
    return results


def run_search(query_text: str, limit: int = 3, min_mrr: float = None):
    # 1. Initialize LanceDB connection
    if not LANCEDB_DIR.exists():
        print(f"Error: LanceDB directory does not exist at {LANCEDB_DIR}")
        print("Please run scripts/vector_ingest.py first to create the tables.")
        return

    db = lancedb.connect(str(LANCEDB_DIR))
    tables = db.table_names()
    print(f"Found LanceDB tables: {tables}")

    if not tables:
        print("Error: LanceDB contains no tables. Please run ingestion first.")
        return

    # 2. Load model and embed the query
    # Critical: BGE models require a special prefix on query strings!
    prefixed_query = BGE_QUERY_PREFIX + query_text
    model = get_embedding_model()
    print(f"Embedding query: '{query_text}'...")
    query_vector = model.encode(prefixed_query).tolist()

    # 3. Search each table and display results
    print("\n" + "=" * 80)
    print(f"SEMANTIC SEARCH RESULTS FOR: '{query_text}'")
    if min_mrr is not None:
        print(f"FILTER: MRR >= ${min_mrr}")
    print("=" * 80)

    for table_name in ["sales_notes", "support_conversations", "call_transcripts"]:
        if table_name not in tables:
            print(f"\n[Source: {table_name}] — Table not found, skipping.")
            continue

        table = db.open_table(table_name)
        results = search_table(table, query_vector, limit=limit, min_mrr=min_mrr)

        print(f"\n=== SOURCE: {table_name.upper()} (Top {len(results)} matches) ===")

        if not results:
            print("  No matching documents found.")
            continue

        for i, match in enumerate(results, start=1):
            similarity = 1.0 - match.get("_distance", 1.0)  # cosine distance to similarity
            text = match.get("text", "")
            snippet = text[:250] + "..." if len(text) > 250 else text

            # Account Metadata
            company_name = match.get("company_name", "Unknown")
            company_id = match.get("company_id", "Unknown")
            mrr = match.get("mrr")
            mrr_str = f"${mrr:,.2f}" if mrr is not None else "N/A"
            health = match.get("health_score")
            health_str = f"{health:.0f}/100" if health is not None else "N/A"
            segment = match.get("segment") or "N/A"

            print(f"\n  {i}. Match [Similarity: {similarity:.4f}]")
            if table_name == "sales_notes":
                print(f"     Company: {company_name} (ID: {company_id}) | Segment: {segment}")
                print(f"     MRR: {mrr_str} | Health: {health_str} | Owner: {match.get('owner_name', 'N/A')}")
                print(f"     Sentiment: {match.get('sentiment', 'N/A')} | Date: {match.get('created_at', 'N/A')}")
            elif table_name == "support_conversations":
                print(f"     Ticket ID: {match.get('ticket_id', 'N/A')} | Company ID: {company_id}")
                print(f"     MRR: {mrr_str} | Health: {health_str} | Topic: {match.get('topic', 'N/A')}")
                print(f"     Priority: {match.get('priority', 'N/A')} | Sender: {match.get('author_type', 'N/A')}")
            elif table_name == "call_transcripts":
                print(f"     Company: {company_name} (ID: {company_id}) | Speaker: {match.get('speaker_id', 'N/A')}")
                print(f"     MRR: {mrr_str} | Health: {health_str} | Call Type: {match.get('call_type', 'N/A')}")
                print(f"     Date: {match.get('call_date', 'N/A')} | Duration: {match.get('duration_minutes', 0.0):.1f} min")

            print(f"     Snippet: \"{snippet}\"")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query LanceDB vector database")
    parser.add_argument("query", type=str, help="The semantic query to search for")
    parser.add_argument("--limit", type=int, default=3, help="Max results per table")
    parser.add_argument("--min-mrr", type=float, default=None, help="Filter: Minimum MRR of company")

    args = parser.parse_args()
    run_search(args.query, limit=args.limit, min_mrr=args.min_mrr)
