import os
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st

# -------------------------------------------------------------------
# Config
# -------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "processed", "venmito.db")

st.set_page_config(
    page_title="Venmito Analytics",
    page_icon="💳",
    layout="wide",
)


# -------------------------------------------------------------------
# DB helpers
# -------------------------------------------------------------------

@st.cache_resource
def get_connection():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Did you run scripts/build_db.py?")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn


@st.cache_data
def load_table(table_name: str) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)


@st.cache_data
def load_transactions_with_items() -> pd.DataFrame:
    """
    Convenience join of transactions + items if you want line-level analysis.
    """
    conn = get_connection()
    query = """
        SELECT
            ti.transaction_id,
            ti.line_number,
            ti.product_name,
            ti.price,
            ti.price_per_item,
            ti.quantity,
            t.store,
            t.date,
            t.customer_id,
            t.total_price
        FROM transaction_items ti
        JOIN transactions t
          ON ti.transaction_id = t.transaction_id
    """
    return pd.read_sql_query(query, conn)


# -------------------------------------------------------------------
# Data loading
# -------------------------------------------------------------------

customers = load_table("customers")
promotions = load_table("promotions")
transactions = load_table("transactions")
tx_items = load_table("transaction_items")
transfers = load_table("transfers")  # might be enriched later

# Convert date columns to datetime for filtering / grouping
for df, col in [
    (promotions, "promotion_date"),
    (transactions, "date"),
    (tx_items, "date"),
    (transfers, "date"),
]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")


# -------------------------------------------------------------------
# Sidebar filters
# -------------------------------------------------------------------

st.sidebar.title("Venmito Analytics 💳")
st.sidebar.markdown("Use these filters to slice the data.")

# Date range based on transactions (main activity)
if not transactions.empty:
    min_date = transactions["date"].min()
    max_date = transactions["date"].max()
else:
    min_date = None
    max_date = None

