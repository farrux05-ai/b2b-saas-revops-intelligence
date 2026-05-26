"""
scripts/vector_ingest.py
========================
Vector Engine — Unstructured Data Ingestion Pipeline

WHAT THIS DOES (in order):
  1. Load       — Read JSON files with Polars (lazy, memory-efficient)
  2. Clean      — Strip whitespace, remove HTML artifacts, drop nulls
  3. Chunk      — Split text into units based on data type:
                  * Sales notes    → 1 note = 1 chunk (document-level)
                  * Zendesk        → 1 comment = 1 chunk (message-level)
                  * Gong           → 1 speaker segment = 1 chunk (speaker-turn)
  4. Enrich     — JOIN with dim_accounts via DuckDB to add MRR, segment, health_score
  5. Embed      — Encode text with BAAI/bge-small-en-v1.5 (local, 130MB, free)
  6. Write      — Upsert into LanceDB tables, create HNSW index for fast ANN search

WHY THESE CHOICES:
  - Polars: handles large JSONs lazily without loading entire file into RAM
  - bge-small-en-v1.5: retrieval-optimized (not just similarity), understands B2B revenue
    language ("MRR at risk", "churn signal"), 384-dim vectors, local/free
  - LanceDB: file-based (no server), Arrow-native (compatible with DuckDB/Polars),
    supports hybrid ANN + SQL WHERE filtering, zero ops overhead
  - DuckDB for enrichment only: structured JOIN is where SQL shines — not text processing

USAGE:
  # Run standalone (for testing):
  python scripts/vector_ingest.py

  # Called from Dagster asset (see dagster_pipeline.py):
  from scripts.vector_ingest import run as run_vector_ingest

OUTPUT:
  duckdb/lancedb/
  ├── sales_notes.lance
  ├── support_conversations.lance
  └── call_transcripts.lance
"""

import json
import re
import os
from pathlib import Path
from typing import Any

import duckdb
import polars as pl

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent.resolve()
UNSTRUCTURED_DIR = ROOT_DIR / "data" / "raw" / "unstructured"
DUCKDB_PATH = ROOT_DIR / "duckdb" / "revops_intelligence.duckdb"
LANCEDB_DIR = ROOT_DIR / "duckdb" / "lancedb"

SALES_NOTES_FILE = UNSTRUCTURED_DIR / "hubspot_sales_notes.json"
ZENDESK_FILE = UNSTRUCTURED_DIR / "zendesk_ticket_comments.json"
GONG_FILE = UNSTRUCTURED_DIR / "gong_call_transcripts.json"

# ── Embedding Model ────────────────────────────────────────────────────────────
MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384

# BGE models require this prefix on QUERY strings (not on documents being indexed).
# Documents are embedded as-is. Queries get the prefix so the model knows the context.
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# ==============================================================================
# STEP 1 + 2: Load & Clean
# ==============================================================================

def _clean_text(text: str) -> str:
    """
    Strips HTML tags, normalizes whitespace, and trims the string.
    Sales notes from HubSpot sometimes contain <p> and <br> tags from rich text editors.
    """
    if not text:
        return ""
    # Remove HTML tags: <p>text</p> → text
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse multiple spaces/newlines into a single space
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_sales_notes() -> list[dict]:
    """
    Loads HubSpot sales notes from JSON.
    Strategy: document-level chunking (1 note = 1 chunk).
    Each note is already short (~200 tokens) so no splitting needed.
    Returns a flat list of chunk dicts ready for embedding.
    """
    with open(SALES_NOTES_FILE, "r") as f:
        records = json.load(f)

    chunks = []
    for rec in records:
        body = _clean_text(rec.get("body", ""))
        if not body or len(body.split()) < 5:
            continue  # skip empty or trivially short notes

        chunks.append({
            "id":           rec.get("hs_engagement_id", ""),
            "text":         body,
            "company_id":   str(rec.get("associated_company_id", "")),
            "company_name": rec.get("associated_company_name", ""),
            "owner_name":   rec.get("owner_name", ""),
            "sentiment":    rec.get("sentiment", ""),
            "tags":         json.dumps(rec.get("tags", [])),  # store as JSON string
            "deal_amount":  float(rec.get("deal_amount") or 0.0),
            "created_at":   rec.get("created_at", ""),
            "source":       "sales_note",
            # These will be filled in Step 4 (DuckDB enrich). Default = None.
            "mrr":          None,
            "health_score": None,
            "segment":      rec.get("segment", ""),  # already present in raw data
        })

    print(f"  [sales_notes] Loaded {len(chunks)} chunks from {len(records)} records")
    return chunks


