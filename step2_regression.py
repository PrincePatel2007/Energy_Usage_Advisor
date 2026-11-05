import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error, r2_score

train = pd.read_csv("train.csv", index_col=0, parse_dates=True)
test  = pd.read_csv("test.csv",  index_col=0, parse_dates=True)

features = ["hour_sin","hour_cos","dow","is_weekend","is_peak","occupancy_pct",
    "is_exam_period","is_festival_or_holiday","outdoor_temp_c","humidity_pct","cloud_cover_pct",
    "lag_1d","lag_1w","roll_3h"]
target = "total_consumption_kwh"
Xtr, ytr, Xte, yte = train[features], train[target], test[features], test[target]

models = {
    "Naive (same slot yesterday)": None,
    "Ridge regression": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "Random forest": RandomForestRegressor(n_estimators=200, min_samples_leaf=3, random_state=0, n_jobs=-1),
}
rows, preds = [], {}
for name, m in models.items():
    p = test["lag_1d"].values if m is None else m.fit(Xtr, ytr).predict(Xte)
    preds[name] = p
    rows.append({"model": name,
                 "MAE (kWh/slot)": round(mean_absolute_error(yte, p), 3),
                 "MAPE (%)": round(100*np.mean(np.abs((yte-p)/yte)), 2),
                 "R2": round(r2_score(yte, p), 3)})
print(pd.DataFrame(rows).to_string(index=False))

# Error on special days (stress test)
mask = test.is_festival_or_holiday.values == 1
for name, p in preds.items():
    print(f"{name:30s} MAE on festival/holiday slots: {mean_absolute_error(yte[mask], p[mask]):.3f}")

rf = models["Random forest"]
imp = pd.Series(rf.feature_importances_, index=features).sort_values(ascending=False)
print("\nTop features:\n", imp.head(6).round(3).to_string())

out = test[[target]].copy(); out["pred_rf"] = preds["Random forest"]; out.to_csv("test_predictions.csv")
