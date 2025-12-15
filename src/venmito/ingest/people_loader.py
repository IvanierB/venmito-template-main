from __future__ import annotations

from pathlib import Path
from typing import List

import json
import pandas as pd
import yaml


def load_people_json(path: str | Path) -> pd.DataFrame:
    """
    Load people from people.json into a normalized DataFrame.

    Expected structure: list of dicts like:
    {
        "id": "0001",
        "first_name": "Jamie",
        "last_name": "Bright",
        "telephone": "533-849-3913",
        "email": "Jamie.Bright@example.com",
        "devices": ["Android"],
        "location": {"City": "Montreal", "Country": "Canada"},
        "dob": "05/20/2000"
    }
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    df = pd.json_normalize(raw)

    # Normalize column names
    df = df.rename(
        columns={
            "id": "customer_id",
            "telephone": "phone",
            "location.City": "city",
            "location.Country": "country",
        }
    )

    # Email normalization
    if "email" in df.columns:
        df["email"] = df["email"].astype(str).str.strip().str.lower()

    # Full name
    if "first_name" in df.columns and "last_name" in df.columns:
        df["full_name"] = (df["first_name"].astype(str).str.strip() + " " +
                           df["last_name"].astype(str).str.strip())

    # Devices: list -> boolean flags
    df["device_android"] = df["devices"].apply(
        lambda v: "Android" in v if isinstance(v, list) else False
    )
    df["device_iphone"] = df["devices"].apply(
        lambda v: "Iphone" in v or "iPhone" in v if isinstance(v, list) else False
    )
    df["device_desktop"] = df["devices"].apply(
        lambda v: "Desktop" in v if isinstance(v, list) else False
    )

    # Date of birth: MM/DD/YYYY
    if "dob" in df.columns:
        df["dob"] = pd.to_datetime(df["dob"], format="%m/%d/%Y", errors="coerce")

    df["source"] = "people_json"

    # Keep a clean subset plus helpful fields
    preferred_cols: List[str] = [
        "customer_id",
        "first_name",
        "last_name",
        "full_name",
        "email",
        "phone",
        "city",
        "country",
        "dob",
        "device_android",
        "device_iphone",
        "device_desktop",
        "source",
    ]
    cols = [c for c in preferred_cols if c in df.columns]
    return df[cols].copy()
    

def load_people_yaml(path: str | Path) -> pd.DataFrame:
    """
    Load people from people.yml into a normalized DataFrame.

    Expected structure: list of dicts like:
    {
        'Android': 1,
        'Desktop': 0,
        'Iphone': 0,
        'city': 'Montreal, Canada',
        'email': 'Jamie.Bright@example.com',
        'id': 1,
        'name': 'Jamie Bright',
        'phone': '533-849-3913',
        'dob': 'May 20, 2000'
    }
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    df = pd.json_normalize(raw)

    # Normalize columns
    df = df.rename(
        columns={
            "id": "customer_id",
            "name": "full_name",
            "phone": "phone",
        }
    )

    # Email normalization
    if "email" in df.columns:
        df["email"] = df["email"].astype(str).str.strip().str.lower()

    # Split city into city/country if possible (e.g. "Montreal, Canada")
    if "city" in df.columns:
        city_split = df["city"].astype(str).str.split(",", n=1, expand=True)
        df["city_name"] = city_split[0].str.strip()
        if city_split.shape[1] > 1:
            df["country"] = city_split[1].str.strip()
        else:
            df["country"] = pd.NA

    # Devices: numeric flags 0/1
    df["device_android"] = df.get("Android", 0).fillna(0).astype(int).astype(bool)
    df["device_desktop"] = df.get("Desktop", 0).fillna(0).astype(int).astype(bool)
    df["device_iphone"] = df.get("Iphone", 0).fillna(0).astype(int).astype(bool)

    # Date of birth: "May 20, 2000"
    if "dob" in df.columns:
        df["dob"] = pd.to_datetime(df["dob"], errors="coerce")

    df["source"] = "people_yaml"

    preferred_cols: List[str] = [
        "customer_id",
        "full_name",
        "email",
        "phone",
        "city_name",
        "country",
        "dob",
        "device_android",
        "device_iphone",
        "device_desktop",
        "source",
    ]
    cols = [c for c in preferred_cols if c in df.columns]
    out = df[cols].copy()

    # For consistency with JSON output, call it "city"
    if "city_name" in out.columns:
        out = out.rename(columns={"city_name": "city"})

    return out