def load_support_conversations() -> list[dict]:
    """
    Loads Zendesk ticket comments from JSON.
    Strategy: message-level chunking (1 comment = 1 chunk).
    Why: each comment has a different author (end_user vs agent). Mixing them destroys
    the ability to query "what did the customer complain about?" vs "how did support respond?".
    """
    with open(ZENDESK_FILE, "r") as f:
        records = json.load(f)

    chunks = []
    for ticket in records:
        ticket_id = str(ticket.get("ticket_id", ""))
        company_id = str(ticket.get("associated_company_id", ""))
        topic = ticket.get("topic", "")
        priority = ticket.get("priority", "normal")
        created_at = ticket.get("created_at", "")

        for comment in ticket.get("comments", []):
            body = _clean_text(comment.get("body", ""))
            if not body or len(body.split()) < 5:
                continue

            chunks.append({
                "id":          f"{ticket_id}_{comment.get('comment_id', '')}",
                "text":        body,
                "ticket_id":   ticket_id,
                "company_id":  company_id,
                "author_type": comment.get("author_type", ""),  # "end_user" | "agent"
                "topic":       topic,
                "priority":    priority,
                "sentiment":   comment.get("sentiment", ""),
                "created_at":  created_at,
                "source":      "support_comment",
                # Filled in Step 4
                "mrr":         None,
                "health_score": None,
                "segment":     "",
            })

    print(f"  [support_conversations] Loaded {len(chunks)} chunks from {len(records)} tickets")
    return chunks


def load_call_transcripts() -> list[dict]:
    """
    Loads Gong call transcripts from JSON.
    Strategy: speaker-turn chunking (1 speaker segment = 1 chunk).
    Why: Gong provides pre-segmented transcript blocks per speaker. Preserving speaker
    identity allows queries like "what objections did the prospect raise?".
    Segments with < 10 words are skipped (filler words, short acks like "Sure", "Mm-hmm").
    """
    with open(GONG_FILE, "r") as f:
        records = json.load(f)

    chunks = []
    for call in records:
        call_id = str(call.get("call_id", ""))
        company_id = str(call.get("associated_company_id", ""))
        call_type = call.get("call_type", "")
        call_date = call.get("call_date", "")
        company_name = call.get("associated_company_name", "")
        duration = float(call.get("duration_minutes") or 0.0)
        sentiment = call.get("sentiment", "")

        for segment in call.get("transcript", []):
            # Each segment: {"speakerId": "spk_rep", "sentences": [{"text": "...", ...}]}
            sentences = segment.get("sentences", [])
            segment_text = " ".join(s.get("text", "") for s in sentences)
            segment_text = _clean_text(segment_text)

            if len(segment_text.split()) < 10:
                continue  # skip very short filler segments

            chunks.append({
                "id":               f"{call_id}_{segment.get('speakerId', '')}_{len(chunks)}",
                "text":             segment_text,
                "call_id":          call_id,
                "company_id":       company_id,
                "company_name":     company_name,
                "speaker_id":       segment.get("speakerId", ""),
                "call_type":        call_type,
                "call_date":        call_date,
                "duration_minutes": duration,
                "sentiment":        sentiment,
                "source":           "call_transcript",
                # Filled in Step 4
                "mrr":              None,
                "health_score":     None,
                "segment":          "",
            })

    print(f"  [call_transcripts] Loaded {len(chunks)} chunks from {len(records)} calls")
    return chunks


# ==============================================================================
# STEP 4: Enrich with DuckDB (JOIN dim_accounts)
# ==============================================================================

