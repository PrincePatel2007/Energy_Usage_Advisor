"""Hostel Energy Advisor - local app.
Put this file and ui.html in the SAME folder as step1_*.py ... step6_*.py, then run:  python app.py
It opens http://localhost:8000. Uploaded data never leaves this computer.
Each run happens in a fresh temporary folder, so your original files are never changed."""
import os, sys, re, io, json, glob, shutil, tempfile, threading, subprocess, uuid, webbrowser, traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATASET = "/Users/princepatel/AI Project/Datasets/hostel_energy_dataset_3months.csv"        # name the step scripts expect; also the built-in test file
STEPS = ["Checking your data", "Forecasting your usage", "Finding your usage patterns",
         "Testing smart scheduling", "Testing habit changes", "Sizing a battery"]
JOBS = {}

class UserError(Exception): pass

# ---------------------------------------------------------------- 1. make any hostel file look like our dataset
APPL = {"lighting_kwh": r"light", "ceiling_fans_kwh": r"fan", "air_conditioners_kwh": r"air_?cond|aircon|(^|_)ac(_|$)",
        "water_heaters_kwh": r"heater|geyser", "kitchen_mess_kwh": r"kitchen|mess",
        "refrigeration_water_cooler_kwh": r"refrig|cooler|fridge", "laundry_machines_kwh": r"laundry|washing",
        "electronics_wifi_kwh": r"electronic|wifi|computer", "water_pumps_kwh": r"pump", "common_areas_kwh": r"common"}

def find(cols, *pats, skip=()):
    for p in pats:
        for c in cols:
            if c not in skip and re.search(p, c): return c

def normalise(raw):
    raw.columns = [str(c).strip().lower().replace(" ", "_").lstrip("\ufeff") for c in raw.columns]
    cols, notes = list(raw.columns), []
    tc = find(cols, r"^timestamp$", r"time|date")
    sc = find(cols, r"^solar_generation_kwh$", r"solar.*gen", r"solar(?!.*(irrad|self|surplus|used))")
    miss = []
    if not tc: miss.append("a date and time column")
    if not sc: miss.append("a solar electricity made column (name contains “solar”)")
    ap = {k: find(cols, "^" + k + "$", p, skip=(tc, sc)) for k, p in APPL.items()}
    tot = find(cols, r"^total_consumption_kwh$", r"total.*consum", r"^total", skip=(tc, sc))
    if not tot and not any(ap.values()): miss.append("a total electricity used column (name contains “total”)")
    if miss: raise UserError("Your file is missing " + ", ".join(miss) + ".")
    ts = pd.to_datetime(raw[tc], errors="coerce"); ok = ts.notna()
    if ok.sum() < 48 * 21: raise UserError("We need at least 3 weeks of readable half-hourly data (3 months is best).")
    raw, ts = raw[ok], ts[ok]
    num = lambda c: pd.to_numeric(raw[c], errors="coerce").values
    out = pd.DataFrame({"timestamp": ts.values})
    out["solar_generation_kwh"] = num(sc)
    for k, c in ap.items(): out[k] = num(c) if c else 0.0
    out["total_consumption_kwh"] = num(tot) if tot else out[list(APPL)].sum(axis=1)
    tr = find(cols, r"^grid_tariff_inr_per_kwh$", r"tariff.*(inr|kwh|price)", r"^tariff$", r"price|rate", skip=(tc, sc, tot))
    out["grid_tariff_inr_per_kwh"] = num(tr) if tr else np.nan
    for k, pats, dflt in [("occupancy_pct", (r"occup",), 70.0), ("outdoor_temp_c", (r"temp",), 30.0),
                          ("humidity_pct", (r"humid",), 60.0), ("cloud_cover_pct", (r"cloud",), 30.0),
                          ("is_exam_period", (r"exam",), 0.0), ("is_festival_or_holiday", (r"festival|holiday",), 0.0)]:
        c = find(cols, "^" + k + "$", *pats, skip=(tc, sc, tot)); out[k] = num(c) if c else dflt
        if not c and k in ("occupancy_pct", "outdoor_temp_c", "cloud_cover_pct"): notes.append({"occupancy_pct": "occupancy", "outdoor_temp_c": "temperature", "cloud_cover_pct": "cloud cover"}[k] + " (set to a constant)")
    out = out.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    step = out.index.to_series().diff().median()
    if step != pd.Timedelta("30min"): raise UserError("Readings must be every 30 minutes (yours look like every %s)." % step)
    out = out.reindex(pd.date_range(out.index.min().floor("D"), out.index.max().ceil("D") - pd.Timedelta("30min"), freq="30min"))
    out = out.interpolate(limit=6, limit_area="inside").ffill().bfill().fillna(0)
    out.index.name = "timestamp"
    h = out.index.hour + out.index.minute / 60
    out["hour"] = h; out["is_weekend"] = (out.index.dayofweek >= 5).astype(int)
    t = out["grid_tariff_inr_per_kwh"]
    if t.isna().all() or tr is None:
        out["grid_tariff_inr_per_kwh"] = np.where((h >= 18) & (h < 22), 9.5, np.where((h >= 6) & (h < 18), 7.0, 5.5))
        notes.append("no price column, so we assumed Rs 5.5 at night, Rs 7 by day, Rs 9.5 from 6 pm to 10 pm")
    t = out["grid_tariff_inr_per_kwh"]; mx, mn = t.max(), t.min()
    out["tariff_period"] = np.where((t >= .95 * mx) & (mx > mn), "peak", np.where((t <= 1.05 * mn) & (mx > mn), "off_peak", "normal"))
    out["month"] = out.index.month
    return out, notes, [k for k, c in ap.items() if c]

