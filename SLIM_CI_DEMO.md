# ⚡ dbt Slim CI & Continuous Integration (CI/CD) Demo Guide

> **Goal:** Demonstrate how dbt Slim CI dramatically accelerates CI/CD pipeline execution by compiling and testing **only modified models and their downstream dependencies**, using state deferral against Snowflake.

---

## 💡 What is dbt Slim CI?

| Standard CI | dbt Slim CI (State Deferral) |
|-------------|------------------------------|
| ❌ Rebuilds all 69 models from scratch | ✅ Builds **only modified models** (e.g. 1 or 2 models) |
| ❌ Runs all 200+ data quality tests | ✅ Runs tests **only for affected models** |
| ⏱️ Takes **3 to 5 minutes** per PR | ⏱️ Takes **10 to 15 seconds** per PR |
| 💸 High Snowflake warehouse compute cost | 💰 **90%+ reduction** in Snowflake compute cost |

---

## 🎬 Demo 1: Local Terminal Simulation (2-Minute Live Demo)

You can demonstrate Slim CI directly on your machine without opening a GitHub PR.

### Step 1: Save the Baseline State (Simulate Production `main`)
```bash
# 1. Parse project and save production manifest into ./state
dbt parse --target snowflake
mkdir -p state
cp target/manifest.json state/manifest.json
```

### Step 2: Make a 1-Line Change in 1 Model
Open `models/marts/sales/fct_pipeline.sql` and add a comment or edit a column alias.

### Step 3: Execute Slim CI Command
```bash
dbt build --target ci --select state:modified+ --defer --state ./state --store-failures
```

### 🎯 Expected Demo Natija / Output:
```
16:15:02  Found 69 models, 200 data tests...
16:15:03  Selected 1 modified model:
16:15:03    - fct_pipeline
16:15:03  Deferring 68 unmodified models to production schema (REVOPS_INTELLIGENCE.MARTS)
16:15:03
16:15:03  1 of 1 START sql table model MARTS_CI.fct_pipeline ......... [RUN]
16:15:05  1 of 1 OK created sql table model MARTS_CI.fct_pipeline .... [SUCCESS in 2.1s]
16:15:06  Done. PASS=1 WARN=0 ERROR=0 SKIP=0 TOTAL=1
```
> **Key Point:** 68 models were deferred to `MARTS`. Only 1 model was compiled and tested in `MARTS_CI`!

---

## 🐙 Demo 2: Real GitHub Actions PR Demo (CI/CD Pipeline)

Follow these steps to demonstrate real GitHub Actions automation to your team:

### Step 1: Create a Feature Branch
```bash
git checkout -b feature/optimize-mrr-waterfall
```

### Step 2: Modify a SQL Model
Make a minor edit in `models/marts/finance/fct_mrr_waterfall.sql`.

### Step 3: Commit & Push to GitHub
```bash
git add models/marts/finance/fct_mrr_waterfall.sql
git commit -m "feat(finance): optimize mrr waterfall query"
git push origin feature/optimize-mrr-waterfall
```

### Step 4: Open a Pull Request on GitHub
1. Navigate to your GitHub repository: `https://github.com/farrux05-ai/b2b-saas-revops-intelligence`
2. Click **Compare & pull request**.
3. Create the Pull Request.

### Step 5: Show the Live GitHub Actions Workflow Execution
1. Click on the **Checks** tab or the workflow status link on the PR.
2. Watch `.github/workflows/dbt_slim_ci.yml` run:
   - 📥 **Checkout Repository**
   - 📂 **Download Main Branch Manifest**
   - 🚀 **Run dbt Slim CI (`state:modified+`)**
   - 🛡️ **Elementary Data Observability Checks**
3. Point out the green checkmark ✅ and show that execution completed in seconds!

---

## 🔑 Summary of Best Practices Used

1. **State Deferral (`--defer --state ./state`)**: Unmodified upstream tables are resolved directly from `REVOPS_INTELLIGENCE.MARTS`.
2. **Isolated CI Schema (`MARTS_CI`)**: PR builds execute safely in `MARTS_CI` without touching production data.
3. **Automatic Artifact Caching**: Main branch merges automatically upload `target/manifest.json` for future PR Slim CI runs.
