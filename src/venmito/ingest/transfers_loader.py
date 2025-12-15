from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_transfers_csv(path: str | Path) -> pd.DataFrame:
    """
    Load transfers.csv into a clean DataFrame.

    Columns (after cleaning):
        sender_id     (string or int)
        recipient_id  (string or int)
        amount        (float)
        date          (datetime)
    """
    path = Path(path)
    df = pd.read_csv(path)

    # Normalize column names (strip spaces and lowercase)
    df.columns = [c.strip().lower() for c in df.columns]

    # Ensure expected columns exist
    expected = {"sender_id", "recipient_id", "amount", "date"}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"transfers.csv missing expected columns: {missing}")

    # Types
    df["sender_id"] = df["sender_id"].astype(str).str.strip()
    df["recipient_id"] = df["recipient_id"].astype(str).str.strip()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    df["source"] = "transfers_csv"
    return df
