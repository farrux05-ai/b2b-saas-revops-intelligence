import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import duckdb
from datetime import datetime
import json
import os

# ============================================
# CONFIGURATION & THEME
# ============================================
st.set_page_config(
    page_title="RevOps Intelligence | Series A Engine",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Look
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    [data-testid="stMetricValue"] {
        font-size: 2.2rem;
        font-weight: 700;
        color: #00d4ff;
    }
    .metric-card {
        background-color: #1e293b;
        padding: 1.5rem;
        border-radius: 0.75rem;
        border-left: 5px solid #3b82f6;
        margin-bottom: 1rem;
    }
    h1, h2, h3 {
        color: #f8fafc;
        font-family: 'Inter', sans-serif;
    }
    .stDataFrame {
        border: 1px solid #334155;
        border-radius: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

# ============================================
# DATA CONNECTION
# ============================================
@st.cache_resource
def get_connection():
    return duckdb.connect('./duckdb/revops_analytics.duckdb', read_only=True)

def query(sql):
    conn = get_connection()
    try:
        return conn.execute(sql).df()
    except Exception as e:
        st.error(f"Query Error: {e}")
        return pd.DataFrame()

# ============================================
# SIDEBAR FILTERS
# ============================================
st.sidebar.image("https://img.icons8.com/isometric/100/rocket.png", width=80)
st.sidebar.title("Revenue Control")

# Get filter options from the DB safely
segment_df = query("SELECT DISTINCT account_segment FROM revops_marts.dim_accounts WHERE account_segment IS NOT NULL")
industry_df = query("SELECT DISTINCT industry FROM revops_marts.dim_accounts WHERE industry IS NOT NULL")

segments = segment_df['account_segment'].tolist() if not segment_df.empty and 'account_segment' in segment_df.columns else []
industries = industry_df['industry'].tolist() if not industry_df.empty and 'industry' in industry_df.columns else []

selected_segment = st.sidebar.multiselect("Account Segment", options=segments, default=segments)
selected_industry = st.sidebar.multiselect("Industry", options=industries, default=industries)

# Construct Filter String safely
filter_clause = "WHERE 1=1 "
if selected_segment:
    if len(selected_segment) > 1:
        filter_clause += f"AND account_segment IN {tuple(selected_segment)} "
    else:
        filter_clause += f"AND account_segment IN ('{selected_segment[0]}') "

if selected_industry:
    if len(selected_industry) > 1:
        filter_clause += f"AND industry IN {tuple(selected_industry)} "
    else:
        filter_clause += f"AND industry IN ('{selected_industry[0]}') "

# ============================================
# REVERSE ETL SYNC WIDGET
# ============================================
st.sidebar.divider()
st.sidebar.subheader("🔄 Reverse ETL Sync")
log_path = './logs/latest_sync.json'
if os.path.exists(log_path):
    with open(log_path, 'r') as f:
        sync_data = json.load(f)
    status_color = "🟢" if sync_data.get('status') == 'Success' else "🟠"
    st.sidebar.markdown(f"**Status:** {status_color} {sync_data.get('status')}")
    st.sidebar.markdown(f"**Last Sync:** `{sync_data.get('last_sync_time')}`")
    st.sidebar.markdown(f"**Synced to HubSpot:** `{sync_data.get('synced_count')} accounts`")
    if sync_data.get('is_dry_run'):
        st.sidebar.caption("*(Dry-run mode active)*")
else:
    st.sidebar.markdown("No recent sync logs found.")
    st.sidebar.caption("Run `python scripts/sync_to_hubspot.py` to populate.")
    
st.sidebar.button("▶ Trigger Manual Sync", help="Normally runs via Dagster/Airflow")

# ============================================
# HEADER
# ============================================
st.title("🚀 Revenue Intelligence Command Center")
st.markdown("<p style='color: #94a3b8;'>Series A Analytics Foundation | Business-Ready Intelligence</p>", unsafe_allow_html=True)

# ============================================
# TOP KPI ROW
# ============================================
kpis = query(f"""
    SELECT 
        SUM(arr) as total_arr,
        SUM(mrr) as total_mrr,
        AVG(engagement_ratio) as avg_engagement,
        COUNT(DISTINCT account_key) as total_accounts,
        COUNT(DISTINCT CASE WHEN health_status = 'at_risk' THEN account_key END) as accounts_at_risk
    FROM revops_marts.dim_accounts
    {filter_clause}
""")

if not kpis.empty:
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total ARR", f"${kpis['total_arr'][0]/1e6:.2f}M", delta=f"${kpis['total_mrr'][0]/1e3:.1f}K MRR")
    with m2:
        st.metric("Accounts", f"{kpis['total_accounts'][0]:.0f}")
    with m3:
        st.metric("Avg Engagement", f"{kpis['avg_engagement'][0]*100:.1f}%")
    with m4:
        st.metric("At Risk", f"{kpis['accounts_at_risk'][0]:.0f}", delta_color="inverse", delta="Requires Action")

st.divider()

# ============================================
# REVENUE WATERFALL (The Wow Factor)
# ============================================
st.header("📈 Monthly MRR Waterfall")
waterfall_data = query(f"""
    SELECT 
        date_month,
        mrr_type,
        SUM(mrr_change) as total_change
    FROM revops_marts.fct_mrr_history
    WHERE date_month >= CURRENT_DATE - INTERVAL '6 months'
      AND mrr_type IN ('new', 'expansion', 'contraction', 'churn')
    GROUP BY 1, 2
    ORDER BY 1
""")

if not waterfall_data.empty:
    fig = px.bar(
        waterfall_data, 
        x="date_month", 
        y="total_change", 
        color="mrr_type",
        title="Revenue Drivers (Last 6 Months)",
        color_discrete_map={'new': '#10b981', 'expansion': '#3b82f6', 'contraction': '#f59e0b', 'churn': '#ef4444'},
        barmode="group",
        template="plotly_dark"
    )
    fig.update_layout(height=400, margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ============================================
# TWO COLUMN LAYOUT: FUNNEL vs HEALTH
# ============================================
c1, c2 = st.columns([1, 1])

with c1:
    st.header("🌪️ Sales Funnel Velocity")
    funnel = query(f"""
        SELECT funnel_stage, COUNT(*) as count
        FROM revops_marts.fct_pipeline
        GROUP BY 1
        ORDER BY count DESC
    """)
    if not funnel.empty:
        fig = px.funnel(funnel, x='count', y='funnel_stage', color_discrete_sequence=['#6366f1'], template="plotly_dark")
        fig.update_layout(height=350, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

with c2:
    st.header("🛡️ Portfolio Health")
    health = query(f"""
        SELECT health_status, COUNT(*) as count
        FROM revops_marts.dim_accounts
        {filter_clause}
        GROUP BY 1
    """)
    if not health.empty:
        fig = px.pie(health, values='count', names='health_status', 
                    color_discrete_map={'healthy': '#10b981', 'at_risk': '#ef4444', 'inactive': '#64748b', 'churned': '#1e293b'},
                    hole=0.4, template="plotly_dark")
        fig.update_layout(height=350, showlegend=True, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ============================================
# ACTIONABLE RISK MATRIX
# ============================================
st.header("🚨 High-ARR Accounts At Risk")
risk_matrix = query(f"""
    SELECT 
        account_name,
        arr,
        engagement_ratio,
        urgent_support_tickets,
        overdue_invoices,
        health_status
    FROM revops_marts.dim_accounts
    WHERE health_status = 'at_risk'
    ORDER BY arr DESC
    LIMIT 10
""")

if not risk_matrix.empty:
    st.dataframe(risk_matrix, use_container_width=True, hide_index=True)
else:
    st.success("✅ No critical accounts at risk in the current filter.")

# ============================================
# HIERARCHY EXPLORER
# ============================================
st.header("🏢 Global Parent Performance")
hierarchy = query(f"""
    SELECT 
        account_name as global_parent,
        industry,
        SUM(arr) as family_arr,
        COUNT(account_key) as sub_entities,
        MAX(health_status) as group_health
    FROM revops_marts.dim_accounts
    WHERE hierarchy_level = 'Global Parent'
    GROUP BY 1, 2
    ORDER BY family_arr DESC
    LIMIT 10
""")

if not hierarchy.empty:
    st.dataframe(hierarchy, use_container_width=True, hide_index=True)

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown(f"<p style='text-align: center; color: #64748b; font-size: 0.8rem;'>RevOps Engine v2.0 | Foundation: Series A Indestructible | Updated: {datetime.now().strftime('%H:%M:%S')}</p>", unsafe_allow_html=True)
