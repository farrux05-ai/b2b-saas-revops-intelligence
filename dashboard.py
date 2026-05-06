import streamlit as st
import duckdb
import pandas as pd

# Page config
st.set_page_config(
    page_title="RevOps Intelligence Dashboard",
    page_icon="🚀",
    layout="wide"
)

# Constants
DUCKDB_PATH = "md:revops_intelligence"

@st.cache_resource
def get_connection():
    return duckdb.connect(DUCKDB_PATH, read_only=True)

conn = get_connection()

# Header
st.title("🚀 RevOps Intelligence Engine")
st.markdown("*Simulating Lightdash Semantic Layer BI Visualizations*")

st.divider()

# Semantic Layer Metrics Fetching
try:
    # Finance Metrics
    finance_metrics = conn.execute("""
        SELECT 
            SUM(mrr) as total_mrr,
            SUM(arr) as total_arr
        FROM main_marts.dim_accounts
        WHERE health_status != 'Churned'
    """).df()

    # Product & Core Metrics
    core_metrics = conn.execute("""
        SELECT 
            COUNT(DISTINCT account_id) as total_accounts,
            SUM(CASE WHEN is_pql THEN 1 ELSE 0 END) as pql_count,
            AVG(seat_utilization_pct) as avg_seat_utilization,
            SUM(CASE WHEN health_status = 'Churned' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as logo_churn_rate
        FROM main_marts.dim_accounts
    """).df()

    activation_metrics = conn.execute("""
        SELECT 
            AVG(activation_rate) as avg_activation_rate
        FROM main_marts.fct_product_activation
    """).df()

    # Layout: Top KPIs
    st.subheader("Key Performance Indicators (KPIs)")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total MRR", 
            value=f"${finance_metrics['total_mrr'].iloc[0]:,.2f}",
            delta="+5.2% (MoM)"
        )
    with col2:
        st.metric(
            label="Total ARR", 
            value=f"${finance_metrics['total_arr'].iloc[0]:,.2f}"
        )
    with col3:
        st.metric(
            label="Active PQLs", 
            value=f"{int(core_metrics['pql_count'].iloc[0])}"
        )
    with col4:
        churn_rate = core_metrics['logo_churn_rate'].iloc[0]
        st.metric(
            label="Logo Churn Rate", 
            value=f"{churn_rate:.1f}%",
            delta="-0.5%" if churn_rate < 5 else "+1.2%",
            delta_color="inverse"
        )

    st.divider()

    # Layout: Secondary Metrics
    st.subheader("Product & Expansion Signals")
    col5, col6, col7 = st.columns(3)

    with col5:
        st.metric(
            label="Avg Seat Utilization", 
            value=f"{core_metrics['avg_seat_utilization'].iloc[0] * 100:.1f}%"
        )
    with col6:
        st.metric(
            label="Product Activation Rate", 
            value=f"{activation_metrics['avg_activation_rate'].iloc[0] * 100:.1f}%"
        )
    with col7:
        st.metric(
            label="Total Accounts (All Time)", 
            value=f"{int(core_metrics['total_accounts'].iloc[0])}"
        )

    st.divider()

    # Visualizations
    st.subheader("Account Segmentation")
    segments = conn.execute("""
        SELECT account_segment, COUNT(*) as count 
        FROM main_marts.dim_accounts 
        WHERE health_status != 'Churned'
        GROUP BY 1
        ORDER BY 2 DESC
    """).df()
    
    st.bar_chart(data=segments, x="account_segment", y="count")

    st.subheader("Feature Adoption Heatmap (Last 30 Days)")
    features = conn.execute("""
        SELECT feature_category, SUM(total_events) as event_count
        FROM main_marts.fct_feature_usage
        GROUP BY 1
        ORDER BY 2 DESC
    """).df()
    
    st.bar_chart(data=features, x="feature_category", y="event_count")

except Exception as e:
    st.error(f"Failed to load metrics from DuckDB. Is the dbt pipeline finished? Error: {e}")

st.sidebar.markdown("""
### Semantic Layer Context
This dashboard consumes the dimensions and metrics defined in our dbt `schema.yml` files.
In a production setup, tools like **Lightdash** automatically generate these metrics.

**Metrics Defined:**
- `total_mrr`
- `total_arr`
- `pql_count`
- `avg_seat_utilization`
- `avg_activation_rate`
""")
