import pandas as pd
from pathlib import Path

# ==========================================================
# LOAD MASTERS
# ==========================================================

product_master = pd.read_csv(
    "./outputs/product_master.csv"
)

supplier_master = pd.read_csv(
    "./outputs/supplier_master.csv"
)

# ==========================================================
# FILES TO ENRICH
# ==========================================================

files = [

    "inventory_snapshot.csv",
    "inventory_gaps.csv",
    "supplier_item_mapping.csv"

]

for file in files:

    if not Path(file).exists():
        continue

    print(f"Processing {file}")

    df = pd.read_csv(file)

    # ------------------------------------------------------
    # PRODUCT INFO
    # ------------------------------------------------------

    if "item_id" in df.columns:

        df = df.merge(
            product_master[
                [
                    "item_id",
                    "product_name",
                    "brand",
                    "unit_size"
                ]
            ],
            on="item_id",
            how="left"
        )

    # ------------------------------------------------------
    # SUPPLIER INFO
    # ------------------------------------------------------

    if "supplier_id" in df.columns:

        df = df.merge(
            supplier_master[
                [
                    "supplier_id",
                    "supplier_name",
                    "supplier_type"
                ]
            ],
            on="supplier_id",
            how="left"
        )

    output_file = (
        file.replace(
            ".csv",
            "_enriched.csv"
        )
    )

    df.to_csv(
        output_file,
        index=False
    )

    print(f"Saved {output_file}")

print("\nDone.")