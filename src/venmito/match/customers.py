from __future__ import annotations

from typing import Tuple
import pandas as pd


def _normalize_email(series: pd.Series) -> pd.Series:
    """Lowercase + strip, preserving missing values."""
    return series.astype("string").str.strip().str.lower()


def build_customers(
    people_json: pd.DataFrame,
    people_yaml: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Build a unified customers table plus mapping tables from the people_json and people_yaml sources.

    Returns:
        customers_df: unified customers dimension
        json_map_df: mapping from json customer_id -> unified customer_id
        yaml_map_df: mapping from yaml customer_id -> unified customer_id
    """
    pj = people_json.copy()
    py = people_yaml.copy()

    # Normalize emails for matching
    pj["email_norm"] = _normalize_email(pj["email"])
    py["email_norm"] = _normalize_email(py["email"])

    # Build a full_name column for JSON if not present
    if "full_name" not in pj.columns:
        pj["full_name"] = (
            pj.get("first_name", "").astype("string").str.strip()
            + " "
            + pj.get("last_name", "").astype("string").str.strip()
        ).str.strip()

    # For YAML, loader should already have full_name or name
    if "full_name" not in py.columns:
        if "name" in py.columns:
            py["full_name"] = py["name"].astype("string").str.strip()
        else:
            py["full_name"] = pd.NA

    # Preserve original IDs for mapping
    pj["json_customer_id"] = pj.get("customer_id")
    py["yaml_customer_id"] = py.get("customer_id")

    # === 1) Match by normalized email (outer join) ===
    merged = pj.merge(
        py,
        on="email_norm",
        how="outer",
        suffixes=("_json", "_yaml"),
        indicator=True,
    )

    def coalesce_first(row: pd.Series, *cols: str):
        """Return the first non-null, non-empty value among the given columns."""
        for col in cols:
            if col is None or col not in row.index:
                continue
            v = row[col]
            if v is not None and not pd.isna(v) and v != "":
                return v
        return pd.NA

    customer_records = []
    json_map_records = []
    yaml_map_records = []

    next_customer_id = 1

    for _, row in merged.iterrows():
        has_json = pd.notna(row.get("json_customer_id"))
        has_yaml = pd.notna(row.get("yaml_customer_id"))

        if has_json and has_yaml:
            source_flags = "json+yaml"
        elif has_json:
            source_flags = "json"
        elif has_yaml:
            source_flags = "yaml"
        else:
            source_flags = ""

        # Coalesce attributes from JSON / YAML
        full_name = coalesce_first(row, "full_name_json", "full_name_yaml")
        first_name = row.get("first_name", pd.NA)
        last_name = row.get("last_name", pd.NA)

        email = row.get("email_norm", pd.NA)

        # Phone: try typical column names on both sides
        phone = coalesce_first(
            row,
            "telephone_json",
            "phone_json",
            "telephone_yaml",
            "phone_yaml",
        )

        # Location fields (we're defensive with possible column names)
        city = coalesce_first(
            row,
            "city_json",
            "city_yaml",
            "location_city_json",
            "location_city_yaml",
        )
        country = coalesce_first(
            row,
            "country_json",
            "country_yaml",
            "location_country_json",
            "location_country_yaml",
        )

        dob = coalesce_first(row, "dob_json", "dob_yaml")

        # Device flags: OR across sources
        dev_android = bool(
            (row.get("device_android_json", False) is True)
            or (row.get("device_android_yaml", False) is True)
        )
        dev_iphone = bool(
            (row.get("device_iphone_json", False) is True)
            or (row.get("device_iphone_yaml", False) is True)
        )
        dev_desktop = bool(
            (row.get("device_desktop_json", False) is True)
            or (row.get("device_desktop_yaml", False) is True)
        )

        unified_id = next_customer_id
        next_customer_id += 1

        customer_records.append(
            {
                "customer_id": unified_id,
                "json_customer_id": row.get("json_customer_id"),
                "yaml_customer_id": row.get("yaml_customer_id"),
                "full_name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "phone": phone,
                "city": city,
                "country": country,
                "dob": dob,
                "device_android": dev_android,
                "device_iphone": dev_iphone,
                "device_desktop": dev_desktop,
                "source_flags": source_flags,
            }
        )

        if pd.notna(row.get("json_customer_id")):
            json_map_records.append(
                {
                    "json_customer_id": row.get("json_customer_id"),
                    "customer_id": unified_id,
                }
            )

        if pd.notna(row.get("yaml_customer_id")):
            yaml_map_records.append(
                {
                    "yaml_customer_id": row.get("yaml_customer_id"),
                    "customer_id": unified_id,
                }
            )

    customers_df = pd.DataFrame(customer_records)
    json_map_df = pd.DataFrame(json_map_records).drop_duplicates()
    yaml_map_df = pd.DataFrame(yaml_map_records).drop_duplicates()

    return customers_df, json_map_df, yaml_map_df
