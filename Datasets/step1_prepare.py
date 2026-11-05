import numpy as np, pandas as pd

# 1) LOAD
df = pd.read_csv("hostel_energy_dataset_3months.csv", parse_dates=["timestamp"])
df = df.sort_values("timestamp").set_index("timestamp")

# 2) SANITY CHECKS
print("shape:", df.shape)
print("missing values:", int(df.isna().sum().sum()))
print("duplicate timestamps:", int(df.index.duplicated().sum()))
print("slots per day (should all be 48):", df.groupby(df.index.date).size().unique())
assert (df.index.to_series().diff().dropna() == pd.Timedelta("30min")).all()
assert (df.solar_generation_kwh >= 0).all() and (df.total_consumption_kwh > 0).all()

# 3) FEATURES (only things known BEFORE the slot happens)
df["hour_sin"] = np.sin(2*np.pi*df.hour/24)
df["hour_cos"] = np.cos(2*np.pi*df.hour/24)
df["dow"] = df.index.dayofweek
df["lag_1d"] = df.total_consumption_kwh.shift(48)    # same slot yesterday
df["lag_1w"] = df.total_consumption_kwh.shift(336)   # same slot last week
df["roll_3h"] = df.total_consumption_kwh.shift(1).rolling(6).mean()  # last 3 hours
df["is_peak"] = (df.tariff_period == "peak").astype(int)
df = df.dropna()   # first 7 days have no weekly lag

# 4) TIME-BASED SPLIT (never shuffle)
train = df.loc[:"2026-10-10 23:30"]
test  = df.loc["2026-10-11":]
print("train:", train.shape, train.index.min().date(), "->", train.index.max().date())
print("test: ", test.shape,  test.index.min().date(),  "->", test.index.max().date())

# 5) FEATURE LISTS
forecast_features = ["hour_sin","hour_cos","dow","is_weekend","is_peak","occupancy_pct",
    "is_exam_period","is_festival_or_holiday","outdoor_temp_c","humidity_pct","cloud_cover_pct",
    "lag_1d","lag_1w","roll_3h"]
target = "total_consumption_kwh"
appliance_cols = ["lighting_kwh","ceiling_fans_kwh","air_conditioners_kwh","water_heaters_kwh",
    "kitchen_mess_kwh","refrigeration_water_cooler_kwh","laundry_machines_kwh",
    "electronics_wifi_kwh","water_pumps_kwh","common_areas_kwh"]   # used in step 3 (PCA)

train.to_csv("train.csv"); test.to_csv("test.csv")
print("naive baseline MAE (same slot yesterday):",
      round((test[target]-test["lag_1d"]).abs().mean(), 3), "kWh per slot")