def enrich_with_dim_accounts(chunks: list[dict], duckdb_path: str) -> list[dict]:
    """
    JOINs chunks with dim_accounts to attach structured RevOps context:
      - mrr: monthly recurring revenue (how valuable is this account?)
      - health_score: 0–100 score (how risky is this account?)
      - segment: at_risk | expansion | pql | healthy (what category?)

    WHY: When searching for "billing complaints at high-MRR accounts", we need to
    filter by mrr > X. Without enrichment, that filter is impossible because mrr
    lives only in dim_accounts (structured layer), not in the raw JSON files.

    FALLBACK: If dim_accounts doesn't exist (dbt hasn't run yet), the function
    returns chunks unchanged with mrr=None. Vector ingestion still works — just
    without the structured filters. Log a warning.
    """
    try:
        con = duckdb.connect(str(duckdb_path), read_only=True)

        # Check if dim_accounts exists
        tables = con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_name = 'dim_accounts'"
        ).fetchall()

        if not tables:
            print("  ⚠️  dim_accounts not found in DuckDB. Skipping enrichment.")
            print("     Run dbt build first to create mart tables.")
            con.close()
            return chunks

        # Build a lookup dict: company_id → {mrr, health_score, segment}
        rows = con.execute("""
            SELECT
                hubspot_company_id,
                mrr,
                health_score,
                segment
            FROM main_marts.dim_accounts
            WHERE hubspot_company_id IS NOT NULL
        """).fetchall()
        con.close()

        # Map company_id → enrichment data
        account_map: dict[str, dict] = {}
        for row in rows:
            account_map[str(row[0])] = {
                "mrr":          float(row[1]) if row[1] is not None else None,
                "health_score": float(row[2]) if row[2] is not None else None,
                "segment":      row[3] or "",
            }

        # Apply enrichment
        enriched_count = 0
        for chunk in chunks:
            cid = chunk.get("company_id", "")
            if cid in account_map:
                chunk["mrr"]          = account_map[cid]["mrr"]
                chunk["health_score"] = account_map[cid]["health_score"]
                # Only override segment if raw data didn't have it
                if not chunk.get("segment"):
                    chunk["segment"] = account_map[cid]["segment"]
                enriched_count += 1

        print(f"  [enrich] Enriched {enriched_count}/{len(chunks)} chunks with dim_accounts data")
        return chunks

    except Exception as e:
        print(f"  ⚠️  Enrichment failed: {e}. Continuing without MRR/health_score.")
        return chunks


# ==============================================================================
# STEP 5: Embed
# ==============================================================================

def get_embedding_model():
    """
    Loads BAAI/bge-small-en-v1.5 from HuggingFace (cached after first download).
    130MB download on first run. Subsequent runs use local cache in ~/.cache/huggingface/.

    BGE-specific: when embedding DOCUMENTS, use raw text.
                  when embedding QUERIES (at search time), prepend BGE_QUERY_PREFIX.
    """
    from sentence_transformers import SentenceTransformer
    print(f"  [embed] Loading model: {MODEL_NAME} (downloading if first time, ~130MB)...")
    model = SentenceTransformer(MODEL_NAME)
    print(f"  [embed] Model loaded. Embedding dim: {EMBED_DIM}")
    return model


def embed_chunks(chunks: list[dict], model) -> list[dict]:
    """
    Encodes the 'text' field of each chunk into a 384-dim vector.
    Runs in batches of 64 for memory efficiency.
    Adds 'vector' field to each chunk dict.
    """
    texts = [c["text"] for c in chunks]
    print(f"  [embed] Encoding {len(texts)} chunks in batches of 64...")

    vectors = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
    )

    for chunk, vec in zip(chunks, vectors):
        chunk["vector"] = vec.tolist()

    print(f"  [embed] Done. Each vector: {len(chunks[0]['vector'])} dims")
    return chunks


# ==============================================================================
# STEP 6: Write to LanceDB
# ==============================================================================

