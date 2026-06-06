import pandas as pd

supplier_master = pd.read_csv("./outputs/supplier_master.csv")

supplier_names = {

    "SUP001": "Global Foods Distribution",
    "SUP002": "Prime Consumer Goods",

    "SUP003": "Metro Wholesale Partners",
    "SUP004": "Retail Source Network",
    "SUP005": "Evergreen Supply Chain",

    "SUP006": "ValueMart Procurement",
    "SUP007": "Budget Goods Supply",
    "SUP008": "CostEdge Distributors",

    "SUP009": "Rapid Fulfillment Services",
    "SUP010": "Express Supply Solutions",

    "SUP011": "West Coast Retail Supply",
    "SUP012": "Heartland Distribution Group"
}

supplier_master["supplier_name"] = (
    supplier_master["supplier_id"]
    .map(supplier_names)
)

supplier_master.to_csv(
    "supplier_master.csv",
    index=False
)

print("Supplier names updated")