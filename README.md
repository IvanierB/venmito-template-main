# Venmito Customer 360 — Customer Insights Dashboard

**Author:** Ivanier Bellido  
**Email:** <ivanierb@gmail.com>  

---

## Project Overview

This project builds a complete **Customer 360 analytics system** for Venmito. The goal is to take fragmented customer, transaction, promotion, and transfer data coming from different sources and formats, unify it into a clean data model, and expose meaningful insights through an interactive dashboard.

The focus of this project is **decision support**. Everything—from the data model to the dashboard design—was built to help managers understand customer behavior, revenue drivers, and promotion effectiveness in a clear and intuitive way.

The project is designed to run locally on **Mac or Linux** with minimal setup.

---

## What the Project Does

- Ingests raw data from multiple file formats (JSON, YAML, CSV, XML)
- Matches customers across sources using normalized identifiers
- Creates a single, unified `customer_id`
- Enriches transactions and promotions with customer information
- Stores clean, structured data in a SQLite database
- Displays insights through an interactive Streamlit dashboard

---

## Technologies Used

- **Python** – main language for data processing and the dashboard  
- **Pandas** – data ingestion, cleaning, transformation, and aggregation  
- **SQLite** – lightweight database used as the final data store  
- **Streamlit** – interactive dashboard framework  
- **Altair** – clean, declarative data visualizations  

These tools were chosen because they are lightweight, widely supported, easy to run locally, and well suited for analytics and prototyping.

---

## Project Structure

```

venmito-template-main/
│
├── data/
│   ├── (raw input files)
│   └── processed/
│       └── venmito.db          # Generated SQLite database
│
├── scripts/
│   ├── test_ingest.py          # Validates data ingestion
│   └── build_db.py             # Builds the full database
│
├── src/
│   └── venmito/
│       ├── ingest/             # Data loaders (JSON, YAML, etc.)
│       └── match/              # Customer matching logic
│
├── app/
│   └── venmito_dashboard.py    # Streamlit dashboard
│
└── README.md

````

---

## Data Model Overview

The data pipeline produces the following tables in `venmito.db`:

- **customers** – unified customer dimension with normalized contact info  
- **json_customer_map** – maps JSON customer IDs to unified customer IDs  
- **yaml_customer_map** – maps YAML customer IDs to unified customer IDs  
- **transactions** – transaction-level data  
- **transaction_items** – item-level transaction data  
- **promotions** – promotion campaigns and responses  
- **transfers** – peer-to-peer transfers  

This structure ensures that all downstream analysis is based on a single, consistent customer identity.

---

## Dashboard Overview

The dashboard is divided into five main sections:

### Overview

High-level executive summary including:

- Total revenue
- Average order value
- Active customers
- Promotion response rate
- Revenue trends over time

### Customers

Customer behavior and segmentation:

- RFM-style customer segments
- Segment distribution
- Top customers by spend
- Recency and activity metrics

### Promotions

Promotion performance analysis:

- Overall funnel metrics (sent, contactable, responded)
- Interactive breakdowns by:
  - Promotion type
  - Device type
  - Customer country
  - Weekday sent
- Analysis of which factors most influence response behavior

### Stores & Products

Operational performance insights:

- Top-performing stores
- Best-selling products
- Basket analysis for co-purchased items (analyst mode)

### Data Quality

Quality and anomaly checks:

- Missing customer contact information
- Zero or negative transaction totals
- Suspicious line items
- Potential duplicate transactions

---

## Key Design Decisions

### Customer Matching First

All analysis depends on reliable customer identity. Customer matching is performed before any metrics are calculated to avoid duplication and inconsistencies.

### SQLite as the Output Database

SQLite was chosen because it is:

- Portable (single file)
- Easy to inspect and debug
- Ideal for demos, analysis, and local execution

### Executive vs Analyst Views

The dashboard supports two modes:

- **Executive summary** for high-level insights
- **Analyst detail** for deeper exploration and raw data inspection

### Clear Visual Hierarchy

The dashboard emphasizes:

- Large, high-contrast KPIs
- A consistent color palette
- Simple charts focused on comparisons and trends

This makes insights easy to scan and interpret quickly.

---

## How to Run the Project (Mac or Linux)

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
````

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. (Optional) Test data ingestion

```bash
python scripts/test_ingest.py
```

This step verifies that raw data files are being read correctly.

### 4. Build the database

```bash
python scripts/build_db.py
```

This command processes all raw data and creates:

```
data/processed/venmito.db
```

### 5. Run the dashboard

```bash
streamlit run app/venmito_dashboard.py
```

The dashboard will automatically open in your browser.

---

## Using the Dashboard

- Use the **Global Filters** in the sidebar to filter by date range, store, country, and device type
- Switch between **Executive summary** and **Analyst detail** views
- Navigate through tabs to explore different aspects of the business
- Hover over charts to see detailed tooltips and additional context

---

## Notes and Troubleshooting

- If the database is missing, ensure `scripts/build_db.py` ran successfully
- Always run commands from the **project root directory**
- Make sure the virtual environment is activated before running scripts
