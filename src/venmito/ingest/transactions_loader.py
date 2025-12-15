from __future__ import annotations

from pathlib import Path
from typing import Tuple, List, Dict, Any

import pandas as pd
from lxml import etree


def load_transactions_xml(path: str | Path) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load transactions.xml into two DataFrames:

    1) transactions_df: one row per transaction
        - transaction_id
        - phone
        - store
        - date (datetime)
        - total_price (sum of line prices)
        - total_quantity (sum of quantities)
        - num_items (number of line items)
        - source = "transactions_xml_header"

    2) items_df: one row per line item
        - transaction_id
        - line_number (1..N per transaction)
        - product_name
        - price (line price)
        - price_per_item
        - quantity
        - store (denormalized)
        - date (denormalized)
        - source = "transactions_xml_items"
    """
    path = Path(path)
    tree = etree.parse(str(path))
    root = tree.getroot()

    tx_records: List[Dict[str, Any]] = []
    item_records: List[Dict[str, Any]] = []

    for tx in root.findall(".//transaction"):
        tx_id = tx.get("id")

        phone_elem = tx.find("phone")
        store_elem = tx.find("store")
        date_elem = tx.find("date")

        phone = phone_elem.text.strip() if phone_elem is not None and phone_elem.text else None
        store = store_elem.text.strip() if store_elem is not None and store_elem.text else None
        date_str = date_elem.text.strip() if date_elem is not None and date_elem.text else None

        total_price = 0.0
        total_quantity = 0
        num_items = 0

        items_container = tx.find("items")
        if items_container is not None:
            for line_number, item_elem in enumerate(items_container.findall("item"), start=1):
                # The inner <item> tag contains the product name
                name_elem = item_elem.find("item")
                price_elem = item_elem.find("price")
                ppi_elem = item_elem.find("price_per_item")
                qty_elem = item_elem.find("quantity")

                product_name = (
                    name_elem.text.strip()
                    if name_elem is not None and name_elem.text
                    else None
                )

                price_str = price_elem.text.strip() if price_elem is not None and price_elem.text else None
                ppi_str = ppi_elem.text.strip() if ppi_elem is not None and ppi_elem.text else None
                qty_str = qty_elem.text.strip() if qty_elem is not None and qty_elem.text else None

                # We'll convert to numeric later with pandas to handle errors consistently
                item_records.append(
                    {
                        "transaction_id": tx_id,
                        "line_number": line_number,
                        "product_name": product_name,
                        "price": price_str,
                        "price_per_item": ppi_str,
                        "quantity": qty_str,
                        "store": store,
                        "date": date_str,
                        "source": "transactions_xml_items",
                    }
                )

                num_items += 1

        tx_records.append(
            {
                "transaction_id": tx_id,
                "phone": phone,
                "store": store,
                "date": date_str,
                # We'll compute totals from the items_df after we convert to numeric
                # but we keep placeholders for now
                "source": "transactions_xml_header",
                # we will fill these later once items_df exists
                "total_price": None,
                "total_quantity": None,
                "num_items": num_items,
            }
        )

    # Build DataFrames
    transactions_df = pd.DataFrame(tx_records)
    items_df = pd.DataFrame(item_records)

    # Parse dates
    if "date" in transactions_df.columns:
        transactions_df["date"] = pd.to_datetime(transactions_df["date"], errors="coerce")
    if not items_df.empty and "date" in items_df.columns:
        items_df["date"] = pd.to_datetime(items_df["date"], errors="coerce")

    # Convert numeric columns in items_df
    if not items_df.empty:
        items_df["price"] = pd.to_numeric(items_df["price"], errors="coerce")
        items_df["price_per_item"] = pd.to_numeric(items_df["price_per_item"], errors="coerce")
        items_df["quantity"] = pd.to_numeric(items_df["quantity"], errors="coerce")

        # Compute totals per transaction from items_df
        agg = (
            items_df.groupby("transaction_id")
            .agg(
                total_price=("price", "sum"),
                total_quantity=("quantity", "sum"),
            )
            .reset_index()
        )

        # Merge back into transactions_df
        transactions_df = transactions_df.merge(
            agg, on="transaction_id", how="left", suffixes=("", "_agg")
        )

        # Overwrite placeholder totals with aggregated values
        transactions_df["total_price"] = transactions_df["total_price_agg"]
        transactions_df["total_quantity"] = transactions_df["total_quantity_agg"]
        transactions_df = transactions_df.drop(columns=["total_price_agg", "total_quantity_agg"])

    return transactions_df, items_df
