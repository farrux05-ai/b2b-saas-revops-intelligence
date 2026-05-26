# Vector Engine — Build Log & Decision Record

> **Purpose:** A living document that records every decision made, why it was made,
> and what each step does. Written for future-you who needs to understand this in 6 months.

---

## Project Context

We are building a **semantic search layer** on top of the existing B2B SaaS RevOps pipeline.

The existing pipeline handles **structured data** (MRR, health scores, seat utilization) via:
`JSON → dlt → DuckDB → dbt → marts → MotherDuck → Lightdash`

The new layer handles **unstructured data** (sales notes, support tickets, call transcripts) via:
`JSON → Polars (clean) → DuckDB JOIN (enrich) → Embed (bge-small) → LanceDB`

These two layers will eventually be queried together to give a **full picture of an account**.

---

## Architecture Decision: Why NOT put unstructured data through dbt?

| Capability | dbt/SQL | Python/Polars |
|---|---|---|
| Clean raw text (strip HTML, whitespace) | ❌ Painful | ✅ Natural |
| Regex / NLP preprocessing | ❌ No native regex | ✅ Full support |
| Chunking (split text into segments) | ❌ Impossible | ✅ Pure Python |
| Generate embeddings (384-dim vectors) | ❌ Impossible | ✅ sentence-transformers |
| Write to LanceDB | ❌ Impossible | ✅ Native API |
| Structured metadata JOIN | ✅ Ideal | ✅ Also works (DuckDB in Python) |

**Decision:** Python-only pipeline for unstructured data. SQL (dbt/DuckDB) is used only
for one thing: joining `dim_accounts` metadata (MRR, segment, health_score) onto chunks.

---

## Architecture Decision: Why LanceDB?

Options considered:
- **Pinecone** – Cloud-only, costs money, needs internet. ❌
- **Weaviate** – Docker required, heavy ops. ❌
- **Chroma** – Good for experiments, less mature for production. ⚠️
- **pgvector** – Requires Postgres, we are DuckDB-first. ❌
- **LanceDB** – Local file-based, columnar (Apache Arrow), DuckDB-compatible, zero ops. ✅

**Why LanceDB wins for us:**
1. Stores data as `.lance` files on disk — same philosophy as `.duckdb` files
2. Natively reads/writes Apache Arrow (same as DuckDB and Polars)
3. Supports hybrid search: ANN vector search + SQL WHERE filters
4. No server to run — just a directory
5. Can be cloud-synced to S3/R2 later without code changes

---

## Architecture Decision: Why `BAAI/bge-small-en-v1.5` for embeddings?

Options considered:
| Model | Size | Cost | Quality (RevOps) |
|---|---|---|---|
| `all-MiniLM-L6-v2` | 80MB | Free/local | Good (general purpose) |
| `BAAI/bge-small-en-v1.5` | 130MB | Free/local | **Best** (retrieval-optimized) |
| `text-embedding-3-small` | API | $0.02/1M tokens | Best (needs OpenAI API) |

**Why BGE wins:**
- **Retrieval-tuned**: trained specifically for search tasks (not just semantic similarity)
- Understands B2B revenue language: "MRR at risk", "churn signal", "seat utilization"
- 100% local — no API keys, no internet required, runs inside Dagster assets
- 384 dimensions: small enough to be fast, large enough to be accurate
- BGE requires a `query_prefix` for search queries: `"Represent this sentence for searching relevant passages: "`

---

## Architecture Decision: Chunking Strategy

Different data types need different chunking because of their structure:

| Data Type | Strategy | Why |
|---|---|---|
| HubSpot Sales Notes | **Document-level** (1 note = 1 chunk) | Notes are ~200 tokens. Full context matters. No splitting needed. |
| Zendesk Ticket Comments | **Message-level** (1 comment = 1 chunk) | Each comment has a different author (agent vs customer). Mixing them loses signal. |
| Gong Call Transcripts | **Speaker-turn** (1 segment = 1 chunk) | Speaker diarization must be preserved. "Did the prospect say X?" requires speaker-level chunks. |

**Token limit rule:**
- If a chunk < 400 tokens → keep as-is (document level)
- If a chunk > 400 tokens → split recursively with 50-token overlap

---

## Architecture Decision: Where does this fit in Dagster?

```
ingestion_dlt            → Layer 1: Load JSON → DuckDB raw_data
revops_dbt_assets        → Layer 2: Transform raw → dim_accounts, fct_*
vector_ingest  [NEW]     → Layer 3: Unstructured JSON + dim_accounts → LanceDB
motherduck_sync          → Layer 4: DuckDB → MotherDuck Cloud
dlt_reverse_etl          → Layer 5: marts → HubSpot CRM
elementary_report        → Layer 6: Observability report
```

`vector_ingest` has `deps=[revops_dbt_assets]` because it reads `dim_accounts`
from the marts layer to enrich chunks with MRR, segment, health_score.

---

## Architecture Decision: Slack / LLM Integration (Future)

The user has a Lightdash AI agent connected to Slack. That agent handles
structured queries (MetricFlow semantic layer → DuckDB → numbers).

