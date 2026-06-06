import pandas as pd
import numpy as np

np.random.seed(42)

EDA_FILE = "./outputs/eda_sku_features.csv"
OUTPUT_FILE = "./outputs/product_master.csv"

eda = pd.read_csv(EDA_FILE)

# ==========================================================
# CATALOGS
# ==========================================================

foods_1_products = [
    "Organic Rice",
    "Whole Wheat Flour",
    "Brown Sugar",
    "Premium Salt",
    "Arabica Coffee",
    "Green Tea",
    "Corn Flakes",
    "Rolled Oats",
    "Cooking Oil",
    "Digestive Biscuits",
    "Basmati Rice",
    "Black Tea",
    "Pasta",
    "Peanut Butter",
    "Honey",
    "Tomato Ketchup",
    "Mayonnaise",
    "Breakfast Muesli",
    "Instant Coffee",
    "Hot Chocolate"
]

foods_2_products = [
    "Potato Chips",
    "Chocolate Cookies",
    "Frozen Pizza",
    "Vanilla Ice Cream",
    "Greek Yogurt",
    "Chocolate Bar",
    "Energy Drink",
    "Fruit Juice",
    "Frozen Vegetables",
    "Instant Noodles",
    "Cheese Slices",
    "Chicken Nuggets",
    "Frozen Fries",
    "Cup Noodles",
    "Protein Bar",
    "Soft Drink",
    "Sandwich Cookies",
    "Ice Pops",
    "Flavored Yogurt",
    "Snack Crackers"
]

household_products = [
    "Laundry Detergent",
    "Dishwashing Liquid",
    "Glass Cleaner",
    "Toilet Cleaner",
    "Trash Bags",
    "Paper Towels",
    "Toilet Paper",
    "Air Freshener",
    "Floor Cleaner",
    "Multi Surface Spray",
    "Fabric Softener",
    "Bathroom Cleaner",
    "Kitchen Cleaner",
    "Garbage Liners",
    "Tissue Box",
    "Hand Wash",
    "Surface Wipes",
    "Furniture Polish",
    "Room Spray",
    "Bleach Cleaner"
]

brands = [
    "FreshHarvest",
    "GoldenGrain",
    "MorningBrew",
    "HealthyStart",
    "SnackMax",
    "QuickBite",
    "CreamWorld",
    "DairyFresh",
    "PowerRush",
    "CleanPro",
    "Sparkle",
    "SoftHome",
    "FreshAir",
    "NatureSip",
    "FarmFresh"
]

sizes = [
    "250g","500g","750g","1kg",
    "250ml","500ml","1L","2L",
    "6 Pack","12 Pack","24 Pack"
]

products = []

for idx, row in eda.iterrows():

    dept = row["dept_id"]

    if dept == "FOODS_1":
        base = np.random.choice(foods_1_products)

    elif dept == "FOODS_2":
        base = np.random.choice(foods_2_products)

    else:
        base = np.random.choice(household_products)

    brand = np.random.choice(brands)
    size = np.random.choice(sizes)

    products.append({
        "item_id": row["item_id"],
        "product_name": f"{brand} {base} {idx+1}",
        "brand": brand,
        "unit_size": size,
        "dept_id": dept
    })

product_master = pd.DataFrame(products)

product_master.to_csv(
    OUTPUT_FILE,
    index=False
)

print(f"Saved {OUTPUT_FILE}")
print(product_master.head())