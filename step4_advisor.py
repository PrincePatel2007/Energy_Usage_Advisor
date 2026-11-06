import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

test = pd.read_csv("Datasets/test.csv", index_col=0, parse_dates=True)
pred = pd.read_csv("Regression/test_predictions.csv", index_col=0, parse_dates=True)
d = test.join(pred[["pred_rf"]])

# ---- Flexible loads and their rules (everything else is never touched)
LOADS = {  # column: (window start, window end, cap kWh per slot)
    "laundry_machines_kwh": ("09:00", "17:30", 3.0),
    "water_pumps_kwh":      ("09:00", "16:30", 1.5),
}

def plan_day(day, use_forecast=True):
    """Re-schedule laundry and pumps within one day. Daily energy per load is preserved."""
    day = day.copy()
    demand = day.pred_rf if use_forecast else day.total_consumption_kwh
    shiftable_now = sum(day[c] for c in LOADS)
    base = demand - shiftable_now                    # forecast demand without flexible loads
    headroom = (day.solar_generation_kwh - base).clip(lower=0)   # free solar room per slot
    new = {}
    for col, (t0, t1, cap) in LOADS.items():
        total = day[col].sum()
        alloc = pd.Series(0.0, index=day.index)
        win = day.index[(day.index.strftime("%H:%M") >= t0) & (day.index.strftime("%H:%M") <= t1)]
        # 1) fill free solar room first (largest room first)
        for t in headroom[win].sort_values(ascending=False).index:
            if total <= 1e-9: break
            x = min(total, cap, headroom[t]); alloc[t] += x; total -= x; headroom[t] -= x
        # 2) leftover goes to the cheapest-tariff slots in the window
        order = day.loc[win].sort_values("grid_tariff_inr_per_kwh", kind="stable").index
        for t in order:
            if total <= 1e-9: break
            x = min(total, cap - alloc[t]); alloc[t] += x; total -= x
        new[col] = alloc
    return new

def evaluate(d, use_forecast):
    out = d.copy()
    for col in LOADS: out[col + "_new"] = 0.0
    for _, day in d.groupby(d.index.date):
        new = plan_day(day, use_forecast)
        for col in LOADS: out.loc[day.index, col + "_new"] = new[col]
    out["flex_old"] = sum(out[c] for c in LOADS)
    out["flex_new"] = sum(out[c + "_new"] for c in LOADS)
    out["total_new"] = out.total_consumption_kwh - out.flex_old + out.flex_new
    out["import_new"] = (out.total_new - out.solar_generation_kwh).clip(lower=0)
    out["cost_new"] = out.import_new * out.grid_tariff_inr_per_kwh
    return out

d["import_old"] = (d.total_consumption_kwh - d.solar_generation_kwh).clip(lower=0)
d["cost_old"] = d.import_old * d.grid_tariff_inr_per_kwh
adv = evaluate(d, use_forecast=True)      # uses the random forest forecast
orc = evaluate(d, use_forecast=False)     # perfect foresight (upper bound)

# sanity: energy preserved per day, only flexible loads changed
assert np.isclose(adv.total_new.sum(), d.total_consumption_kwh.sum())

base_cost = d.cost_old.sum()
res = pd.DataFrame({
  "scenario": ["Current schedule", "Advisor (RF forecast)", "Perfect foresight (upper bound)"],
  "grid_cost_inr": [base_cost, adv.cost_new.sum(), orc.cost_new.sum()],
  "grid_import_kwh": [d.import_old.sum(), adv.import_new.sum(), orc.import_new.sum()],
}).round(1)
res["saving_inr"] = (base_cost - res.grid_cost_inr).round(1)
res["saving_pct"] = (100*res.saving_inr/base_cost).round(2)
print(res.to_string(index=False))

peak = d.tariff_period == "peak"
print(f"\nFlexible load in peak tariff slots: before {d.loc[peak, list(LOADS)].sum().sum():.1f} kWh, "
      f"after {adv.loc[peak, [c+'_new' for c in LOADS]].sum().sum():.1f} kWh")
print(f"Flexible load as share of total: {100*adv.flex_old.sum()/d.total_consumption_kwh.sum():.1f}%")
days = d.index.normalize().nunique()
print(f"Average saving: {(base_cost-adv.cost_new.sum())/days:.1f} INR/day over {days} test days")

adv["action"] = np.where(adv.flex_new > adv.flex_old + 0.05, "run flexible loads now",
                 np.where(adv.flex_new < adv.flex_old - 0.05, "defer flexible loads", "no change"))
adv[["flex_old","flex_new","action","cost_old","cost_new"]].to_csv("advisor_schedule.csv")

daily = pd.DataFrame({"current": d.cost_old.groupby(d.index.date).sum(),
                      "advisor": adv.cost_new.groupby(adv.index.date).sum()})
daily.plot(kind="bar", figsize=(12,4), width=0.85, title="Daily grid cost (INR): current vs advisor")
plt.ylabel("INR"); plt.tight_layout(); plt.savefig("savings.png", dpi=130)
