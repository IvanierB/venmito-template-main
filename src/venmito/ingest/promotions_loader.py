from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_promotions_csv(path: str | Path) -> pd.DataFrame:
    """
    Load promotions.csv into a clean DataFrame.

    Columns (after cleaning):
        promotion_id     (from 'id')
        client_email
        telephone
        promotion        (promotion name)
        responded        ("Yes"/"No"/etc.)
        promotion_date   (datetime)
    """
    path = Path(path)
    df = pd.read_csv(path)

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    # Rename 'id' -> 'promotion_id' for clarity
    if "id" in df.columns:
        df = df.rename(columns={"id": "promotion_id"})

    # Normalize email/phone/response
    if "client_email" in df.columns:
        df["client_email"] = df["client_email"].astype(str).str.strip().str.lower()
        # Empty strings -> NaN
        df["client_email"] = df["client_email"].replace("", pd.NA)

    if "telephone" in df.columns:
        df["telephone"] = df["telephone"].astype(str).str.strip()

    if "responded" in df.columns:
        df["responded"] = (
            df["responded"]
            .astype(str)
            .str.strip()
            .str.title()  # "No" / "Yes"
        )

    if "promotion_date" in df.columns:
        df["promotion_date"] = pd.to_datetime(df["promotion_date"], errors="coerce")

    df["source"] = "promotions_csv"

    preferred_cols = [
        "promotion_id",
        "client_email",
        "telephone",
        "promotion",
        "responded",
        "promotion_date",
        "source",
    ]
    cols = [c for c in preferred_cols if c in df.columns]
    return df[cols].copy()