# ---------------------------------------------------------------- 2. run the step files
def script(n):
    for pat in ("step%d_*.py" % n,) + (("step7_*.py",) if n == 6 else ()):
        g = sorted(glob.glob(os.path.join(HERE, pat)))
        if g: return g[0]
    raise UserError("Could not find step%d_*.py next to app.py." % n)

def run_step(n, wd, patch=None):
    src = open(script(n), encoding="utf-8").read()
    if patch: src = patch(src)
    p = os.path.join(wd, "run_step%d.py" % n); open(p, "w", encoding="utf-8").write(src)
    r = subprocess.run([sys.executable, p], cwd=wd, capture_output=True, text=True, timeout=1500,
                       env={**os.environ, "MPLBACKEND": "Agg"})
    if r.returncode: raise RuntimeError("step %d failed: %s" % (n, (r.stderr.strip().splitlines() or ["unknown error"])[-1]))

def job_thread(jid, raw_text, sample):
    J = JOBS[jid]; wd = J["wd"] = tempfile.mkdtemp(prefix="hostel_"); st = J["steps"]
    def mark(i, state, msg=""): st[i].update(state=state, msg=msg)
    try:
        mark(0, "run")
        raw = pd.read_csv(os.path.join(HERE, DATASET)) if sample else pd.read_csv(io.StringIO(raw_text))
        if sample and not os.path.exists(os.path.join(HERE, DATASET)): raise UserError("Put %s in the app folder to use the test file." % DATASET)
        df, notes, have = normalise(raw); df.to_csv(os.path.join(wd, DATASET))
        days = df.index.normalize().nunique()
        if days < 21: raise UserError("We need at least 3 weeks of data.")
        n_test = max(7, round(.3 * days)); last = df.index.max().normalize()
        tr_end = (last - pd.Timedelta(days=n_test)).strftime("%Y-%m-%d") + " 23:30"; te_start = (last - pd.Timedelta(days=n_test - 1)).strftime("%Y-%m-%d")
        def patch1(s):
            s2 = re.sub(r'df\.loc\[:"[^"]+"\]', 'df.loc[:"%s"]' % tr_end, s); s2 = re.sub(r'df\.loc\["[\d-]+":\]', 'df.loc["%s":]' % te_start, s2)
            return s2
        run_step(1, wd, patch1); mark(0, "done")
        patch2 = lambda s: s.replace("for name, p in preds.items():\n    print(f\"{name:30s} MAE on festival", "for name, p in (preds.items() if mask.any() else []):\n    print(f\"{name:30s} MAE on festival")
        mark(1, "run"); run_step(2, wd, patch2); mark(1, "done")
        if len(have) >= 4:
            mark(2, "run"); run_step(3, wd); mark(2, "done")
        else: mark(2, "skip", "needs at least 4 appliance columns")
        mark(3, "run"); run_step(4, wd); mark(3, "done")
        mark(4, "run"); run_step(5, wd); mark(4, "done")
        mark(5, "run"); run_step(6, wd); mark(5, "done")
        J["result"] = build_result(wd, df, notes, have, days)
    except UserError as e: J["error"] = str(e)
    except Exception as e: J["error"] = str(e) if isinstance(e, RuntimeError) else "Something went wrong: %s" % e; traceback.print_exc()
    J["done"] = True