For unstructured queries (sales context, support history, call excerpts), two paths:

**Option A (current — simple):** Two separate bots.
- Lightdash AI: handles metric questions ("What is Acme's MRR?")
- Our LanceDB bot (future): handles signal questions ("What did Acme's CTO complain about?")

**Option B (later — unified):** Single LLM router (LangChain or plain Python).
- One Slack bot receives all questions
- LLM classifies: structured → call Lightdash/MetricFlow API, unstructured → query LanceDB
- Returns combined answer

**Decision:** Build Option A first. Prove the vector search works. Then unify.
Reason: "Get the foundation right. APIs are just plumbing." — engineer principle.

---

## Build Steps (executed in order)

### Step 0: Research & Planning ✅
- Read existing data files
- Confirmed `hubspot_company_id` is the join key between unstructured and `dim_accounts`
- Confirmed 3 source files: sales_notes (159 docs), zendesk (172 tickets), gong (99 calls)

### Step 1: Update `requirements.txt` & Setup Environment with `uv` ✅
Added:
- `lancedb` — vector database
- `sentence-transformers` — local embedding model (BGE)
- `pyarrow` — required by LanceDB for Arrow schema
- `polars` — fast columnar DataFrame for JSON loading and text cleaning

Using `uv` for ultra-fast, parallel package installation:
```bash
# Verify uv is installed
uv --version

# Install remaining dependencies with uv
uv pip install sentence-transformers
# Or sync all requirements:
uv pip install -r requirements.txt
```

### Step 2: Write `scripts/vector_ingest.py` ✅
The core ingestion script. Does:
1. Load each JSON file with `polars` (lazy, memory-efficient)
2. Clean text: strip whitespace, remove null/empty bodies
3. Chunk: per-strategy per data type
4. Enrich: JOIN with `dim_accounts` via DuckDB to get MRR, segment, health_score
5. Embed: batch encode with `bge-small-en-v1.5` (64 docs/batch)
6. Write: `lancedb.connect()` → `create_table(mode="overwrite")` → `add(records)`
7. Index: `create_index()` for ANN search

### Step 3: Add `vector_ingest` Dagster asset ✅ (in progress)
In `dagster_pipeline.py`:
- New `@asset` with `group_name="vector"`, `deps=[revops_dbt_assets]`
- Calls `run_vector_ingest()` from `scripts.vector_ingest`

### Step 4: Verify — Run search demo ✅
Script: `scripts/vector_search_demo.py`
Test query: `python scripts/vector_search_demo.py "billing complaint, churn risk, at-risk account"`
Expected: Returns top results from Acme Corp, Brightwave Labs notes + Zendesk tickets

---

## File Map

| File | Status | Description |
|---|---|---|
| `data/raw/unstructured/hubspot_sales_notes.json` | ✅ Exists | 159 HubSpot engagement notes |
| `data/raw/unstructured/zendesk_ticket_comments.json` | ✅ Exists | 172 Zendesk tickets with comments |
| `data/raw/unstructured/gong_call_transcripts.json` | ✅ Exists | 99 Gong call transcripts |
| `requirements.txt` | ✅ Updated | Added lancedb, sentence-transformers, polars, pyarrow |
| `scripts/vector_ingest.py` | ✅ Written | Core pipeline: clean → chunk → embed → LanceDB |
| `scripts/vector_search_demo.py` | ✅ Written | Test queries against LanceDB |
| `dagster_pipeline.py` | ✅ Updated | Added `vector_ingest` asset |
| `duckdb/lancedb/` | 🔲 Auto-created | Created on first run of vector_ingest |

---

## LanceDB Table Schemas

### `sales_notes`
Fields: `vector (384-dim)`, `text`, `id`, `company_id`, `company_name`, `segment`,
`owner_name`, `sentiment`, `tags`, `deal_amount`, `created_at`,
`mrr` (from dim_accounts), `health_score` (from dim_accounts), `source`

### `support_conversations`
Fields: `vector`, `text`, `ticket_id`, `company_id`, `author_type`, `topic`,
`priority`, `sentiment`, `created_at`, `mrr`, `segment`, `source`

### `call_transcripts`
Fields: `vector`, `text`, `call_id`, `call_type`, `company_id`, `company_name`,
`speaker_id`, `segment`, `duration_minutes`, `sentiment`, `call_date`, `mrr`, `source`

---

## Known Limitations (to fix later)

1. **Full re-index on every run**: Simple but slow for large datasets. Fix: add timestamp
   checksum in a DuckDB metadata table, skip unchanged documents.

2. **No de-duplication**: Same note appearing twice will create two vectors. Fix: use
   `hs_engagement_id` as primary key and check before inserting.

3. **CPU-only embedding**: `bge-small-en-v1.5` on CPU = ~5 min for 430 docs. Fine for now.
   Fix: add `device="cuda"` if GPU available, or switch to OpenAI API for sub-1min runs.

4. **LanceDB is local only**: Files live in `duckdb/lancedb/`. Not synced to MotherDuck.
   Fix: mount to S3/Cloudflare R2 using LanceDB's built-in remote support.

5. **No Slack integration yet**: This is intentional. Prove the search works first.
