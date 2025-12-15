from pathlib import Path
import sys
import pathlib
# Make sure src/ is discoverable
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from venmito.ingest.people_loader import load_people_json, load_people_yaml
from venmito.ingest.transfers_loader import load_transfers_csv
from venmito.ingest.promotions_loader import load_promotions_csv
from venmito.ingest.transactions_loader import load_transactions_xml
from venmito.match.customers import build_customers


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW = PROJECT_ROOT / "data"


def main():
    people_json = load_people_json(RAW / "people.json")
    people_yaml = load_people_yaml(RAW / "people.yml")
    transfers = load_transfers_csv(RAW / "transfers.csv")
    promotions = load_promotions_csv(RAW / "promotions.csv")
    tx_header, tx_items = load_transactions_xml(RAW / "transactions.xml")
    customers, json_map, yaml_map = build_customers(people_json, people_yaml)

    print("people_json:", people_json.head(2), "\n")
    print("people_yaml:", people_yaml.head(2), "\n")
    print("transfers:", transfers.head(2), "\n")
    print("promotions:", promotions.head(2), "\n")
    print("transactions header:", tx_header.head(5), "\n")
    print("transaction items:", tx_items.head(5), "\n")
    print("customers:", customers.head(5), "\n")
    print("json_map:", json_map.head(5), "\n")
    print("yaml_map:", yaml_map.head(5), "\n")


if __name__ == "__main__":
    main()