# ---------------------------------------------------------------- 3. turn the step outputs into plain answers
LEVERS = {"laundry": ("Run laundry and water pumps in the middle of the day", "Midday solar power is free and evenings cost the most. Ask laundry and pump staff to work between 9 am and 5 pm.", "Free"),
          "setpoint": ("Set air conditioners 2 °C warmer", "26 °C instead of 24 °C uses about 12% less AC power and most people barely notice.", "Hostel rule"),
          "pre-cool": ("Cool rooms in the afternoon, before the evening rush", "Start cooling between 2 pm and 5:30 pm while solar is strong, so less AC runs when power is expensive.", "Hostel rule"),
          "geyser": ("Heat water at midday and store it in an insulated tank", "Instead of heating water in the evening, heat it from midday sun. Needs an insulated storage tank.", "Equipment")}

def build_result(wd, df, notes, have, days):
    rd = lambda f, **k: pd.read_csv(os.path.join(wd, f), **k)
    r = {"days": int(days), "rows": len(df), "start": str(df.index.min().date()), "end": str(df.index.max().date()),
         "notes": notes, "appliances_found": len(have)}
    # forecast quality (step 2)
    te = rd("test.csv", index_col=0, parse_dates=True); pr = rd("test_predictions.csv", index_col=0, parse_dates=True)
    y, mean = te["total_consumption_kwh"], te["total_consumption_kwh"].mean()
    mae, naive = float((y - pr["pred_rf"]).abs().mean()), float((y - te["lag_1d"]).abs().mean())
    r["forecast"] = {"mae": round(mae, 2), "naive_mae": round(naive, 2), "error_pct": round(100 * mae / mean, 1),
                     "better_pct": round(100 * (naive - mae) / naive, 1)}
    # busiest hours
    g = df.groupby(df.index.hour)
    use, sun = g["total_consumption_kwh"].mean(), g["solar_generation_kwh"].mean()
    r["hourly"] = {"use": [round(v, 2) for v in use], "solar": [round(v, 2) for v in sun]}
    r["busy"] = sorted(int(h) for h in use.sort_values(ascending=False).index[:3])
    # usage patterns (step 3)
    if os.path.exists(os.path.join(wd, "cluster_labels.csv")):
        d = df.join(rd("cluster_labels.csv", index_col=0, parse_dates=True))
        c = d.groupby("cluster").agg(n=("hour", "size"), kwh=("total_consumption_kwh", "mean"), sun=("solar_generation_kwh", "mean"))
        names = {}; left = list(c.index)
        names[c.kwh.idxmax()] = "Heaviest-use periods"; left.remove(c.kwh.idxmax())
        if left: s = c.loc[left].sun.idxmax(); names[s] = "Sunny daytime"; left.remove(s)
        if left: q = c.loc[left].kwh.idxmin(); names[q] = "Quiet periods"; left.remove(q)
        for k in left: names[k] = "Busy but not peak"
        r["patterns"] = [{"name": names[k], "hours_per_day": round(v.n / days / 2, 1), "kwh": round(v.kwh, 1)} for k, v in c.sort_values("kwh", ascending=False).iterrows()]
        r["has_cluster_img"] = os.path.exists(os.path.join(wd, "clusters.png"))
    # smart scheduling (step 4) and habit levers (step 5)
    td = max(1, te.index.normalize().nunique()); M = 30 / td
    adv = rd("advisor_schedule.csv", index_col=0, parse_dates=True)
    r["schedule_saving_month"] = round(float(adv.cost_old.sum() - adv.cost_new.sum()) * M)
    lv = rd("savings_levers.csv"); base = float(lv.iloc[0].grid_cost_inr); plan, prev = [], base
    for _, row in lv.iloc[1:].iterrows():
        key = next((k for k in LEVERS if k in row.lever.lower()), None)
        s = (prev - float(row.grid_cost_inr)) * M; prev = float(row.grid_cost_inr)
        if key and s > 1: plan.append({"name": LEVERS[key][0], "how": LEVERS[key][1], "effort": LEVERS[key][2], "save": round(s)})
    plan.sort(key=lambda p: -p["save"]); r["plan"] = plan
    r["bill_month"], r["after_month"] = round(base * M), round(prev * M)
    # battery (step 6)
    cur = rd("battery_size_profit_curve.csv"); sc = rd("battery_size_optimum.csv")
    full_base = float((np.clip(df.total_consumption_kwh - df.solar_generation_kwh, 0, None) * df.grid_tariff_inr_per_kwh).sum() / days * 30)
    r["battery"] = {"base_bill_month": round(full_base),
        "curve": [{"kwh": int(x.battery_kwh), "bill": round(x.bill_per_month), "profit": round(x.net_profit_per_year), "replace": float(x.replace_every_yrs)} for x in cur.itertuples()],
        "scenarios": [{"name": x.scenario, "kwh": float(x.best_size_kwh), "profit": round(x.net_profit_per_year)} for x in sc.itertuples()]}
    return r