def write_to_lancedb(table_name: str, chunks: list[dict], lancedb_dir: str) -> None:
    """
    Writes embedded chunks to a LanceDB table.
    mode="overwrite" → drops and recreates the table each run (full re-index).
    This is intentionally simple. Incremental updates can be added later using
    a DuckDB metadata table that tracks last-indexed timestamps.

    After writing, creates an HNSW index for fast Approximate Nearest Neighbor search.
    Without an index, search is exact (exhaustive scan) — fine for < 10k docs.
    With an index, search is ~100x faster via HNSW graph traversal.
    """
    import lancedb

    os.makedirs(lancedb_dir, exist_ok=True)
    db = lancedb.connect(lancedb_dir)

    # LanceDB accepts a list of dicts directly. It infers the schema.
    # The 'vector' field (list of floats) is automatically treated as the vector column.
    table = db.create_table(table_name, data=chunks, mode="overwrite")

    # Create IVF_PQ index (fast ANN). For < 5k docs, exact search is fine too.
    # IVF_PQ requires at least 256 rows. Skip if dataset is tiny.
    if len(chunks) >= 256:
        table.create_index(
            metric="cosine",       # cosine similarity for text embeddings
            num_partitions=32,     # IVF partitions
            num_sub_vectors=16,    # PQ sub-vector count
        )
        print(f"  [lancedb] Table '{table_name}': {len(chunks)} records + IVF_PQ index created")
    else:
        print(f"  [lancedb] Table '{table_name}': {len(chunks)} records (no index, dataset too small)")


# ==============================================================================
# MAIN PIPELINE
# ==============================================================================

def run(duckdb_path: str | None = None, lancedb_dir: str | None = None) -> dict[str, int]:
    """
    Main entry point. Runs the full vector ingestion pipeline for all 3 data sources.

    Args:
        duckdb_path: Path to the DuckDB file. Defaults to ROOT_DIR/duckdb/revops_intelligence.duckdb
        lancedb_dir: Directory to store LanceDB tables. Defaults to ROOT_DIR/duckdb/lancedb

    Returns:
        Dict with record counts per table: {"sales_notes": N, "support_conversations": M, ...}

    Called from:
        - Dagster asset: `vector_ingest` in dagster_pipeline.py
        - CLI: python scripts/vector_ingest.py
    """
    _duckdb = duckdb_path or str(DUCKDB_PATH)
    _lancedb = lancedb_dir or str(LANCEDB_DIR)

    print("=" * 60)
    print("Vector Ingest Pipeline — B2B SaaS RevOps")
    print("=" * 60)

    # ── Step 1+2: Load & Clean ─────────────────────────────────────────────
    print("\n[Step 1+2] Loading and cleaning unstructured data...")
    sales_chunks   = load_sales_notes()
    support_chunks = load_support_conversations()
    call_chunks    = load_call_transcripts()

    total = len(sales_chunks) + len(support_chunks) + len(call_chunks)
    print(f"\n  Total chunks: {total}")

    # ── Step 4: Enrich ────────────────────────────────────────────────────
    print("\n[Step 4] Enriching with dim_accounts (MRR, health_score, segment)...")
    sales_chunks   = enrich_with_dim_accounts(sales_chunks, _duckdb)
    support_chunks = enrich_with_dim_accounts(support_chunks, _duckdb)
    call_chunks    = enrich_with_dim_accounts(call_chunks, _duckdb)

    # ── Step 5: Embed ─────────────────────────────────────────────────────
    print("\n[Step 5] Loading embedding model...")
    model = get_embedding_model()

    print("\n  Embedding sales_notes...")
    sales_chunks = embed_chunks(sales_chunks, model)

    print("\n  Embedding support_conversations...")
    support_chunks = embed_chunks(support_chunks, model)

    print("\n  Embedding call_transcripts...")
    call_chunks = embed_chunks(call_chunks, model)

    # ── Step 6: Write to LanceDB ──────────────────────────────────────────
    print(f"\n[Step 6] Writing to LanceDB at: {_lancedb}")
    write_to_lancedb("sales_notes",           sales_chunks,   _lancedb)
    write_to_lancedb("support_conversations", support_chunks, _lancedb)
    write_to_lancedb("call_transcripts",      call_chunks,    _lancedb)

    print("\n" + "=" * 60)
    print("✅ Vector ingestion complete!")
    print(f"   sales_notes:           {len(sales_chunks)} chunks")
    print(f"   support_conversations: {len(support_chunks)} chunks")
    print(f"   call_transcripts:      {len(call_chunks)} chunks")
    print(f"   LanceDB location:      {_lancedb}")
    print("=" * 60)

    return {
        "sales_notes":           len(sales_chunks),
        "support_conversations": len(support_chunks),
        "call_transcripts":      len(call_chunks),
    }


# Run directly for testing
if __name__ == "__main__":
    counts = run()
