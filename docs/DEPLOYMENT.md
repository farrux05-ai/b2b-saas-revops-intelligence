# Deployment Guide: RevOps Pipeline & Analytics

This guide provides a "Modeling-First" approach to deploying your dbt documentation and Streamlit dashboards. Since this project focuses on data modeling rather than extraction/orchestration, we prioritize simplicity and manual builds over complex CI/CD pipelines.

---

## 1. dbt Documentation Deployment

The dbt documentation consists of static HTML and JSON files. You have two main options:

### Option A: Single-File HTML (Recommended for Sharing)
Generating a single HTML file is the easiest way to share the full documentation via email or Slack without needing a server.

1.  Navigate to your dbt project:
    ```bash
    cd revops_pipeline/revops_project
    ```
2.  Install the `dbt-docs-to-single-file` tool:
    ```bash
    pip install dbt-docs-to-single-file
    ```
3.  Generate the docs and merge them into one file:
    ```bash
    dbt docs generate
    python -m dbt_docs_to_single_file --target-dir target --output docs.html
    ```
4.  **Result**: You now have a `docs.html` file that you can open in any browser or send to colleagues.

### Option B: GitHub Pages (Automatic)
Your project is already configured to deploy dbt docs to GitHub Pages on every push to the `main` branch.
- **URL**: https://farrux05-ai.github.io/b2b-saas-revops/

---

## 2. Streamlit Dashboard Deployment

The primary dashboard is built with Streamlit and can be hosted for free on Streamlit Cloud.

### Option A: Streamlit Cloud (Recommended)
1.  Push your code to GitHub.
2.  Go to [share.streamlit.io](https://share.streamlit.io/).
3.  Connect your repository (`b2b-saas-revops`).
4.  Set the main file path to `revops_project/dashboard.py`.
5.  **Important**: Ensure `revops_project/requirements.txt` is present so Streamlit can install dependencies.
6.  **DuckDB File**: Since DuckDB is a local file, it will be bundled with your app. On every deployment, it will state the contents of the `.duckdb` file you pushed.

---

## 3. Maintenance & Updates

Since you are not using GitHub Workflows for orchestration:
1.  **Update Data**: Run `dbt run` and `dbt snapshot` locally.
2.  **Update Docs**: Run `dbt docs generate` and push to GitHub.
3.  **Update Dashboard**: Commit the updated `.duckdb` file and `dashboard.py` and push to GitHub. Streamlit Cloud will automatically reboot with the new data.

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'streamlit'"**
- Ensure you have activated your virtual environment: `source dbt-venv/bin/activate`
- Run `pip install -r requirements.txt` again.

**"DuckDB Error: table not found"**
- Ensure you have run `dbt run` to build the tables in the DuckDB file before launching the dashboard.
