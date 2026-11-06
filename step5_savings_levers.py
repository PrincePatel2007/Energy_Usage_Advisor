import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

d = pd.read_csv("Datasets/test.csv", index_col=0, parse_dates=True)
solar, tariff = d.solar_generation_kwh, d.grid_tariff_inr_per_kwh
peak = d.tariff_period == "peak"
hhmm = d.index.strftime("%H:%M")
def cost(total): return ((total - solar).clip(lower=0) * tariff).sum()
base = cost(d.total_consumption_kwh)

def window(t0, t1): return pd.Series((hhmm >= t0) & (hhmm <= t1), index=d.index)

def move(total, removed, win, cap, loss=0.0):
    """Take `removed` kWh out of their slots, put removed*(1+loss) into window slots:
    free solar first, then cheapest tariff. Done day by day. Returns new total series."""
    total = total.copy()
    for day, idx in d.groupby(d.index.date).groups.items():
        idx = pd.DatetimeIndex(idx)
        rem = removed.loc[idx]
        E = rem.sum() * (1 + loss)
        total.loc[idx] -= rem
        w = idx[win.loc[idx].values]
        head = (solar.loc[idx] - total.loc[idx]).clip(lower=0)
        alloc = pd.Series(0.0, index=idx)
        for t in head.loc[w].sort_values(ascending=False).index:
            if E <= 1e-9: break
            x = min(E, cap, head[t]); alloc[t] += x; E -= x
        for t in tariff.loc[w].sort_values(kind="stable").index:
            if E <= 1e-9: break
            x = min(E, cap - alloc[t]); alloc[t] += x; E -= x
        total.loc[idx] += alloc
    return total

# ---- Levers (each takes and returns the total-consumption series)
def L_laundry_pumps(t):
    t = move(t, d.laundry_machines_kwh, window("09:00","17:30"), 3.0)
    return move(t, d.water_pumps_kwh, window("09:00","16:30"), 1.5)
def L_geyser_storage(t):    # 60% of peak-time geyser energy pre-heated at midday, 12% storage loss
    return move(t, 0.6*d.water_heaters_kwh.where(peak, 0), window("10:00","15:30"), 6.0, loss=0.12)
def L_ac_setpoint(t):       # raise AC setpoint ~2 C -> about 12% less AC energy
    return t - 0.12*d.air_conditioners_kwh
def L_ac_precool(t):        # 25% of peak-time AC energy done earlier in the afternoon, 15% extra loss
    return move(t, 0.25*d.air_conditioners_kwh.where(peak, 0), window("14:00","17:30"), 6.0, loss=0.15)

def battery(total, cap_kwh, rt_eff=0.90, c_rate=0.5, floor=0.10):
    eta = np.sqrt(rt_eff); p = cap_kwh*c_rate*0.5      # kWh per half hour
    soc, cost_b, cycles = cap_kwh*floor, 0.0, 0.0
    for t, tot, sol, tar, pk in zip(d.index, total, solar, tariff, peak):
        surplus, imp = max(0, sol-tot), max(0, tot-sol)
        ch = min(surplus, p, (cap_kwh-soc)/eta); soc += ch*eta
        dis = min(imp, p, (soc-cap_kwh*floor)*eta) if pk else 0.0; soc -= dis/eta; cycles += dis
        cost_b += (imp - dis) * tar
    return cost_b, cycles/cap_kwh/ d.index.normalize().nunique()

days = d.index.normalize().nunique()
rows = []
def add(name, c, note=""): rows.append({"lever": name, "grid_cost_inr": round(c), "saving_inr": round(base-c),
                                       "saving_per_day_inr": round((base-c)/days,1), "saving_pct": round(100*(base-c)/base,2), "note": note})
add("Current schedule", base)
tot0 = d.total_consumption_kwh
levers = [("Shift laundry and pumps to midday", L_laundry_pumps),
          ("Pre-heat geyser water at midday (storage tank)", L_geyser_storage),
          ("AC setpoint +2 C", L_ac_setpoint),
          ("AC pre-cooling before evening peak", L_ac_precool)]
print("STANDALONE (each lever alone vs current schedule)")
for n, f in levers: add("Alone: " + n, cost(f(tot0)))
print(pd.DataFrame(rows).to_string(index=False)); rows_alone = list(rows)

rows.clear(); add("Current schedule", base)
t = tot0; steps = [("Current schedule", base)]
for n, f in levers:
    t = f(t); c = cost(t); add("+ " + n, c); steps.append((n, c))
print("\nCUMULATIVE (levers stacked in order)")
print(pd.DataFrame(rows).to_string(index=False))
t_levers = t

print("\nBATTERY ON TOP OF ALL BEHAVIOUR LEVERS (solar-charged, discharges in peak slots only)")
brows = []
for cap in [50, 100, 200, 400]:
    cb, cyc = battery(t_levers, cap)
    brows.append({"battery_kwh": cap, "grid_cost_inr": round(cb), "extra_saving_inr": round(cost(t_levers)-cb),
        "extra_saving_per_day": round((cost(t_levers)-cb)/days,1),
        "saving_per_kwh_capacity_per_day_inr": round((cost(t_levers)-cb)/days/cap,2), "full_cycles_per_day": round(cyc,2)})
bt = pd.DataFrame(brows); print(bt.to_string(index=False))

# ---- figure: cost after each stacked lever
labels = ["Current"] + ["+ laundry/pumps", "+ geyser storage", "+ AC setpoint", "+ AC pre-cool"]
vals = [c for _, c in steps]
plt.figure(figsize=(9,4)); plt.bar(labels, vals, color="#7F77DD")
for i, v in enumerate(vals): plt.text(i, v+300, f"{v:,.0f}", ha="center", fontsize=9)
plt.ylim(min(vals)*0.9, max(vals)*1.03); plt.ylabel("Grid cost, 29 days (INR)")
plt.title("Cost after stacking each behaviour change"); plt.tight_layout(); plt.savefig("levers.png", dpi=130)
pd.DataFrame(rows).to_csv("savings_levers.csv", index=False); bt.to_csv("battery_sizing.csv", index=False)
