#!/usr/bin/env python
from __future__ import annotations
import sys
import pathlib
from pandas.api.types import is_datetime64_any_dtype as is_datetime

# Add src/ to PYTHONPATH so "import venmito" works when running scripts/
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

"""
Build the Venmito SQLite database from raw files.

Steps:
1. Load raw data (JSON, YAML, CSV, XML) via ingestion loaders.
2. Build unified customers dimension + mapping tables.
3. Enrich promotions and transactions with customer_id (email/phone matching).
4. Persist all tables into data/processed/venmito.db (SQLite).
"""

import sqlite3
from pathlib import Path

import pandas as pd

from venmito.ingest.people_loader import load_people_json, load_people_yaml
from venmito.ingest.transfers_loader import load_transfers_csv
from venmito.ingest.promotions_loader import load_promotions_csv
from venmito.ingest.transactions_loader import load_transactions_xml
from venmito.match.customers import build_customers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def project_paths():
    """Return root, raw_dir, processed_dir, db_path."""
    root = Path(__file__).resolve().parents[1]
    raw_dir = root / "data" 
    processed_dir = root / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    db_path = processed_dir / "venmito.db"
    return root, raw_dir, processed_dir, db_path


def normalize_email(series: pd.Series) -> pd.Series:
    """Lowercase + strip, keep NaNs."""
    return series.astype("string").str.strip().str.lower()


def normalize_phone(series: pd.Series) -> pd.Series:
    """
    Strip non-digits from phone numbers.

    Example:
        '533-849-3913' -> '5338493913'
    """
    return series.astype("string").str.replace(r"\D+", "", regex=True)


def convert_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert any datetime64 columns in a DataFrame to ISO date strings (YYYY-MM-DD).

    This keeps SQLite happy (it stores them as TEXT) and still human-readable.
    """
    df = df.copy()
    for col in df.columns:
        if is_datetime(df[col]):
            # You could also use astype(str), but strftime keeps format consistent
            df[col] = df[col].dt.strftime("%Y-%m-%d")
    return df


# ---------------------------------------------------------------------------
# Build DB pipeline
# ---------------------------------------------------------------------------

def main():
    root, raw_dir, processed_dir, db_path = project_paths()
    print(f"Project root: {root}")
    print(f"Raw data dir: {raw_dir}")
    print(f"Output DB:    {db_path}")

    # ----------------------------
    # 1) Load raw data
    # ----------------------------
    print("\n[1/4] Loading raw data...")

    people_json = load_people_json(raw_dir / "people.json")
    people_yaml = load_people_yaml(raw_dir / "people.yml")
    transfers = load_transfers_csv(raw_dir / "transfers.csv")
    promotions = load_promotions_csv(raw_dir / "promotions.csv")
    tx_header, tx_items = load_transactions_xml(raw_dir / "transactions.xml")

    print(f"  people_json rows: {len(people_json)}")
    print(f"  people_yaml rows: {len(people_yaml)}")
    print(f"  transfers rows:   {len(transfers)}")
    print(f"  promotions rows:  {len(promotions)}")
    print(f"  tx_header rows:   {len(tx_header)}")
    print(f"  tx_items rows:    {len(tx_items)}")

    # ----------------------------
    # 2) Build unified customers
    # ----------------------------
    print("\n[2/4] Building customers dimension...")

    customers, json_map, yaml_map = build_customers(people_json, people_yaml)

    print(f"  customers rows:   {len(customers)}")
    print(f"  json_map rows:    {len(json_map)}")
    print(f"  yaml_map rows:    {len(yaml_map)}")

    # Prepare normalized email/phone for enrichment
    customers = customers.copy()
    customers["email_norm"] = normalize_email(customers["email"])
    customers["phone_norm"] = normalize_phone(customers["phone"])

    cust_email = (
        customers[["customer_id", "email_norm"]]
        .dropna()
        .drop_duplicates("email_norm")
    )
    cust_phone = (
        customers[["customer_id", "phone_norm"]]
        .dropna()
        .drop_duplicates("phone_norm")
    )

    # ----------------------------
    # 3) Enrich promotions & transactions with customer_id
    # ----------------------------
    print("\n[3/4] Enriching promotions and transactions with customer_id...")

    # ---- Promotions
    promo = promotions.copy()
    promo["email_norm"] = normalize_email(promo["client_email"])
    promo["phone_norm"] = normalize_phone(promo["telephone"])

    promo = promo.merge(
        cust_email.rename(columns={"customer_id": "customer_id_email"}),
        on="email_norm",
        how="left",
    )
    promo = promo.merge(
        cust_phone.rename(columns={"customer_id": "customer_id_phone"}),
        on="phone_norm",
        how="left",
    )

    # Prefer email match; fallback to phone match
    promo["customer_id"] = promo["customer_id_email"].fillna(
        promo["customer_id_phone"]
    )

    promo = promo.drop(
        columns=["email_norm", "phone_norm", "customer_id_email", "customer_id_phone"]
    )

    # ---- Transactions (header)
    tx = tx_header.copy()
    tx["phone_norm"] = normalize_phone(tx["phone"])

    tx = tx.merge(
        cust_phone.rename(columns={"customer_id": "customer_id_phone"}),
        on="phone_norm",
        how="left",
    )

    tx["customer_id"] = tx["customer_id_phone"]
    tx = tx.drop(columns=["phone_norm", "customer_id_phone"])

    # tx_items we leave as-is; it links via transaction_id

    # ----------------------------
    # 4) Persist to SQLite
    # ----------------------------
    print("\n[4/4] Writing tables to SQLite...")

    # Optional: delete existing DB to avoid stale schema
    if db_path.exists():
        print(f"  Removing existing DB at {db_path}")
        db_path.unlink()

    # Customers: explicitly convert dob to string for SQLite
    customers_sql = customers.copy()
    if "dob" in customers_sql.columns:
        customers_sql["dob"] = customers_sql["dob"].astype(str)
        
    json_map_sql = convert_datetimes(json_map)
    yaml_map_sql = convert_datetimes(yaml_map)
    transfers_sql = convert_datetimes(transfers)
    promo_sql = convert_datetimes(promo)
    tx_sql = convert_datetimes(tx)
    tx_items_sql = convert_datetimes(tx_items)

    conn = sqlite3.connect(db_path)

    try:
        # Dimensions / mapping
        customers_sql.to_sql("customers", conn, if_exists="replace", index=False)
        json_map_sql.to_sql("json_customer_map", conn, if_exists="replace", index=False)
        yaml_map_sql.to_sql("yaml_customer_map", conn, if_exists="replace", index=False)

        # Facts
        transfers_sql.to_sql("transfers", conn, if_exists="replace", index=False)
        promo_sql.to_sql("promotions", conn, if_exists="replace", index=False)
        tx_sql.to_sql("transactions", conn, if_exists="replace", index=False)
        tx_items_sql.to_sql("transaction_items", conn, if_exists="replace", index=False)

        print("  ✅ All tables written successfully:")
        print("     - customers")
        print("     - json_customer_map")
        print("     - yaml_customer_map")
        print("     - transfers")
        print("     - promotions")
        print("     - transactions")
        print("     - transaction_items")
    finally:
        conn.close()


    print("\nDone. You can now query data from:", db_path)


if __name__ == "__main__":
    main()