if min_date and max_date:
    date_range = st.sidebar.date_input(
        "Transaction date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )
    if isinstance(date_range, tuple):
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date.date(), max_date.date()
else:
    start_date, end_date = None, None

selected_store = st.sidebar.multiselect(
    "Filter by store",
    options=sorted(transactions["store"].dropna().unique()),
    default=None,
)

# Apply filters
filtered_tx = transactions.copy()
filtered_items = tx_items.copy()

if start_date and end_date:
    mask_tx = (filtered_tx["date"].dt.date >= start_date) & (filtered_tx["date"].dt.date <= end_date)
    filtered_tx = filtered_tx[mask_tx]

    mask_items = (filtered_items["date"].dt.date >= start_date) & (filtered_items["date"].dt.date <= end_date)
    filtered_items = filtered_items[mask_items]

if selected_store:
    filtered_tx = filtered_tx[filtered_tx["store"].isin(selected_store)]
    filtered_items = filtered_items[filtered_items["store"].isin(selected_store)]


# -------------------------------------------------------------------
# Helper metric functions
# -------------------------------------------------------------------

def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def overview_metrics():
    st.header("📊 Overview")

    total_customers = len(customers)
    customers_with_tx = filtered_tx["customer_id"].nunique()
    customers_with_promos = promotions["customer_id"].nunique()

    total_revenue = filtered_tx["total_price"].sum()
    total_transactions = len(filtered_tx)
    avg_order_value = filtered_tx["total_price"].mean() if total_transactions > 0 else 0
    avg_items_per_tx = filtered_tx["total_quantity"].mean() if total_transactions > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Customers", f"{total_customers:,}")
    col2.metric("Customers with Transactions", f"{customers_with_tx:,}")
    col3.metric("Customers with Promotions", f"{customers_with_promos:,}")
    col4.metric("Total Revenue (filtered)", format_currency(total_revenue))

    col5, col6 = st.columns(2)
    col5.metric("Average Order Value", format_currency(avg_order_value))
    col6.metric("Avg Items per Transaction", f"{avg_items_per_tx:.2f}")

    # Simple revenue over time chart
    if not filtered_tx.empty:
        revenue_by_date = (
            filtered_tx.groupby("date", as_index=False)["total_price"].sum().rename(columns={"total_price": "revenue"})
        )
        st.subheader("Revenue Over Time")
        st.line_chart(
            revenue_by_date.set_index("date")["revenue"]
        )
    else:
        st.info("No transactions in the selected filters.")


def promotions_metrics():
    st.header("🎯 Promotions Performance")

    if promotions.empty:
        st.info("No promotions data available.")
        return

    # Overall response rate
    total_promos = len(promotions)
    total_yes = (promotions["responded"].str.lower() == "yes").sum()
    response_rate = (total_yes / total_promos * 100) if total_promos > 0 else 0

    col1, col2 = st.columns(2)
    col1.metric("Total Promotions Sent", f"{total_promos:,}")
    col2.metric("Overall Response Rate", f"{response_rate:.2f}%")

    # Response rate by promotion type
    promo_group = (
        promotions.groupby("promotion")
        .agg(
            total_sent=("promotion_id", "count"),
            total_yes=("responded", lambda x: (x.str.lower() == "yes").sum()),
        )
        .reset_index()
    )
    promo_group["response_rate_pct"] = promo_group["total_yes"] / promo_group["total_sent"] * 100

    st.subheader("Response Rate by Promotion")
    st.dataframe(
        promo_group.sort_values("response_rate_pct", ascending=False),
        use_container_width=True,
    )

    st.bar_chart(
        promo_group.set_index("promotion")["response_rate_pct"]
    )

    st.markdown(
        """
        **Manager insight ideas:**
        - Focus budget on promotions with higher response rate.
        - For promotions with many "No" responses, consider adjusting:
            - Channel (SMS vs email),
            - Timing (day of week / hour),
            - Discount depth or product mix.
        """
    )


def stores_and_products_metrics():
    st.header("🏬 Stores & 🛒 Products")

    if filtered_items.empty:
        st.info("No transaction items in the selected filters.")
        return

    # Top products by units
    product_stats = (
        filtered_items.groupby("product_name")
        .agg(
            total_units=("quantity", "sum"),
            total_revenue=("price", "sum"),
            num_transactions=("transaction_id", "nunique"),
        )
        .reset_index()
    )
    top_products_units = product_stats.sort_values("total_units", ascending=False).head(10)
    top_products_revenue = product_stats.sort_values("total_revenue", ascending=False).head(10)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top Products by Units Sold")
        st.dataframe(top_products_units, use_container_width=True)
        st.bar_chart(top_products_units.set_index("product_name")["total_units"])
    with col2:
        st.subheader("Top Products by Revenue")
        st.dataframe(top_products_revenue, use_container_width=True)
        st.bar_chart(top_products_revenue.set_index("product_name")["total_revenue"])

    # Store performance
    if not filtered_tx.empty:
        store_stats = (
            filtered_tx.groupby("store")
            .agg(
                store_revenue=("total_price", "sum"),
                num_transactions=("transaction_id", "nunique"),
                avg_ticket=("total_price", "mean"),
            )
            .reset_index()
        )
        st.subheader("Store Performance")
        st.dataframe(
            store_stats.sort_values("store_revenue", ascending=False),
            use_container_width=True,
        )
        st.bar_chart(
            store_stats.set_index("store")["store_revenue"]
        )

        st.markdown(
            """
            **Manager insight ideas:**
            - Use *store_revenue* and *avg_ticket* to benchmark store performance.
            - Identify underperforming stores and investigate:
                - Product mix,
                - Local promotions,
                - Customer demographics.
            """
        )
    else:
        st.info("No transaction header data for the selected filters.")


def transfers_metrics():
    st.header("💸 Transfers (Peer-to-Peer / Wallet)")

    if transfers.empty:
        st.info("No transfer data available.")
        return

    total_transfers = len(transfers)
    total_volume = transfers["amount"].sum()
    avg_transfer = transfers["amount"].mean()

    col1, col2, col3 = st.columns(3)
    col1.metric("Number of Transfers", f"{total_transfers:,}")
    col2.metric("Total Transfer Volume", format_currency(total_volume))
    col3.metric("Average Transfer", format_currency(avg_transfer))

    # Transfers over time
    transfers_by_date = (
        transfers.groupby("date", as_index=False)["amount"].sum().rename(columns={"amount": "volume"})
    )
    st.subheader("Transfer Volume Over Time")
    st.line_chart(transfers_by_date.set_index("date")["volume"])

    st.markdown(
        """
        **Manager insight ideas:**
        - Monitor transfer volume trends to understand liquidity usage.
        - Combine with promotions to see if certain campaigns increase P2P usage.
        """
    )


def data_quality_metrics():
    st.header("🧹 Data Quality & Anomalies")

    # Customers missing key fields
    missing_email = customers["email"].isna().sum()
    missing_phone = customers["phone"].isna().sum()

    col1, col2 = st.columns(2)
    col1.metric("Customers without Email", f"{missing_email:,}")
    col2.metric("Customers without Phone", f"{missing_phone:,}")

    # Suspicious transactions: zero / negative / extreme values
    suspicious = filtered_items[
        (filtered_items["price"] <= 0)
        | (filtered_items["price_per_item"] <= 0)
    ]

    st.subheader("Suspicious Transaction Lines (price <= 0)")
    if suspicious.empty:
        st.success("No suspicious lines found in the filtered dataset.")
    else:
        st.warning(f"{len(suspicious)} suspicious lines found.")
        st.dataframe(suspicious.head(50), use_container_width=True)
        st.markdown(
            """
            Example issues:
            - Free promotional items recorded with price = 0,
            - Refunds / chargebacks (negative prices),
            - Data entry errors.
            Managers should decide:
            - Do we keep them, tag them as promo/refund, or clean them from KPIs?
            """
        )

    # Duplicate transactions (same customer + date + store + total_price)
    if not filtered_tx.empty:
        dup_keys = filtered_tx.groupby(
            ["customer_id", "store", "date", "total_price"]
        ).size().reset_index(name="count")
        dup_keys = dup_keys[dup_keys["count"] > 1]

        st.subheader("Potential Duplicate Transactions")
        if dup_keys.empty:
            st.success("No obvious duplicate transactions based on (customer, store, date, total_price).")
        else:
            st.warning(f"{len(dup_keys)} potential duplicate groups found.")
            st.dataframe(dup_keys.head(50), use_container_width=True)


# -------------------------------------------------------------------
# Layout
# -------------------------------------------------------------------

st.title("Venmito Data Analytics Dashboard")
st.caption(
    "Built on top of unified data from people.json / people.yml / transfers.csv / "
    "transactions.xml / promotions.csv"
)

tab_overview, tab_promos, tab_stores_products, tab_transfers, tab_data_quality = st.tabs(
    ["Overview", "Promotions", "Stores & Products", "Transfers", "Data Quality"]
)

with tab_overview:
    overview_metrics()

with tab_promos:
    promotions_metrics()

with tab_stores_products:
    stores_and_products_metrics()

with tab_transfers:
    transfers_metrics()

with tab_data_quality:
    data_quality_metrics()
# -------------------------------------------------------------------
# End of file
# -------------------------------------------------------------------
