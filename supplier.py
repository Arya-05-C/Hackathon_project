import pandas as pd
import numpy as np

# ==========================================================
# CONFIG
# ==========================================================

EDA_FILE = "./outputs/eda_sku_features.csv"

SUPPLIER_OUTPUT = "./outputs/supplier_master.csv"
MAPPING_OUTPUT = "./outputs/supplier_item_mapping.csv"

np.random.seed(42)

# ==========================================================
# LOAD SKU DATA
# ==========================================================

eda = pd.read_csv(EDA_FILE)

print(f"Loaded {len(eda)} SKUs")

# ==========================================================
# SUPPLIER ARCHETYPES
# ==========================================================

supplier_configs = [

    # Strategic
    ("SUP001", "Strategic"),
    ("SUP002", "Strategic"),

    # Balanced
    ("SUP003", "Balanced"),
    ("SUP004", "Balanced"),
    ("SUP005", "Balanced"),

    # Cost
    ("SUP006", "Cost"),
    ("SUP007", "Cost"),
    ("SUP008", "Cost"),

    # Emergency
    ("SUP009", "Emergency"),
    ("SUP010", "Emergency"),

    # Regional
    ("SUP011", "Regional"),
    ("SUP012", "Regional"),
]

suppliers = []

# ==========================================================
# GENERATE SUPPLIER MASTER
# ==========================================================

for supplier_id, supplier_type in supplier_configs:

    if supplier_type == "Strategic":

        lead_time = np.random.randint(7, 13)
        reliability = np.random.randint(90, 99)
        quality = np.random.randint(90, 99)
        fill_rate = np.random.randint(92, 99)

        cost_factor = np.random.uniform(1.10, 1.25)
        risk_score = np.random.randint(5, 15)

        capacity = 10000

    elif supplier_type == "Balanced":

        lead_time = np.random.randint(5, 11)
        reliability = np.random.randint(80, 91)
        quality = np.random.randint(80, 91)
        fill_rate = np.random.randint(80, 95)

        cost_factor = np.random.uniform(0.95, 1.05)
        risk_score = np.random.randint(15, 30)

        capacity = 7000

    elif supplier_type == "Cost":

        lead_time = np.random.randint(10, 21)
        reliability = np.random.randint(65, 86)
        quality = np.random.randint(70, 86)
        fill_rate = np.random.randint(65, 90)

        cost_factor = np.random.uniform(0.75, 0.95)
        risk_score = np.random.randint(30, 60)

        capacity = 12000

    elif supplier_type == "Emergency":

        lead_time = np.random.randint(1, 5)
        reliability = np.random.randint(85, 96)
        quality = np.random.randint(80, 96)
        fill_rate = np.random.randint(85, 98)

        cost_factor = np.random.uniform(1.20, 1.50)
        risk_score = np.random.randint(10, 25)

        capacity = 3000

    else:  # Regional

        lead_time = np.random.randint(3, 9)
        reliability = np.random.randint(75, 91)
        quality = np.random.randint(75, 91)
        fill_rate = np.random.randint(75, 95)

        cost_factor = np.random.uniform(0.90, 1.10)
        risk_score = np.random.randint(20, 40)

        capacity = 5000

    suppliers.append({
        "supplier_id": supplier_id,
        "supplier_name": f"{supplier_type} Supplier {supplier_id[-3:]}",
        "supplier_type": supplier_type,
        "lead_time_days": lead_time,
        "reliability_score": reliability,
        "quality_score": quality,
        "fill_rate": fill_rate,
        "cost_factor": round(cost_factor, 3),
        "risk_score": risk_score,
        "capacity_units": capacity
    })

supplier_master = pd.DataFrame(suppliers)

supplier_master.to_csv(
    SUPPLIER_OUTPUT,
    index=False
)

print(f"Saved {SUPPLIER_OUTPUT}")

# ==========================================================
# BUILD SKU → SUPPLIER MAPPING
# ==========================================================

mapping_rows = []

supplier_lookup = supplier_master.set_index(
    "supplier_id"
).to_dict("index")

# Each SKU gets 4 suppliers
SUPPLIERS_PER_SKU = 4

for _, row in eda.iterrows():

    item_id = row["item_id"]

    mean_price = row["mean_price"]

    abc_class = row["abc_class"]

    # ------------------------------------------------------
    # Important SKUs get better suppliers
    # ------------------------------------------------------

    if abc_class == "A":

        candidate_pool = [
            "SUP001",
            "SUP002",
            "SUP003",
            "SUP004",
            "SUP005",
            "SUP009",
            "SUP010"
        ]

    elif abc_class == "B":

        candidate_pool = [
            "SUP003",
            "SUP004",
            "SUP005",
            "SUP006",
            "SUP007",
            "SUP011",
            "SUP012"
        ]

    else:

        candidate_pool = [
            "SUP006",
            "SUP007",
            "SUP008",
            "SUP011",
            "SUP012"
        ]

    selected_suppliers = np.random.choice(
        candidate_pool,
        size=min(SUPPLIERS_PER_SKU, len(candidate_pool)),
        replace=False
    )

    for supplier_id in selected_suppliers:

        supplier = supplier_lookup[supplier_id]

        supplier_price = (
            mean_price
            * supplier["cost_factor"]
            * np.random.uniform(0.95, 1.05)
        )

        mapping_rows.append({

            "item_id": item_id,

            "supplier_id": supplier_id,

            "supplier_type": supplier["supplier_type"],

            "supplier_price": round(
                supplier_price,
                2
            ),

            "lead_time_days":
                supplier["lead_time_days"],

            "reliability_score":
                supplier["reliability_score"],

            "quality_score":
                supplier["quality_score"],

            "fill_rate":
                supplier["fill_rate"],

            "risk_score":
                supplier["risk_score"],

            "capacity_units":
                supplier["capacity_units"]

        })

supplier_mapping = pd.DataFrame(mapping_rows)

supplier_mapping.to_csv(
    MAPPING_OUTPUT,
    index=False
)

print(f"Saved {MAPPING_OUTPUT}")

print("\nSummary")
print("=" * 60)

print(
    f"Suppliers: {len(supplier_master)}"
)

print(
    f"Mappings: {len(supplier_mapping)}"
)

print(
    f"Avg suppliers per SKU: "
    f"{len(supplier_mapping)/len(eda):.1f}"
)