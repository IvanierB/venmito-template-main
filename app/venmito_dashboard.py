import sqlite3
from pathlib import Path
from datetime import datetime, date

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

# --- Page config ---
st.set_page_config(
    page_title="Venmito Customer 360",
    layout="wide",
    page_icon="📊",
)

# --- Minimal styling (works well on dark mode) ---
st.markdown("""
<style>
.big-metric {
    font-size: 64px !important;
    font-weight: 900 !important;
    line-height: 1.0 !important;
    color: #009f4d !important;
    margin-bottom: 6px !important;
    padding: 4px 8px;
    border-radius: 6px;
    background: rgba(255,255,255,0.05);
    text-shadow: 0px 0px 4px rgba(255,255,255,0.15);
}

.sub-metric {
    font-size: 32px !important;
    color: #ffffff !important;  /* white text for dark background */
}

.section-title {
    font-size: 24px;
    font-weight: 700;
    margin-top: 1.5rem;
    margin-bottom: 0.5rem;
    color: #ffffff;
}

/* ===== PAGE TITLES & SECTION HEADERS ===== */
.stApp h1, .stApp h2, .stApp h3, .section-title {
    font-size: 32px !important;   /* Increase header size */
    font-weight: 900 !important;  /* Make bold */
    color: #ffffff !important;    /* Bright white for dark mode */
    padding-top: 10px !important;
    padding-bottom: 5px !important;
}

/* Even bigger main title */
.stApp h1 {
    font-size: 40px !important;
}

/* ===== TAB LABELS ===== */
.stTabs [role="tab"] {
    font-size: 18px !important;     /* Increase text size */
    font-weight: 700 !important;    /* Bold */
    padding: 10px 18px !important;  /* More breathing room */
}

/* Selected tab styling */
.stTabs [aria-selected="true"] {
    font-size: 25px !important;     /* Slightly larger when active */
    font-weight: 800 !important;
    background-color: #333333 !important;
    color: #ffffff !important;
}

/* ===== GLOBAL BODY TEXT (descriptions, st.write, paragraphs, labels, captions) ===== */
html, body, .stApp, .stMarkdown, .stText, p, span, label, div[data-testid="stMarkdownContainer"] {
    font-size: 18px !important;   /* increase readability */
    line-height: 1.5 !important;
    color: #ffffff !important;    /* white for dark mode */
}

/* Captions (e.g., st.caption) */
.caption, .stCaption, [data-testid="stCaptionContainer"] {
    font-size: 16px !important;
    color: #cccccc !important;    /* softer gray for secondary text */
}

/* Text inside metrics below big metric text */
.sub-metric {
    font-size: 22px !important; /* better balance with larger body text */
}
/* ===== SIDEBAR STYLING ===== */
.stSidebar .stHeader h2 {
    font-size: 28px !important;
    font-weight: 900 !important;
    color: #ffffff !important;
    padding-top: 10px !important;
    padding-bottom: 5px !important;
}
.stSidebar label, .stSidebar .stText, .stSidebar .stMarkdown {
    font-size: 18px !important;
    color: #ffffff !important;
}
.stSidebar .stSelectbox label, .stSidebar .stMultiSelect label {
    font-size: 20px !important;
    font-weight: 700 !important;
}
.stSidebar .stRadio label {
    font-size: 20px !important;
    font-weight: 700 !important;
}

</style>
""", unsafe_allow_html=True)

# --- Color palette (your brand) ---
COLOR_WHITE   = "#ffffff"
COLOR_ORANGE  = "#ff7f32"
COLOR_MAGENTA = "#c6007e"
COLOR_GREEN   = "#009f4d"
COLOR_BLUE    = "#59cbe8"

# --- Paths / DB ---
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "processed" / "venmito.db"


# --- Data loading (cached) ---
@st.cache_data(show_spinner=True)
def load_data(db_path: Path):
    conn = sqlite3.connect(db_path)
    customers = pd.read_sql("SELECT * FROM customers;", conn)
    transfers = pd.read_sql("SELECT * FROM transfers;", conn)
    promotions = pd.read_sql("SELECT * FROM promotions;", conn)
    tx = pd.read_sql("SELECT * FROM transactions;", conn)
    tx_items = pd.read_sql("SELECT * FROM transaction_items;", conn)
    conn.close()

    # Parse date columns if present
    for df, col in [
        (transfers, "date"),
        (promotions, "promotion_date"),
        (tx, "date"),
        (tx_items, "date"),
    ]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Ensure booleans for device flags
    for col in ["device_android", "device_iphone", "device_desktop"]:
        if col in customers.columns:
            customers[col] = customers[col].astype("boolean")

    return {
        "customers": customers,
        "transfers": transfers,
        "promotions": promotions,
        "tx": tx,
        "tx_items": tx_items,
    }


