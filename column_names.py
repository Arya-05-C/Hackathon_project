import pandas as pd

eda = pd.read_csv("./outputs/eda_sku_features.csv")
fc30 = pd.read_csv("./outputs/forecast_30_days.csv")

print("\nEDA Columns:")
print(eda.columns.tolist())

print("\nForecast Columns:")
print(fc30.columns.tolist())

print("\nEDA Shape:", eda.shape)
print("Forecast Shape:", fc30.shape)