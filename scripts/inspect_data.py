from pathlib import Path
import json
import yaml
import pandas as pd
from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data"


def inspect_people_json():
    path = RAW / "people.json"
    print(f"\n=== {path.name} ===")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        print(f"Type: list, len={len(data)}")
        print("Sample record keys:", list(data[0].keys()))
        print("First record:", data[0])
    else:
        print(f"Top-level type: {type(data)}")
        print("Top-level keys:", list(data.keys()))


def inspect_people_yaml():
    path = RAW / "people.yml"
    print(f"\n=== {path.name} ===")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if isinstance(data, list):
        print(f"Type: list, len={len(data)}")
        print("Sample record keys:", list(data[0].keys()))
        print("First record:", data[0])
    else:
        print(f"Top-level type: {type(data)}")
        print("Top-level keys:", list(data.keys()))


def inspect_csv(filename: str):
    path = RAW / filename
    print(f"\n=== {filename} ===")
    df = pd.read_csv(path)
    print("Columns:", list(df.columns))
    print("Head(3):")
    print(df.head(3))


def inspect_transactions_xml():
    path = RAW / "transactions.xml"
    print(f"\n=== {path.name} ===")
    tree = etree.parse(str(path))
    root = tree.getroot()

    # grab first few transaction nodes
    txs = root.findall(".//transaction")[:3]
    print(f"Found {len(txs)} <transaction> elements (showing up to 3).")

    for i, tx in enumerate(txs, start=1):
        print(f"\nTransaction #{i}")
        print("Attributes:", tx.attrib)
        for child in list(tx):
            print(f"  Tag: {child.tag}, Text: {child.text}")


def main():
    inspect_people_json()
    inspect_people_yaml()
    inspect_csv("transfers.csv")
    inspect_csv("promotions.csv")
    inspect_transactions_xml()


if __name__ == "__main__":
    main()