def _safe_minmax_dates(tx: pd.DataFrame):
    if "date" not in tx.columns or tx["date"].isna().all():
        today = date.today()
        return today, today
    dmin = tx["date"].min().date()
    dmax = tx["date"].max().date()
    return dmin, dmax


# --- Global filters ---
def apply_global_filters(data):
    customers = data["customers"].copy()
    promotions = data["promotions"].copy()
    tx = data["tx"].copy()
    tx_items = data["tx_items"].copy()

    date_min, date_max = _safe_minmax_dates(tx)

    with st.sidebar:
        st.header("🔍 Global Filters")

        # Date range for transactions
        date_range = st.date_input(
            "Transaction date range",
            value=(date_min, date_max),
            min_value=date_min,
            max_value=date_max,
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = date_min
            end_date = date_max

        # Store filter
        store_list = sorted(tx["store"].dropna().unique()) if "store" in tx.columns else []
        selected_stores = st.multiselect(
            "Stores",
            options=store_list,
            default=store_list,
        )

        # Country filter (customers)
        country_list = sorted(customers["country"].dropna().unique()) if "country" in customers.columns else []
        selected_countries = st.multiselect(
            "Customer country",
            options=country_list,
            default=country_list,
        )

        # Device filter
        device_options = ["Android", "iPhone", "Desktop"]
        selected_devices = st.multiselect(
            "Devices",
            options=device_options,
            default=device_options,
        )

        # View mode
        view_mode = st.radio(
            "View mode",
            ["Executive summary", "Analyst detail"],
            horizontal=True,
        )

    # Apply date + store filters to transactions
    if "date" in tx.columns:
        mask_date = (tx["date"].dt.date >= start_date) & (tx["date"].dt.date <= end_date)
        tx = tx[mask_date]

    if "store" in tx.columns and selected_stores:
        tx = tx[tx["store"].isin(selected_stores)]

    # Filter tx_items by filtered transaction_id and store if present
    if "transaction_id" in tx_items.columns and "transaction_id" in tx.columns:
        tx_items = tx_items[tx_items["transaction_id"].isin(tx["transaction_id"])]
    if "store" in tx_items.columns and selected_stores:
        tx_items = tx_items[tx_items["store"].isin(selected_stores)]

    # Filter customers by country
    if "country" in customers.columns and selected_countries:
        customers = customers[customers["country"].isin(selected_countries)]

    # Filter customers by device flags
    device_mask = pd.Series(True, index=customers.index)
    if "Android" not in selected_devices and "device_android" in customers.columns:
        device_mask &= ~customers["device_android"].fillna(False)
    if "iPhone" not in selected_devices and "device_iphone" in customers.columns:
        device_mask &= ~customers["device_iphone"].fillna(False)
    if "Desktop" not in selected_devices and "device_desktop" in customers.columns:
        device_mask &= ~customers["device_desktop"].fillna(False)
    customers = customers[device_mask]

    # Filter promotions by promotion_date intersecting date range (if it exists)
    if "promotion_date" in promotions.columns:
        p_mask = (promotions["promotion_date"].dt.date >= start_date) & (
            promotions["promotion_date"].dt.date <= end_date
        )
        promotions = promotions[p_mask]

    # If promotions have customer_id and we filtered customers, keep only matching customers
    if "customer_id" in promotions.columns and "customer_id" in customers.columns:
        promotions = promotions[promotions["customer_id"].isin(customers["customer_id"])]

    return {
        "customers": customers.reset_index(drop=True),
        "promotions": promotions.reset_index(drop=True),
        "tx": tx.reset_index(drop=True),
        "tx_items": tx_items.reset_index(drop=True),
        "view_mode": view_mode,
    }


# --- Helper: KPI card ---
def kpi_card(label: str, value: str, help_text: str | None = None):
    st.markdown(f"<div class='big-metric'>{value}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sub-metric'>{label}</div>", unsafe_allow_html=True)
    if help_text:
        st.caption(help_text)


# --- Overview tab ---
def render_overview(filtered, view_mode: str):
    customers = filtered["customers"]
    tx = filtered["tx"]
    promotions = filtered["promotions"]

    st.markdown("<div class='section-title'>📊 Overview</div>", unsafe_allow_html=True)
    st.write("High-level view of revenue, activity, and engagement for the selected filters.")

    # Basic aggregates
    total_revenue = tx["total_price"].sum() if "total_price" in tx.columns else 0.0
    tx_count = tx["transaction_id"].nunique() if "transaction_id" in tx.columns else len(tx)
    active_customers = tx["customer_id"].nunique() if "customer_id" in tx.columns else 0

    aov = total_revenue / tx_count if tx_count > 0 else 0.0

    promos_sent = len(promotions)
    responded_col = "responded" if "responded" in promotions.columns else None
    if responded_col:
        num_responses = promotions[responded_col].str.upper().eq("YES").sum()
        promo_rr = num_responses / promos_sent if promos_sent > 0 else 0.0
    else:
        promo_rr = 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Total Revenue", f"${total_revenue:,.0f}", "Sum of transaction totals.")
    with c2:
        kpi_card("Avg Order Value", f"${aov:,.2f}", "Revenue / number of transactions.")
    with c3:
        kpi_card("Active Customers", f"{active_customers:,}", "Customers with at least one transaction.")
    with c4:
        if responded_col:
            kpi_card("Promo Response Rate", f"{promo_rr*100:,.1f}%", "Responses / promotions sent.")
        else:
            kpi_card("Promo Response Rate", "N/A", "No response field available.")

    # Revenue over time
    if "date" in tx.columns and not tx.empty:
        st.markdown("<div class='section-title'>📈 Revenue over time</div>", unsafe_allow_html=True)
        freq = st.selectbox("Aggregation frequency", ["Daily", "Weekly", "Monthly"], index=2, key="rev_freq")

        if freq == "Daily":
            grp = pd.Grouper(key="date", freq="D")
        elif freq == "Weekly":
            grp = pd.Grouper(key="date", freq="W")
        else:
            grp = pd.Grouper(key="date", freq="M")

        revenue_ts = (
            tx.groupby(grp)["total_price"]
            .sum()
            .reset_index()
            .rename(columns={"total_price": "revenue"})
        )

        chart = (
            alt.Chart(revenue_ts)
            .mark_line(point=True, strokeWidth=3)
            .encode(
                x=alt.X("date:T", title="Date"),
                y=alt.Y("revenue:Q", title="Revenue"),
                tooltip=["date:T", "revenue:Q"],
                color=alt.value(COLOR_BLUE),  # light blue line
            )
            .properties(height=320)
        ).interactive()

        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No transactions available for the current filter selection.")

    if view_mode == "Analyst detail":
        st.markdown("<div class='section-title'>Raw transactions sample</div>", unsafe_allow_html=True)
        st.dataframe(tx.head(50))


# --- Customers (RFM) tab ---
def render_customers(filtered, view_mode: str):
    customers = filtered["customers"]
    tx = filtered["tx"]

    st.markdown("<div class='section-title'>👤 Customers & Segments</div>", unsafe_allow_html=True)
    st.write("Basic RFM-style segmentation to highlight valuable and at-risk customers.")

    if tx.empty or "customer_id" not in tx.columns:
        st.warning("No transaction-level customer data available for this filter selection.")
        return

    # RFM metrics
    ref_date = tx["date"].max() if "date" in tx.columns else pd.Timestamp.today()

    rfm = (
        tx.groupby("customer_id")
        .agg(
            last_purchase=("date", "max"),
            tx_count=("transaction_id", "nunique"),
            total_spend=("total_price", "sum"),
        )
        .reset_index()
    )

    rfm["recency_days"] = (ref_date - rfm["last_purchase"]).dt.days

    # Simple segmentation rules (tweak as you like)
    def segment_row(row):
        if row["tx_count"] >= 5 and row["recency_days"] <= 30:
            return "High Value"
        elif row["tx_count"] >= 3 and row["recency_days"] <= 90:
            return "Loyal"
        elif row["recency_days"] > 180 and row["tx_count"] >= 2:
            return "At Risk"
        elif row["tx_count"] == 1 and row["recency_days"] <= 30:
            return "New"
        else:
            return "Other"

    rfm["segment"] = rfm.apply(segment_row, axis=1)

    # Join customer name/email if available
    if "customer_id" in customers.columns:
        cols_to_use = ["customer_id", "full_name", "email", "country", "city"]
        cols_to_use = [c for c in cols_to_use if c in customers.columns]
        rfm = rfm.merge(
            customers[cols_to_use],
            on="customer_id",
            how="left",
        )

    # KPI: count by segment
    seg_counts = rfm["segment"].value_counts().reset_index()
    seg_counts.columns = ["segment", "count"]

    # --- Segment distribution (Pie Chart, centered & large) ---
    st.markdown("<div class='section-title'>Segment distribution</div>", unsafe_allow_html=True)

    # Create a larger pie chart (no hole)
    pie_chart = (
        alt.Chart(seg_counts)
        .mark_arc()   # full pie (no innerRadius)
        .encode(
            theta=alt.Theta("count:Q", stack=True),
            color=alt.Color(
                "segment:N",
                legend=alt.Legend(title="Customer Segment"),
                scale=alt.Scale(
                    range=[COLOR_ORANGE, COLOR_MAGENTA, COLOR_GREEN, COLOR_BLUE]
                ),
            ),
            tooltip=["segment:N", "count:Q"]
        )
        .properties(
            height=500,   
            width=500
        )
    )

    # Center the chart on the page
    center_col = st.columns([1, 2, 1])[1]
    with center_col:
        st.altair_chart(pie_chart, use_container_width=False)


    # Top customers table
    st.markdown("<div class='section-title'>Top customers by spend</div>", unsafe_allow_html=True)
    top_n = st.slider("Number of customers to show", 5, 50, 10, key="top_n_customers")

    cols = [
        "customer_id",
        "full_name",
        "email",
        "country",
        "city",
        "segment",
        "total_spend",
        "tx_count",
        "recency_days",
    ]
    cols = [c for c in cols if c in rfm.columns]

    st.dataframe(
        rfm[cols].sort_values("total_spend", ascending=False).head(top_n),
        use_container_width=True,
    )

    if view_mode == "Analyst detail":
        st.markdown("<div class='section-title'>RFM raw table (sample)</div>", unsafe_allow_html=True)
        st.dataframe(rfm.head(100))


def render_promotions(filtered, view_mode: str):
    promotions = filtered["promotions"]
    customers = filtered["customers"]

    st.markdown("<div class='section-title'>🎯 Promotions performance</div>", unsafe_allow_html=True)
    st.write("How well are promotions reaching and converting customers?")

    if promotions.empty:
        st.info("No promotions in scope for current filters.")
        return

    # Ensure responded_flag exists (1 = YES, 0 = otherwise)
    if "responded" in promotions.columns:
        promotions = promotions.copy()
        promotions["responded_flag"] = (
            promotions["responded"]
            .fillna("")
            .astype(str)
            .str.upper()
            .eq("YES")
            .astype(int)
        )
    else:
        promotions["responded_flag"] = 0  # fallback, no responses

    total_sent = len(promotions)
    total_yes = int(promotions["responded_flag"].sum())
    base_rate = total_yes / total_sent if total_sent > 0 else 0.0

    # ===== TOP-LEVEL FUNNEL KPIs =====
    has_cust = promotions["customer_id"].notna().sum() if "customer_id" in promotions.columns else 0
    has_email = promotions["client_email"].notna().sum() if "client_email" in promotions.columns else 0
    has_phone = promotions["telephone"].notna().sum() if "telephone" in promotions.columns else 0
    contactable = max(has_email, has_phone)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Promotions sent", f"{total_sent:,}")
    with c2:
        kpi_card("Linked to customer", f"{has_cust:,}")
    with c3:
        kpi_card("Contactable", f"{contactable:,}")
    with c4:
        kpi_card("Responses", f"{total_yes:,} ({base_rate*100:,.1f}%)")

    # Helper: try to guess a "promotion type" column
    promo_type_col = None
    for candidate in ["promotion_name", "promotion", "product_name", "product", "campaign"]:
        if candidate in promotions.columns:
            promo_type_col = candidate
            break

    # If we have customer_id, join customers for device / country analysis
    joined = None
    if "customer_id" in promotions.columns and "customer_id" in customers.columns:
        cols = ["customer_id", "device_android", "device_iphone", "device_desktop", "country"]
        cols = [c for c in cols if c in customers.columns]
        if cols:
            joined = promotions.merge(
                customers[cols],
                on="customer_id",
                how="left",
            )

    st.markdown(
        "<div class='section-title'>📊 Interactive promotion analysis</div>",
        unsafe_allow_html=True,
    )

    analysis_mode = st.radio(
        "Choose analysis view",
        [
            "By promotion type",
            "By device type",
            "By customer country",
            "By weekday sent",
        ],
        horizontal=True,
    )

    # ===== VIEW 1: BY PROMOTION TYPE (unchanged) =====
    if analysis_mode == "By promotion type":
        if promo_type_col is None:
            st.info("No promotion type column found (expected something like 'promotion_name', 'promotion', 'product', or 'campaign').")
        else:
            grouped = (
                promotions.groupby(promo_type_col)
                .agg(
                    sent=("promotion_id", "count"),
                    responses=("responded_flag", "sum"),
                )
                .reset_index()
            )
            grouped["response_rate"] = grouped["responses"] / grouped["sent"]

            st.write("Response rate by promotion type.")
            chart = (
                alt.Chart(grouped.sort_values("response_rate", ascending=False))
                .mark_bar()
                .encode(
                    x=alt.X("response_rate:Q", title="Response rate", axis=alt.Axis(format="%")),
                    y=alt.Y(f"{promo_type_col}:N", sort="-x", title="Promotion type"),
                    tooltip=[promo_type_col, "sent", "responses", "response_rate"],
                )
                .properties(height=400)
                .encode(color=alt.value(COLOR_BLUE))
            )
            st.altair_chart(chart, use_container_width=True)

            if view_mode == "Analyst detail":
                st.dataframe(grouped.sort_values("response_rate", ascending=False), use_container_width=True)

    # ===== VIEW 2: BY DEVICE TYPE (NOW HORIZONTAL BAR) =====
    elif analysis_mode == "By device type":
        if joined is None:
            st.info("No customer-device information available to break down by device.")
        else:
            dev_cols = [c for c in ["device_android", "device_iphone", "device_desktop"] if c in joined.columns]
            if not dev_cols:
                st.info("No device columns available in customer data.")
            else:
                dev_long = (
                    joined.melt(
                        id_vars=["promotion_id", "responded_flag"],
                        value_vars=dev_cols,
                        var_name="device",
                        value_name="has_device",
                    )
                    .query("has_device == True")
                )

                if dev_long.empty:
                    st.info("No promotions linked to customers with device flags.")
                else:
                    dev_long["device"] = dev_long["device"].str.replace("device_", "", regex=False).str.title()

                    grouped = (
                        dev_long.groupby("device")
                        .agg(
                            sent=("promotion_id", "count"),
                            responses=("responded_flag", "sum"),
                        )
                        .reset_index()
                    )
                    grouped["response_rate"] = grouped["responses"] / grouped["sent"]

                    st.write("Response rate by customer device type.")
                    chart = (
                        alt.Chart(grouped.sort_values("response_rate", ascending=False))
                        .mark_bar()
                        .encode(
                            x=alt.X("response_rate:Q", title="Response rate", axis=alt.Axis(format="%")),
                            y=alt.Y("device:N", sort="-x", title="Device"),
                            tooltip=["device", "sent", "responses", "response_rate"],
                            color=alt.value(COLOR_GREEN),
                        )
                        .properties(height=300)
                    )
                    st.altair_chart(chart, use_container_width=True)

                    if view_mode == "Analyst detail":
                        st.dataframe(grouped, use_container_width=True)

    # ===== VIEW 3: BY CUSTOMER COUNTRY (unchanged) =====
    elif analysis_mode == "By customer country":
        if joined is None or "country" not in joined.columns:
            st.info("No customer country information available to analyze promotions by country.")
        else:
            country_stats = (
                joined.groupby("country")
                .agg(
                    sent=("promotion_id", "count"),
                    responses=("responded_flag", "sum"),
                )
                .reset_index()
            )
            # Filter out tiny countries for readability
            country_stats = country_stats[country_stats["sent"] >= 5]
            if country_stats.empty:
                st.info("Not enough promotions per country (>= 5) to show a breakdown.")
            else:
                country_stats["response_rate"] = country_stats["responses"] / country_stats["sent"]
                st.write("Response rate by customer country (only countries with ≥ 5 promotions).")

                chart = (
                    alt.Chart(country_stats.sort_values("response_rate", ascending=False))
                    .mark_bar()
                    .encode(
                        x=alt.X("response_rate:Q", title="Response rate", axis=alt.Axis(format="%")),
                        y=alt.Y("country:N", sort="-x", title="Country"),
                        tooltip=["country", "sent", "responses", "response_rate"],
                    )
                    .properties(height=400)
                    .encode(color=alt.value(COLOR_MAGENTA))
                )
                st.altair_chart(chart, use_container_width=True)

                if view_mode == "Analyst detail":
                    st.dataframe(country_stats.sort_values("response_rate", ascending=False), use_container_width=True)

    # ===== VIEW 4: BY WEEKDAY SENT (NOW HORIZONTAL BAR) =====
    elif analysis_mode == "By weekday sent":
        if "promotion_date" not in promotions.columns or promotions["promotion_date"].isna().all():
            st.info("No promotion_date column available to analyze by weekday.")
        else:
            promos_wd = promotions.copy()
            promos_wd["weekday"] = promos_wd["promotion_date"].dt.day_name()

            # Order weekdays
            weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            promos_wd["weekday"] = pd.Categorical(promos_wd["weekday"], categories=weekday_order, ordered=True)

            grouped = (
                promos_wd.groupby("weekday")
                .agg(
                    sent=("promotion_id", "count"),
                    responses=("responded_flag", "sum"),
                )
                .reset_index()
            )
            grouped = grouped[grouped["sent"] > 0]
            if grouped.empty:
                st.info("No promotions with valid weekdays to show.")
            else:
                grouped["response_rate"] = grouped["responses"] / grouped["sent"]

                st.write("Response rate by weekday promotions were sent.")
                chart = (
                    alt.Chart(grouped.sort_values("response_rate", ascending=False))
                    .mark_bar()
                    .encode(
                        x=alt.X("response_rate:Q", title="Response rate", axis=alt.Axis(format="%")),
                        y=alt.Y("weekday:N", sort="-x", title="Weekday"),
                        tooltip=["weekday", "sent", "responses", "response_rate"],
                    )
                    .properties(height=400)
                    .encode(color=alt.value(COLOR_BLUE))
                )
                st.altair_chart(chart, use_container_width=True)

                if view_mode == "Analyst detail":
                    st.dataframe(grouped, use_container_width=True)

    # ===== SECTION 2: FACTORS INFLUENCING RESPONSE (same as before) =====
    st.markdown(
        "<div class='section-title'>🧠 Factors influencing response (relative impact)</div>",
        unsafe_allow_html=True,
    )
    st.write(
        "This compares each factor's response rate against the overall average to "
        "estimate which dimensions have the strongest influence on customers saying 'YES'."
    )

    impact_rows = []

    def factor_impact(df: pd.DataFrame, factor_col: str, label: str):
        nonlocal impact_rows, base_rate
        if factor_col not in df.columns:
            return
        tmp = df[[factor_col, "responded_flag"]].dropna()
        if tmp.empty:
            return
        grp = tmp.groupby(factor_col)["responded_flag"].mean()
        if len(grp) < 2:
            return
        impact = float((grp - base_rate).abs().max())
        impact_rows.append({"factor": label, "impact": impact})

    # 1) Promotion type
    if promo_type_col is not None:
        factor_impact(promotions, promo_type_col, "Promotion type")

    # 2) Device type
    if joined is not None:
        dev_cols = [c for c in ["device_android", "device_iphone", "device_desktop"] if c in joined.columns]
        if dev_cols:
            dev_long = (
                joined.melt(
                    id_vars=["promotion_id", "responded_flag"],
                    value_vars=dev_cols,
                    var_name="device",
                    value_name="has_device",
                )
                .query("has_device == True")
            )
            if not dev_long.empty:
                dev_long["device"] = dev_long["device"].str.replace("device_", "", regex=False).str.title()
                factor_impact(dev_long.rename(columns={"device": "factor_val"}), "factor_val", "Device type")

    # 3) Country
    if joined is not None and "country" in joined.columns:
        factor_impact(joined.rename(columns={"country": "factor_val"}), "factor_val", "Customer country")

    # 4) Weekday
    if "promotion_date" in promotions.columns and not promotions["promotion_date"].isna().all():
        wd_df = promotions.copy()
        wd_df["weekday"] = wd_df["promotion_date"].dt.day_name()
        factor_impact(wd_df.rename(columns={"weekday": "factor_val"}), "factor_val", "Weekday sent")

    if impact_rows:
        impact_df = pd.DataFrame(impact_rows).sort_values("impact", ascending=False)
        impact_df["impact_pct_points"] = impact_df["impact"] * 100.0

        chart = (
            alt.Chart(impact_df)
            .mark_bar()
            .encode(
                x=alt.X("impact_pct_points:Q", title="Max change in response rate (percentage points)"),
                y=alt.Y("factor:N", sort="-x", title="Factor"),
                tooltip=["factor", "impact_pct_points"],
            )
            .properties(height=300)
            .encode(color=alt.value(COLOR_ORANGE))
        )
        st.altair_chart(chart, use_container_width=True)

        if view_mode == "Analyst detail":
            st.dataframe(impact_df, use_container_width=True)
    else:
        st.info("Not enough variation in the available data to estimate influencing factors.")


# --- Store & Products tab ---
def render_store_products(filtered, view_mode: str):
    tx = filtered["tx"]
    tx_items = filtered["tx_items"]

    st.markdown("<div class='section-title'>🏪 Stores & Products</div>", unsafe_allow_html=True)
    st.write("Which stores and products are driving performance?")

    # Top stores
    if not tx.empty and "store" in tx.columns:
        st.markdown("<div class='section-title'>Top stores</div>", unsafe_allow_html=True)

        store_stats = (
            tx.groupby("store")
            .agg(
                revenue=("total_price", "sum"),
                tx_count=("transaction_id", "nunique"),
                unique_customers=("customer_id", "nunique")
                if "customer_id" in tx.columns
                else ("transaction_id", "nunique"),
                avg_basket_value=("total_price", "mean"),
            )
            .reset_index()
        )

        chart = (
            alt.Chart(store_stats.sort_values("revenue", ascending=False).head(10))
            .mark_bar()
            .encode(
                x=alt.X("revenue:Q", title="Revenue"),
                y=alt.Y("store:N", sort="-x", title="Store"),
                tooltip=["store", "revenue", "tx_count", "unique_customers", "avg_basket_value"],
                color=alt.value(COLOR_GREEN),  # green for stores
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)

        if view_mode == "Analyst detail":
            st.dataframe(
                store_stats.sort_values("revenue", ascending=False),
                use_container_width=True,
            )
    else:
        st.info("No store information available in transactions for current filter.")

    # Top products
    if not tx_items.empty and "product_name" in tx_items.columns:
        st.markdown("<div class='section-title'>Top products</div>", unsafe_allow_html=True)

        # Ensure quantity / price columns exist
        qty_col = "quantity" if "quantity" in tx_items.columns else None
        price_col = "price" if "price" in tx_items.columns else None

        agg_dict = {
            "tx_count": ("transaction_id", "nunique"),
        }
        if qty_col:
            agg_dict["units"] = (qty_col, "sum")
        if price_col:
            agg_dict["revenue"] = (price_col, "sum")

        product_stats = (
            tx_items.groupby("product_name")
            .agg(**agg_dict)
            .reset_index()
        )

        if "revenue" in product_stats.columns:
            product_stats = product_stats.sort_values("revenue", ascending=False)
        elif "units" in product_stats.columns:
            product_stats = product_stats.sort_values("units", ascending=False)

        chart_metric = "revenue" if "revenue" in product_stats.columns else "units"

        chart = (
            alt.Chart(product_stats.head(15))
            .mark_bar()
            .encode(
                x=alt.X(f"{chart_metric}:Q", title=chart_metric.capitalize()),
                y=alt.Y("product_name:N", sort="-x", title="Product"),
                tooltip=product_stats.columns.tolist(),
                color=alt.value(COLOR_MAGENTA),  # magenta for products
            )
            .properties(height=320)
        )
        st.altair_chart(chart, use_container_width=True)

        if view_mode == "Analyst detail":
            st.dataframe(product_stats.head(100), use_container_width=True)
    else:
        st.info("No item-level product data available for current filter.")

    # Simple basket analysis (product co-occurrence)
    if view_mode == "Analyst detail" and not tx_items.empty:
        st.markdown("<div class='section-title'>Basket analysis (co-purchased products)</div>", unsafe_allow_html=True)

        # For each transaction, list unique products
        baskets = (
            tx_items.groupby("transaction_id")["product_name"]
            .apply(lambda s: sorted(set(s.dropna().tolist())))
            .reset_index()
        )

        # Build pair counts for small-ish datasets
        pair_counts = {}
        for _, row in baskets.iterrows():
            prods = row["product_name"]
            for i in range(len(prods)):
                for j in range(i + 1, len(prods)):
                    pair = tuple(sorted((prods[i], prods[j])))
                    pair_counts[pair] = pair_counts.get(pair, 0) + 1

        if pair_counts:
            pairs_df = (
                pd.DataFrame(
                    [
                        {"product_a": a, "product_b": b, "count": c}
                        for (a, b), c in pair_counts.items()
                    ]
                )
                .sort_values("count", ascending=False)
                .head(20)
            )
            st.dataframe(pairs_df, use_container_width=True)
        else:
            st.info("Not enough co-purchase data to show product pairings.")


# --- Data Quality tab ---
def render_data_quality(filtered, view_mode: str):
    customers = filtered["customers"]
    tx = filtered["tx"]
    tx_items = filtered["tx_items"]

    st.markdown("<div class='section-title'>🧼 Data quality & anomalies</div>", unsafe_allow_html=True)
    st.write("Quick checks for missing or suspicious data that might affect decision-making.")

    # Customers: missing contact info
    missing_email = customers["email"].isna().sum() if "email" in customers.columns else 0
    missing_phone = customers["phone"].isna().sum() if "phone" in customers.columns else 0

    total_cust = len(customers)
    c1, c2 = st.columns(2)
    with c1:
        kpi_card(
            "Customers without email",
            f"{missing_email:,}",
            f"{missing_email/total_cust*100:,.1f}% of customers" if total_cust else "",
        )
    with c2:
        kpi_card(
            "Customers without phone",
            f"{missing_phone:,}",
            f"{missing_phone/total_cust*100:,.1f}% of customers" if total_cust else "",
        )

    # Transactions: negative or zero prices
    if "total_price" in tx.columns:
        neg_total = tx[tx["total_price"] < 0]
        zero_total = tx[tx["total_price"] == 0]

        c3, c4 = st.columns(2)
        with c3:
            kpi_card("Negative total transactions", f"{len(neg_total):,}")
        with c4:
            kpi_card("Zero total transactions", f"{len(zero_total):,}")

        if view_mode == "Analyst detail":
            if not neg_total.empty:
                st.markdown("<div class='section-title'>Negative total transactions</div>", unsafe_allow_html=True)
                st.dataframe(neg_total.head(50), use_container_width=True)
            if not zero_total.empty:
                st.markdown("<div class='section-title'>Zero total transactions</div>", unsafe_allow_html=True)
                st.dataframe(zero_total.head(50), use_container_width=True)

    # Item-level anomalies
    if not tx_items.empty:
        weird = pd.DataFrame()
        if "price" in tx_items.columns:
            weird_price = tx_items[tx_items["price"] < 0]
            weird = pd.concat([weird, weird_price])
        if "quantity" in tx_items.columns:
            weird_qty = tx_items[tx_items["quantity"] <= 0]
            weird = pd.concat([weird, weird_qty])

        st.markdown("<div class='section-title'>Suspicious line items</div>", unsafe_allow_html=True)
        st.write("Negative prices, zero quantities, etc.")

        if weird.empty:
            st.success("No obvious anomalies in item-level data for current filters.")
        else:
            st.dataframe(weird.drop_duplicates().head(100), use_container_width=True)

    # Duplicate-like transactions: same phone+date+total_price
    if {"phone", "date", "total_price"}.issubset(tx.columns):
        dupe_key = tx.groupby(["phone", "date", "total_price"])["transaction_id"].transform("count")
        dupes = tx[dupe_key > 1].sort_values(["phone", "date", "total_price"])

        st.markdown("<div class='section-title'>Potential duplicate transactions</div>", unsafe_allow_html=True)
        if dupes.empty:
            st.success("No obvious duplicate transactions for the current filters.")
        else:
            st.dataframe(dupes.head(100), use_container_width=True)


# --- Main ---
def main():
    st.title("📊 Venmito Customer Insights Dashboard")

    if not DB_PATH.exists():
        st.error(f"Database not found at {DB_PATH}. Run scripts/build_db.py first.")
        return

    with st.spinner("Loading data..."):
        data = load_data(DB_PATH)

    filtered = apply_global_filters(data)
    view_mode = filtered["view_mode"]

    tab_overview, tab_customers, tab_promos, tab_store, tab_quality = st.tabs(
        [
            "Overview",
            "Customers",
            "Promotions",
            "Stores & Products",
            "Data Quality",
        ]
    )

    with tab_overview:
        render_overview(filtered, view_mode)

    with tab_customers:
        render_customers(filtered, view_mode)

    with tab_promos:
        render_promotions(filtered, view_mode)

    with tab_store:
        render_store_products(filtered, view_mode)

    with tab_quality:
        render_data_quality(filtered, view_mode)


if __name__ == "__main__":
    main()