# ---------------------------------------------------------------- 4. tiny web server
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, code, body, ctype="application/json"):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/": return self.send(200, open(os.path.join(HERE, "ui.html"), "rb").read(), "text/html; charset=utf-8")
        J = JOBS.get(q.get("job", [""])[0])
        if u.path == "/api/status" and J:
            return self.send(200, {"steps": J["steps"], "done": J["done"], "error": J["error"], "result": J["result"]})
        if u.path == "/api/img" and J and os.path.exists(os.path.join(J["wd"], "clusters.png")):
            return self.send(200, open(os.path.join(J["wd"], "clusters.png"), "rb").read(), "image/png")
        self.send(404, {"error": "not found"})
    def do_POST(self):
        u = urlparse(self.path); body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8", "replace")
        if u.path != "/api/run": return self.send(404, {"error": "not found"})
        jid = uuid.uuid4().hex[:8]
        JOBS[jid] = {"steps": [{"name": n, "state": "wait", "msg": ""} for n in STEPS], "done": False, "error": None, "result": None, "wd": ""}
        threading.Thread(target=job_thread, args=(jid, body, "sample" in parse_qs(u.query)), daemon=True).start()
        self.send(200, {"job": jid})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000)); srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print("Hostel Energy Advisor running at http://localhost:%d  (press Ctrl+C to stop)" % port)
    threading.Timer(1, lambda: webbrowser.open("http://localhost:%d" % port)).start()
    try: srv.serve_forever()
    except KeyboardInterrupt: pass
