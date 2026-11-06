import numpy as np, pandas as pd, time
from scipy.optimize import linprog
from scipy.sparse import hstack, identity, diags, csr_matrix, vstack

d = pd.read_csv("Datasets/hostel_energy_dataset_3months.csv", parse_dates=["timestamp"]).set_index("timestamp")
T, days = len(d), d.index.normalize().nunique()
n = (d.total_consumption_kwh - d.solar_generation_kwh).values
tar = d.grid_tariff_inr_per_kwh.values
base_bill = (np.clip(n, 0, None) * tar).sum()

# ---- Assumptions (edit these) ----
CYCLE_LIFE = 4_000     # rated full cycles
CAL_LIFE   = 12        # years: battery is replaced at this age even if cycles remain
HORIZON    = 15        # years used for the total-profit figure
RT_EFF, C_RATE, FLOOR = 0.90, 0.5, 0.10
eta = np.sqrt(RT_EFF)
SIZES  = [25, 50, 75, 100, 150, 200, 300, 400, 600]
WEARS  = [0, 1.5, 3, 4.5, 6, 7.5, 9, 10.5]      # INR per kWh discharged, the dispatch "caution" knob

# constraint matrices (independent of battery size)
I = identity(T, format="csr"); Z = csr_matrix((T, T)); Zs = csr_matrix((T, T+1))
A_ub = hstack([I, -I, -I, Zs]).tocsr()                       # c - d - g <= -n
S_next = diags([np.ones(T)], [1], shape=(T, T+1)); S_now = diags([np.ones(T)], [0], shape=(T, T+1))
A_eq = hstack([-eta*I, I/eta, Z, S_next - S_now]).tocsr()    # soc_{t+1} = soc_t + eta c - d/eta

def dispatch(cap, wear):
    p = cap*C_RATE*0.5
    cost = np.concatenate([np.zeros(T), np.full(T, wear), tar, np.zeros(T+1)])
    bounds = [(0,p)]*T + [(0,p)]*T + [(0,None)]*T + [(FLOOR*cap, cap)]*(T+1)
    bounds[3*T] = (FLOOR*cap, FLOOR*cap); bounds[4*T] = (FLOOR*cap, FLOOR*cap)
    r = linprog(cost, A_ub=A_ub, b_ub=-n, A_eq=A_eq, b_eq=np.zeros(T), bounds=bounds, method="highs")
    assert r.status == 0
    g, dis = r.x[2*T:3*T], r.x[T:2*T]
    return float(g @ tar), dis.sum()

t0 = time.time(); rows = []
for cap in SIZES:
    for w in WEARS:
        bill, dis = dispatch(cap, w)
        rows.append({"cap": cap, "wear": w, "bill_91d": bill,
                     "saving_year": (base_bill-bill)*365/days,
                     "cycles_year": dis/(cap*(1-FLOOR))*365/days})
R = pd.DataFrame(rows); print("LP time", round(time.time()-t0), "s")

def best_per_size(price, saving_factor=1.0):
    out = []
    for cap, g in R.groupby("cap"):
        g = g.copy()
        g["life"] = np.minimum(CAL_LIFE, CYCLE_LIFE/g.cycles_year.clip(lower=1e-9))
        g["profit_year"] = saving_factor*g.saving_year - cap*price/g.life        # saving minus yearly cost of owning + replacing
        b = g.loc[g.profit_year.idxmax()]
        packs = int(np.ceil(HORIZON / b.life - 1e-9))                          # purchases within the horizon (initial + replacements)
        out.append({"battery_kwh": cap, "cycles_per_day": round(b.cycles_year/365,2), "replace_every_yrs": round(b.life,1),
                    "purchases_in_15y": packs, "bill_per_month": round((base_bill/days*30) - saving_factor*b.saving_year/365*30),
                    "net_profit_per_year": round(b.profit_year), f"net_profit_{HORIZON}y_lakh": round(b.profit_year*HORIZON/1e5,1)})
    return pd.DataFrame(out)

print(f"No battery: bill per month {base_bill/days*30:,.0f} INR")
scen = [("Price 25,000 per kWh (main case)", 25_000, 1.0), ("Price 18,000 per kWh", 18_000, 1.0),
        ("Price 35,000 per kWh", 35_000, 1.0), ("25,000 and savings 20% lower (monsoon/winter haircut)", 25_000, 0.8)]
summary = []
for name, price, f in scen:
    t = best_per_size(price, f); b = t.loc[t.net_profit_per_year.idxmax()]
    print(f"\n=== {name} ==="); print(t.to_string(index=False))
    summary.append({"scenario": name, "best_size_kwh": b.battery_kwh, "net_profit_per_year": b.net_profit_per_year,
                    "bill_per_month": b.bill_per_month, "cycles_per_day": b.cycles_per_day, "replace_every_yrs": b.replace_every_yrs})
    if price == 25_000 and f == 1.0: t.to_csv("battery_size_profit_curve.csv", index=False)
print("\nSUMMARY"); print(pd.DataFrame(summary).to_string(index=False))
pd.DataFrame(summary).to_csv("battery_size_optimum.csv", index=False)
