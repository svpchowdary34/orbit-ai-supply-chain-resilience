# ==============================================================================
# ORBIT AI — Supply Chain Risk & Resilience Intelligence | ONE Google Colab cell
# See the disruption before it hits production.
# ==============================================================================
import subprocess, sys, os, re, json, zipfile, html, math, warnings
warnings.filterwarnings("ignore")
def _deps():
    try:
        from importlib.metadata import version
        if int(version("gradio").split(".")[0]) not in (4, 5): raise RuntimeError("gradio")
        for p in ("plotly", "requests", "pandas", "numpy"): version(p)
    except Exception:
        print("Installing dependencies (about a minute)...")
        try: subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "gradio>=4.44,<6", "plotly", "requests", "pandas", "numpy"]); print("Dependencies installed.")
        except Exception as e: print("Install warning:", type(e).__name__, "- check internet access and re-run.")
_deps()
try:
    import numpy as np, pandas as pd, plotly.graph_objects as go, gradio as gr, requests
except Exception as e:
    raise SystemExit("Libraries could not be imported (" + type(e).__name__ + "). Restart the runtime and re-run this cell.")

C = dict(bg="#14252D", sf="#253842", te="#80E0C0", am="#F0BF78", vi="#D2B8FF", tx="#F1F5F4", mu="#A5B6C0", co="#F18D88")
G = {}; TESTS = []; _DEMO = {}
BLANK = ["", "nan", "none", "n/a", "na", "-", "null", "nat"]
ASOF = pd.Timestamp("2026-10-26")
DEF = dict(win=90, tol=0, dw=8, hor=120, w=dict(rel=.25, vol=.15, qual=.15, openl=.15, crit=.15, sole=.15))
esc = lambda x: html.escape(str(x))
norm = lambda s: re.sub(r"\W+", "_", str(s).strip().lower()).strip("_")
nul = lambda v: v is None or (not isinstance(v, str) and bool(pd.isna(v)))
nf = lambda v: "—" if nul(v) else format(v, ",.0f")
fx = lambda v, d=1: "—" if nul(v) else format(v, "." + str(d) + "f")
pc0 = lambda v: "—" if nul(v) else format(v, ".0%")
pc1 = lambda v: "—" if nul(v) else format(v, ".1%")
money = lambda v: "—" if nul(v) else ("-$" if v < 0 else "$") + format(abs(v), ",.0f")
dts = lambda v: "—" if nul(v) else pd.Timestamp(v).strftime("%Y-%m-%d")
Td = lambda d: pd.Timedelta(days=int(d))
SEVC = {"High": C["co"], "Medium": C["am"], "Low": C["te"]}
def pill(s, col=None): col = col or SEVC.get(s, C["mu"]); return "<span class='pill' style='color:%s;border-color:%s'>%s</span>" % (col, col, esc(s))
def note(t, k="info"):
    col = {"info": C["mu"], "ok": C["te"], "warn": C["am"], "err": C["co"], "ai": C["vi"]}[k]
    return "<div class='note' style='border-left:3px solid %s'>%s</div>" % (col, t)
def card(lab, val, desc, col=C["te"]): return "<div class='kc'><div class='kl'>%s</div><div class='kv' style='color:%s'>%s</div><div class='kd'>%s</div></div>" % (lab, col, val, desc)
H = lambda t: "<div class='sec'>%s</div>" % t
def tbl(d, cols, fmt=None):
    fmt = fmt or {}; h = "<div class='tw'><table><tr>" + "".join("<th>%s</th>" % n for _, n in cols) + "</tr>"
    for _, r in d.iterrows(): h += "<tr>" + "".join("<td>%s</td>" % (fmt[k](r[k]) if k in fmt else ("—" if nul(r[k]) else esc(r[k]))) for k, _n in cols) + "</tr>"
    return h + "</table></div>"
def sty(f, h=380, t=""):
    f.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=C["tx"]), height=h, title=dict(text=t, x=.02), margin=dict(l=60, r=20, t=55, b=50), legend=dict(orientation="h", y=-.25), colorway=[C["te"], C["vi"], C["am"], C["co"], C["mu"]])
    return f
def empty(msg):
    f = go.Figure(); f.add_annotation(text=msg, showarrow=False, font=dict(color=C["mu"], size=14)); f.update_xaxes(visible=False); f.update_yaxes(visible=False); return sty(f, 300)
def banner(): return note("<b>Illustrative synthetic data.</b> Fictional suppliers, parts, orders and shipments with planted disruptions. Not live monitoring and not real company performance.", "warn") if G.get("demo") else ""
def clean_str(s):
    t = s.astype(str).str.strip(); return t.where(~(s.isna() | t.str.lower().isin(BLANK)), np.nan)
def to_num(s):
    if pd.api.types.is_numeric_dtype(s): return s.astype(float)
    return pd.to_numeric(s.astype(str).str.replace(r"[$,%£€₹\s]", "", regex=True), errors="coerce")
def to_dt(s):
    try: return pd.to_datetime(s, errors="coerce", format="mixed")
    except Exception: return pd.to_datetime(s, errors="coerce")
def read_csv_any(f):
    p = f if isinstance(f, str) else getattr(f, "name", f)
    try: d = pd.read_csv(p)
    except Exception: d = pd.read_csv(p, sep=None, engine="python", encoding_errors="replace")
    if d.empty: raise ValueError("A file contains no rows.")
    return d
def safe(kinds):
    def deco(fn):
        def w(*a):
            def out(msg, k): return tuple((note(msg, k) if i == 0 else "") if c == "h" else empty("No data") for i, c in enumerate(kinds))
            if "X" not in G: return out("Load data first.", "info")
            try: return fn(*a)
            except Exception as e: return out("Could not render this page: " + esc(e), "err")
        return w
    return deco

# ------------------------------ FICTIONAL synthetic supply chain (fixed seed) ------------------------------
CATS = ["Electronics", "Mechanical", "Plastics", "Metals", "Packaging", "Chemicals"]
def make_data(seed=7):
    r = np.random.default_rng(seed); A = ASOF; D = lambda n: A + Td(n); reg = ["Asia", "Europe", "North America", "South America"]; org = dict(zip(reg, ["Port A", "Port B", "Port C", "Port D"])); sup = []
    for i in range(40):
        lt = int(r.integers(7, 40)); sup.append(dict(supplier_id="S%02d" % (i + 1), supplier_name="Supplier %02d" % (i + 1), region=reg[i % 4], material_categories=CATS[i % 6] + ";" + CATS[(i + 3) % 6], standard_lead_time_days=lt, contractual_lead_time_days=lt, minimum_order_quantity=int(r.choice([50, 100, 200])),
                        unit_cost_multiplier=round(float(r.uniform(.95, 1.15)), 2), capacity_limit=int(r.integers(800, 5000)), quality_rate=round(float(r.uniform(.965, .995)), 3), historical_on_time_rate=round(float(r.uniform(.82, .97)), 2), alternate_supplier_status=str(r.choice(["approved", "requires_qualification"], p=[.6, .4]))))
    sup = pd.DataFrame(sup); sd = sup.set_index("supplier_id"); comp = []; ap = {}
    for j in range(100):
        cat = CATS[j % 6]; pool = [s.supplier_id for s in sup.itertuples() if cat in s.material_categories]; n_ap = 1 if r.random() < .35 else int(r.integers(2, 4)); ids = [str(x) for x in r.choice(pool, size=min(n_ap, len(pool)), replace=False)]
        if j == 16: cat = "Plastics"; ids = ["S03"]
        cid = "C%03d" % (j + 1); ap[cid] = ids
        comp.append(dict(component_id=cid, component_name="%s part %03d" % (cat, j + 1), category=cat, unit_cost=round(float(np.clip(r.lognormal(2.3, .9), .5, 300)), 2), criticality=5 if j == 16 else int(r.choice([1, 2, 3, 4, 5], p=[.15, .25, .3, .2, .1])),
                         shelf_life_days=180 if cat == "Chemicals" else np.nan, minimum_order_quantity=int(r.choice([50, 100, 200, 500])), standard_replenishment_days=int(sd.standard_lead_time_days[ids[0]]), approved_supplier_ids=";".join(ids)))
    comp = pd.DataFrame(comp); cm = comp.set_index("component_id").to_dict("index"); allc = list(comp.component_id); prods = ["P%02d" % (i + 1) for i in range(20)]; c17 = {"P03", "P05", "P08", "P12", "P15"}; non17 = [c for c in allc if c != "C017"]; bom = []
    for p in prods:
        cs = [str(x) for x in r.choice(non17, size=7 if p in c17 else 8, replace=False)] + (["C017"] if p in c17 else [])
        for c in cs:
            sub = [x for x in allc if cm[x]["category"] == cm[c]["category"] and x != c]
            bom.append(dict(finished_product_id=p, component_id=c, quantity_required_per_unit=int(r.integers(2, 4)) if c == "C017" else int(r.integers(1, 4)), acceptable_substitute_components=str(r.choice(sub)) if r.random() < .15 and sub else None, substitution_constraints="Requires engineering approval" if r.random() < .15 else None))
    bom = pd.DataFrame(bom); bq = {(b.finished_product_id, b.component_id): b.quantity_required_per_unit for b in bom.itertuples()}
    weeks = [A - Td(7 * (52 - k)) for k in range(52)]; dem = []; base = {}
    for p in prods:
        b = float(r.uniform(80, 300)); base[p] = b
        for k, w in enumerate(weeks):
            fc = b * (1 + .15 * math.sin(2 * math.pi * k / 52)); ac = fc * float(r.lognormal(0, .1))
            if p == "P05" and k >= 47: ac = fc * float(r.uniform(1.35, 1.5))
            dem.append(dict(product_id=p, period=w, actual_demand=round(ac), forecast_demand=round(fc), forecast_version="v1"))
    dem = pd.DataFrame(dem); pl = [p for p in sorted(c17) for _ in (0, 1)] + [str(r.choice(prods)) for _ in range(40)]; orders = []
    for i, p in enumerate(pl):
        st = D(r.integers(2, 22)) if i < 10 else D(r.integers(-3, 36)); cp = st + Td(r.integers(3, 9))
        orders.append(dict(production_order_id="MO%03d" % (i + 1), finished_product_id=p, quantity=int(round(base[p] * float(r.uniform(.5, 1.2)))), planned_start_date=st, planned_completion_date=cp, actual_completion_date=pd.NaT, priority=int(r.choice([1, 2, 3, 4, 5], p=[.1, .25, .35, .2, .1])),
                           status="In progress" if st <= A else "Planned", customer_due_date=cp + Td(r.integers(3, 13)), shortage_cost_per_day=int(r.integers(500, 4000))))
    pr = pd.DataFrame(orders); req = {c: 0.0 for c in allc}
    for o in orders:
        if o["status"] == "Planned":
            for (p, c), q in bq.items():
                if p == o["finished_product_id"]: req[c] += q * o["quantity"]
    dd = {c: sum(q * base[p] for (p, c2), q in bq.items() if c2 == c) / 7 for c in allc}; onh = {c: dd[c] * float(r.uniform(35, 90)) + 100 for c in allc}; onh["C017"] = req["C017"] * .30
    p5 = [c for (p, c), q in bq.items() if p == "P05" and c != "C017"]; planted = {"C017"}
    if p5: onh[p5[0]] = max(req[p5[0]] * .5, dd[p5[0]] * 8); planted.add(p5[0])
    for c in sorted([x for x in allc if x != "C017"], key=lambda x: -req[x])[:2]: onh[c] = req[c] * .6; planted.add(c)
    dl = []; n = 0
    for c in allc:
        start = -365 + int(r.integers(0, 40)); aps = ap[c]; w = [1.0] if len(aps) == 1 else [.6] + [.4 / (len(aps) - 1)] * (len(aps) - 1)
        while start <= -1:
            s = str(r.choice(aps, p=w)); n += 1; od = D(start); b_lt = float(sd.contractual_lead_time_days[s]); mon = (start + 365) / 365; lt = b_lt * float(r.lognormal(0, .12))
            if s == "S03": lt += 14 * mon ** 2 + float(r.normal(0, 2 * mon))
            if r.random() < (1 - float(sd.historical_on_time_rate[s])) * .7: lt += float(r.integers(2, 10))
            actual = od + Td(round(max(2, lt))); promised = od + Td(round(b_lt)); moq = max(cm[c]["minimum_order_quantity"], int(sd.minimum_order_quantity[s])); qty = int(max(moq, math.ceil(dd[c] * float(r.uniform(30, 50)) / moq) * moq)); done = actual <= A; fill = 1.0; dp = 1 - float(sd.quality_rate[s])
            if s == "S11" and start > -130: fill = float(r.uniform(.78, .92))
            elif r.random() < .03: fill = .9
            if s == "S19" and start > -100: dp = .08
            rec = int(round(qty * fill)) if done else 0
            dl.append(dict(purchase_order_id="PO%05d" % n, supplier_id=s, component_id=c, order_date=od, promised_date=promised, actual_delivery_date=actual if done else pd.NaT, ordered_quantity=qty, received_quantity=rec, defect_quantity=int(r.binomial(rec, dp)) if done else 0,
                           delivery_status="Delivered" if done else "Open", disruption_reason=str(r.choice(["Supplier production delay", "Customs", "Weather", "Capacity"])) if done and (actual - promised).days > 3 else None))
            start += int(r.integers(30, 60))
    dl = [x for x in dl if not (x["component_id"] == "C017" and x["delivery_status"] == "Open")]; n += 1; c17po = "PO%05d" % n
    dl.append(dict(purchase_order_id=c17po, supplier_id="S03", component_id="C017", order_date=D(-18), promised_date=D(2), actual_delivery_date=pd.NaT, ordered_quantity=int(math.ceil(req["C017"] * .8 / 100) * 100), received_quantity=0, defect_quantity=0, delivery_status="Open", disruption_reason=None))
    dl.sort(key=lambda x: x["order_date"]); openq = {}
    for x in dl:
        if x["delivery_status"] == "Open": openq[x["component_id"]] = openq.get(x["component_id"], 0) + x["ordered_quantity"]
    rgm = {"Asia": ["Sea", "Air"], "Europe": ["Rail", "Road", "Sea"], "North America": ["Road", "Rail"], "South America": ["Sea", "Air"]}; tt = dict(Sea=18, Air=3, Road=5, Rail=9); cost0 = dict(Sea=1200, Air=4500, Road=900, Rail=1500); tr = []
    for k, x in enumerate(dl[-500:]):
        rg = sd.region[x["supplier_id"]]; mode = str(r.choice(rgm[rg])); og = org[rg]; car = "CAR2" if (og == "Port A" and r.random() < .6) else str(r.choice(["CAR1", "CAR3", "CAR4"])); pdp = x["promised_date"] - Td(tt[mode] + 1); done = pd.notna(x["actual_delivery_date"]); eta = x["promised_date"]
        if done:
            lat = max(0, (x["actual_delivery_date"] - x["promised_date"]).days); adp = min(pdp + Td(int(r.integers(0, 2)) + max(0, lat - int(r.integers(0, 3)))), x["actual_delivery_date"] - Td(1)); aar = x["actual_delivery_date"]; stt = "Delivered"
        else:
            aar = pd.NaT; adp = pdp + Td(int(r.integers(0, 2))) if pdp <= A else pd.NaT; stt = "In transit" if pdp <= A else "Planned"
            if og == "Port A" and car == "CAR2": eta = x["promised_date"] + Td(r.integers(5, 10)); stt = "Delayed"
            elif r.random() < .04: adp = pd.NaT; pdp = A - Td(2); stt = "Delayed"
            if x["purchase_order_id"] == c17po: pdp, adp, eta, stt, car, mode, og = D(-6), D(-3), D(14), "Delayed", "CAR3", "Sea", "Port C"
        tr.append(dict(shipment_id="SH%04d" % (k + 1), purchase_order_id=x["purchase_order_id"], carrier_id=car, transport_mode=mode, origin=og, destination="Plant", planned_departure=pdp, actual_departure=adp, expected_arrival=eta, actual_arrival=aar, shipment_status=stt, estimated_transport_cost=round(cost0[mode] + x["ordered_quantity"] * .2)))
    tr = pd.DataFrame(tr); dls = pd.DataFrame(dl); inv = []
    for c in allc:
        for k in range(4):
            tot = onh[c] * (1 if k == 0 else float(r.uniform(.95, 1.3)))
            for wi, sh in (("W1", .6), ("W2", .4)):
                oh = int(round(tot * sh)); inv.append(dict(component_id=c, warehouse_id=wi, snapshot_date=A - Td(7 * k), on_hand_quantity=oh, reserved_quantity=int(oh * float(r.uniform(0, .06))), allocated_quantity=0 if c in planted else int(oh * float(r.uniform(0, .04))),
                                                           inbound_quantity=int(openq.get(c, 0)) if wi == "W1" else 0, safety_stock=int(round(dd[c] * 7)), reorder_point=int(round(dd[c] * (cm[c]["standard_replenishment_days"] + 7))), storage_capacity=int(oh * 4 + 500)))
    mit = []; mi = 0
    def addm(c, s, a, lead, cost, cap, q, prem, po=None):
        nonlocal mi; mi += 1; mit.append(dict(option_id="M%04d" % mi, component_id=c, supplier_id=s, action_type=a, estimated_lead_time=int(lead), estimated_cost=float(cost), capacity_limit=cap, qualification_status=q, unit_cost_premium=round(float(prem), 2), purchase_order_id=po))
    for c in allc: s0 = ap[c][0]; addm(c, s0, "Emergency purchase", max(4, round(.6 * sd.standard_lead_time_days[s0])), 250, int(sd.capacity_limit[s0] / 4), "approved", .25 * cm[c]["unit_cost"])
    for c in [str(x) for x in r.choice(allc, 30, replace=False)]:
        if c == "C017": continue
        pool = [s for s in sd.index if s not in ap[c]]; addm(c, str(r.choice(pool)), "Alternate supplier", r.integers(5, 25), r.integers(500, 2500), int(r.integers(300, 3000)), str(r.choice(["approved", "requires_qualification", "not_qualified"], p=[.5, .3, .2])), cm[c]["unit_cost"] * float(r.uniform(.05, .4)))
    addm("C017", "S27", "Alternate supplier", 7, 400, 2500, "approved", .35 * cm["C017"]["unit_cost"]); addm("C017", "S31", "Alternate supplier", 12, 1200, 4000, "requires_qualification", .1 * cm["C017"]["unit_cost"])
    for t in tr[tr.shipment_status == "Delayed"].itertuples():
        x = dls[dls.purchase_order_id == t.purchase_order_id].iloc[0]; addm(x.component_id, x.supplier_id, "Expedite shipment", 4, r.integers(600, 2500), int(x.ordered_quantity), "approved", 0.0, x.purchase_order_id)
    return dict(sup=sup, comp=comp, dl=dls, inv=pd.DataFrame(inv), pr=pr, bom=bom, tr=tr, dem=dem, mit=pd.DataFrame(mit))
def get_demo_raw():
    if "raw" not in _DEMO: _DEMO["raw"] = make_data()
    return _DEMO["raw"]
def get_demo():
    if "D" not in _DEMO: _DEMO["D"] = load_all(get_demo_raw())
    return _DEMO["D"]

# ------------------------------ ingestion and validation ------------------------------
def _sp(s):
    o = {}
    for it in s.split(","):
        p = it.strip().split(":"); o[p[0]] = (p[1], p[2] == "1", p[3].split("|") if len(p) > 3 and p[3] else [])
    return o
SPEC = dict(
 sup=_sp("supplier_id:s:1:id,supplier_name:s:0,region:s:0,material_categories:s:0,standard_lead_time_days:n:1:lead_time_days,contractual_lead_time_days:n:0,minimum_order_quantity:n:0,unit_cost_multiplier:n:0,capacity_limit:n:0,quality_rate:n:0,historical_on_time_rate:n:0,alternate_supplier_status:s:0"),
 comp=_sp("component_id:s:1:id,component_name:s:0,category:s:0,unit_cost:n:1,criticality:n:1,shelf_life_days:n:0,minimum_order_quantity:n:0,standard_replenishment_days:n:1:replenishment_days,approved_supplier_ids:s:1:approved_suppliers"),
 dl=_sp("purchase_order_id:s:1:po_id|po,supplier_id:s:1,component_id:s:1,order_date:d:1,promised_date:d:1:promise_date,actual_delivery_date:d:0:delivery_date,ordered_quantity:n:1:qty_ordered,received_quantity:n:0:qty_received,defect_quantity:n:0,delivery_status:s:0:status,disruption_reason:s:0"),
 inv=_sp("component_id:s:1,warehouse_id:s:1:warehouse,snapshot_date:d:1:date,on_hand_quantity:n:1:on_hand,reserved_quantity:n:0:reserved,allocated_quantity:n:0:allocated,inbound_quantity:n:0:inbound,safety_stock:n:0,reorder_point:n:0,storage_capacity:n:0"),
 pr=_sp("production_order_id:s:1:order_id,finished_product_id:s:1:product_id,quantity:n:1,planned_start_date:d:1:start_date,planned_completion_date:d:1:completion_date,actual_completion_date:d:0,priority:n:1,status:s:0,customer_due_date:d:1:due_date,shortage_cost_per_day:n:0"),
 bom=_sp("finished_product_id:s:1:product_id,component_id:s:1,quantity_required_per_unit:n:1:qty_per_unit,acceptable_substitute_components:s:0,substitution_constraints:s:0"),
 tr=_sp("shipment_id:s:1,purchase_order_id:s:1:po_id,carrier_id:s:0:carrier,transport_mode:s:0:mode,origin:s:0,destination:s:0,planned_departure:d:0,actual_departure:d:0,expected_arrival:d:1:eta,actual_arrival:d:0,shipment_status:s:0:status,estimated_transport_cost:n:0"),
 dem=_sp("product_id:s:1,period:d:1:week,actual_demand:n:1:demand,forecast_demand:n:0:forecast,forecast_version:s:0"),
 mit=_sp("option_id:s:1,component_id:s:1,supplier_id:s:0,action_type:s:1:action,estimated_lead_time:n:1:lead_time,estimated_cost:n:1:cost,capacity_limit:n:0,qualification_status:s:0:qualification,unit_cost_premium:n:0,purchase_order_id:s:0"))
TN = dict(sup="suppliers", comp="components", dl="supplier_deliveries", inv="inventory", pr="production_orders", bom="bills_of_materials", tr="transportation", dem="demand_history", mit="mitigation_options")
KEY = dict(sup=["supplier_id"], comp=["component_id"], dl=["purchase_order_id"], inv=["component_id", "warehouse_id", "snapshot_date"], pr=["production_order_id"], bom=["finished_product_id", "component_id"], tr=["shipment_id"], dem=["product_id", "period"], mit=["option_id"])
XR = dict(dl=[("promised_date before order_date", lambda d: d.promised_date < d.order_date), ("actual_delivery_date before order_date", lambda d: d.actual_delivery_date < d.order_date), ("defect_quantity above received_quantity", lambda d: d.defect_quantity > d.received_quantity)],
          pr=[("planned_completion before planned_start", lambda d: d.planned_completion_date < d.planned_start_date)], tr=[("actual_arrival before actual_departure", lambda d: d.actual_arrival < d.actual_departure)])
def parse_map(text):
    ov = {}
    for p in re.split(r"[,;\n]", text or ""):
        if "=" in p: k, v = p.split("=", 1); ov[norm(k)] = norm(v)
    return ov
def map_cols(raw, t, ov, iss):
    d = raw.copy(); d.columns = [norm(c) for c in d.columns]; ren = {}
    for f, (k, req, al) in SPEC[t].items():
        c = ov.get(t + "_" + f) or ov.get(f); c = c if c in d.columns else next((a for a in [f] + [norm(x) for x in al] if a in d.columns and a not in ren), None)
        if c is None or c in ren:
            if req: iss.append(("error", "%s: required field '%s' not found. Columns found: %s. Use the mapping box, e.g. %s=your_column." % (TN[t], f, ", ".join(map(str, raw.columns[:12])), f)))
            continue
        if c != f and f in d.columns: d = d.drop(columns=[f])
        ren[c] = f
    d = d.rename(columns=ren); return d.loc[:, ~d.columns.duplicated()]
def rows_txt(ix): return ", ".join(str(int(i)) for i in ix[:6]) + (" (+%d more)" % (len(ix) - 6) if len(ix) > 6 else "")
def ctab(raw, t, ov, iss, ex):
    d = map_cols(raw, t, ov, iss)
    if any(l == "error" for l, _ in iss): return d
    d = d.copy(); d["_row"] = d.index + 2; bad = pd.Series(False, index=d.index)
    for f, (k, req, al) in SPEC[t].items():
        if f not in d.columns: d[f] = pd.Series(pd.NaT, index=d.index, dtype="datetime64[ns]") if k == "d" else np.nan
        elif k == "n": d[f] = to_num(d[f])
        elif k == "d": d[f] = to_dt(d[f])
        else: d[f] = clean_str(d[f])
    def flag(m, why):
        nonlocal bad
        m = m.fillna(False) & ~bad
        if m.any(): ex.append((TN[t], why, int(m.sum()))); iss.append(("warn", "%s: %d rows excluded: %s (rows %s)" % (TN[t], m.sum(), why, rows_txt(d["_row"][m].values)))); bad = bad | m
    for f, (k, req, al) in SPEC[t].items():
        if req: flag(d[f].isna(), "missing " + f)
        if k == "n": flag(d[f] < 0, "negative " + f)
    for why, fn in XR.get(t, []): flag(fn(d), why)
    flag(d.duplicated(KEY[t], keep="first"), "duplicate " + "+".join(KEY[t]))
    return d[~bad].drop(columns="_row").reset_index(drop=True)
def load_all(raw, mapping=""):
    iss, ex, ov, D = [], [], parse_map(mapping), {}; rows_in = {t: len(raw[t]) for t in SPEC if raw.get(t) is not None}
    for t in ("sup", "comp", "dl", "inv", "pr", "bom"):
        if raw.get(t) is None: iss.append(("error", "Missing required table: %s." % TN[t]))
    if any(l == "error" for l, _ in iss): raise ValueError(" | ".join(m for l, m in iss if l == "error"))
    for t in rows_in: D[t] = ctab(raw[t], t, ov, iss, ex)
    errs = [m for l, m in iss if l == "error"]
    if errs: raise ValueError(" | ".join(errs))
    for t in ("tr", "dem", "mit"):
        if t not in D: D[t] = pd.DataFrame({f: pd.Series(dtype="datetime64[ns]" if k == "d" else float if k == "n" else object) for f, (k, _, _) in SPEC[t].items()}); iss.append(("info", "No %s table: analyses that need it are downgraded or unavailable." % TN[t]))
    def fk(t, col, ids, tgt):
        m = ~D[t][col].isin(ids) & D[t][col].notna()
        if m.any(): ex.append((TN[t], "unknown " + col, int(m.sum()))); iss.append(("warn", "%s: %d rows excluded: unknown %s (not in %s)." % (TN[t], m.sum(), col, tgt))); D[t] = D[t][~m].reset_index(drop=True)
    sid, cid = set(D["sup"].supplier_id), set(D["comp"].component_id); fk("dl", "supplier_id", sid, "suppliers"); fk("dl", "component_id", cid, "components"); fk("inv", "component_id", cid, "components"); fk("bom", "component_id", cid, "components"); fk("mit", "component_id", cid, "components"); fk("mit", "supplier_id", sid, "suppliers"); fk("tr", "purchase_order_id", set(D["dl"].purchase_order_id), "supplier_deliveries")
    dl, inv = D["dl"], D["inv"]; n = int((dl.received_quantity > dl.ordered_quantity).sum())
    if n: iss.append(("warn", "%d deliveries received more than ordered (kept as exceptions; fill rate capped at 100%%)." % n))
    n = int(((inv.reserved_quantity.fillna(0) + inv.allocated_quantity.fillna(0)) > inv.on_hand_quantity).sum())
    if n: iss.append(("warn", "%d inventory rows reserve or allocate more than on hand (kept; available stock is clipped at 0)." % n))
    if inv.reserved_quantity.isna().any() or inv.allocated_quantity.isna().any(): iss.append(("info", "Missing reserved/allocated quantities are treated as 0 in available stock (an assumption: check your source)."))
    nb = int((dl.delivery_status.fillna("").str.lower().str.contains("deliver|receiv") & dl.actual_delivery_date.isna()).sum())
    if nb: iss.append(("warn", "%d deliveries are marked delivered without a delivery date: excluded from delivery performance." % nb))
    pb = set(D["pr"].finished_product_id) - set(D["bom"].finished_product_id)
    if pb: iss.append(("warn", "Production orders for products without a BOM (material need unknown, ignored): %s." % ", ".join(sorted(pb)[:6])))
    if inv.empty: raise ValueError("No valid inventory records remain after validation.")
    asof = inv.snapshot_date.max()
    if dl.order_date.max() > asof + Td(14): iss.append(("warn", "The latest inventory snapshot (%s) is older than the latest purchase orders: stock may be stale." % dts(asof)))
    D.update(issues=iss, excluded=ex, rows_in=rows_in, asof=asof); return D

# ------------------------------ supplier, inbound and inventory analytics ------------------------------
def deliv_frame(d, asof, tol):
    d = d.copy(); st = d.delivery_status.fillna("").str.lower(); d["done"] = d.actual_delivery_date.notna() & (d.actual_delivery_date <= asof); d["open"] = ~d["done"] & ~st.str.contains("deliver|receiv|closed|cancel")
    d["lead"] = (d.actual_delivery_date - d.order_date).dt.days.where(d["done"]); d["late"] = (d.actual_delivery_date - d.promised_date).dt.days.clip(lower=0).where(d["done"]); d["ontime"] = (d["late"] <= tol).astype(float).where(d["done"])
    d["fill"] = (d.received_quantity / d.ordered_quantity.replace(0, np.nan)).clip(upper=1).where(d["done"]); d["short"] = (d["fill"] < .98).astype(float).where(d["fill"].notna()); d["defr"] = (d.defect_quantity.fillna(0) / d.received_quantity.replace(0, np.nan)).where(d["done"]); return d
def sup_stats(X):
    P, asof, d = X["P"], X["asof"], X["dl"]; Tdn = d[d["done"]]; rc = asof - Td(P["win"]); rows = []
    mn = lambda df, c: df[c].mean() if len(df) and df[c].notna().any() else np.nan
    dr = lambda df: df.defect_quantity.fillna(0).sum() / df.received_quantity.sum() if len(df) and df.received_quantity.sum() > 0 else np.nan
    for s in X["T"]["sup"].supplier_id:
        x = Tdn[Tdn.supplier_id == s]; r_ = x[x.actual_delivery_date >= rc]; b = x[x.actual_delivery_date < rc]; late = x[x["late"] > 0]; det = z = np.nan
        if len(r_) >= 5 and len(b) >= 10:
            det = r_["lead"].mean() - b["lead"].mean(); s0 = b["lead"].std(ddof=1); z = det / (s0 / math.sqrt(len(r_))) if s0 and s0 > 0 else np.nan
        rows.append(dict(supplier_id=s, n=len(x), n_r=len(r_), otd=mn(x, "ontime"), otd_r=mn(r_, "ontime"), lead_mean=mn(x, "lead"), lead_med=x["lead"].median() if len(x) else np.nan, lead_sd=x["lead"].std(ddof=1) if len(x) > 1 else np.nan, late_days=late["late"].mean() if len(late) else 0.0,
                         short=mn(x, "short"), short_r=mn(r_, "short"), defr=dr(x), defr_r=dr(r_), defr_b=dr(b), fill=mn(x, "fill"), fill_r=mn(r_, "fill"), det=det, z=z, lead_r=mn(r_, "lead"), lead_b=mn(b, "lead"), med_late=float(late["late"].median()) if len(late) >= 3 else 0.0,
                         last5=int((x.sort_values("actual_delivery_date").tail(5)["late"] > 0).sum())))
    s = pd.DataFrame(rows); s["cv"] = s.lead_sd / s.lead_mean.replace(0, np.nan); return s
def inbound(X):
    asof, d, tol = X["asof"], X["dl"], X["P"]["tol"]; ss = X["ss"].set_index("supplier_id"); o = d[d["open"]].copy(); tr = X["T"]["tr"]; t = tr.sort_values("expected_arrival").drop_duplicates("purchase_order_id", keep="last").set_index("purchase_order_id")
    o["ship"] = o.purchase_order_id.map(t.shipment_id); o["sstat"] = o.purchase_order_id.map(t.shipment_status).fillna(""); o["carrier"] = o.purchase_order_id.map(t.carrier_id); o["origin"] = o.purchase_order_id.map(t.origin)
    o["eta"] = pd.to_datetime(o.purchase_order_id.map(t.expected_arrival), errors="coerce").fillna(o.promised_date); o["qty"] = (o.ordered_quantity - o.received_quantity.fillna(0)).clip(lower=0); nx = asof + Td(1); o["d_p"] = o.eta.where(o.eta >= nx, nx)
    ml = pd.Series(pd.to_timedelta(o.supplier_id.map(ss.med_late).fillna(0).values, unit="D"), index=o.index); o["d_a"] = o.eta.where(o.eta >= asof, asof) + ml; o["d_a"] = o["d_a"].where(o["d_a"] >= nx, nx)
    f = o.supplier_id.map(ss.fill_r).fillna(o.supplier_id.map(ss.fill)).fillna(1.0); df_ = o.supplier_id.map(ss.defr_r).fillna(o.supplier_id.map(ss.defr)).fillna(0.0); o["qty_a"] = o.qty * f * (1 - df_)
    o["delayed"] = (o.eta > o.promised_date + Td(tol)) | (o.promised_date < asof) | o.sstat.astype(str).str.lower().str.contains("delay"); return o.reset_index(drop=True)
def project(avail, dly, ev, H):
    if dly <= 0: return None
    arr = np.zeros(H + 1)
    for o, q in ev:
        if 0 <= o <= H: arr[int(o)] += q
    stock = avail + np.cumsum(arr) - dly * np.arange(H + 1); neg = np.nonzero(stock[1:] <= 1e-9)[0]; return int(neg[0]) + 1 if len(neg) else None
def inv_metrics(X):
    D, P, asof, ib = X["T"], X["P"], X["asof"], X["ib"]; inv = D["inv"]; last = inv[inv.snapshot_date == inv.snapshot_date.max()]; cm = D["comp"].set_index("component_id")
    g = last.groupby("component_id")[["on_hand_quantity", "reserved_quantity", "allocated_quantity", "safety_stock", "reorder_point"]].sum().reindex(cm.index).fillna(0); g.columns = ["on_hand", "reserved", "allocated", "safety", "rop"]
    g["avail_raw"] = g.on_hand - g.reserved - g.allocated; g["avail"] = g.avail_raw.clip(lower=0); g["negs"] = g.avail_raw < 0
    ibc = ib.groupby("component_id").agg(inb=("qty", "sum"), nxt=("d_p", "min")).reindex(cm.index) if len(ib) else pd.DataFrame(index=cm.index, columns=["inb", "nxt"]); g["inb"] = pd.to_numeric(ibc.inb, errors="coerce").fillna(0); g["nxt"] = pd.to_datetime(ibc.nxt, errors="coerce")
    dem, B = D["dem"], D["bom"]; g["daily"] = np.nan; g["dsd"] = np.nan; X["cw"] = None; X["pdev"] = {}
    if len(dem) and len(B):
        wks = sorted(dem.period.unique())[-P["dw"]:]; pv = dem[dem.period.isin(wks)].pivot_table(index="product_id", columns="period", values="actual_demand", aggfunc="sum").fillna(0)
        Bm = B.pivot_table(index="component_id", columns="finished_product_id", values="quantity_required_per_unit", aggfunc="sum").fillna(0); cp = Bm.columns.intersection(pv.index)
        if len(cp):
            cw = pd.DataFrame(Bm[cp].values @ pv.loc[cp].values, index=Bm.index); g["daily"] = (cw.mean(axis=1) / 7).reindex(g.index); g["dsd"] = (cw.std(axis=1, ddof=1).fillna(0) / 7).reindex(g.index) if cw.shape[1] > 1 else 0.0; X["cw"] = cw
        for p, x in dem.sort_values("period").groupby("product_id"):
            x4 = x.tail(4)
            if x4.forecast_demand.sum() > 0: X["pdev"][p] = x4.actual_demand.sum() / x4.forecast_demand.sum() - 1
    dd = X["dl"]; lt = dd[dd["done"] & (dd.order_date >= asof - Td(365))].groupby("component_id")["lead"].median(); g["rlt"] = lt.reindex(g.index).fillna(cm.standard_replenishment_days); H_ = P["hor"]; ibg = {c: x for c, x in ib.groupby("component_id")}; rows = []
    for c, r in g.iterrows():
        x = ibg.get(c); evp = [((a - asof).days, q) for a, q in zip(x.d_p, x.qty)] if x is not None else []; eva = [((a - asof).days, q) for a, q in zip(x.d_a, x.qty_a)] if x is not None else []; dl_ = r["daily"]; sdv = 0.0 if pd.isna(r["dsd"]) else r["dsd"]; ok = pd.notna(dl_) and dl_ > 0
        pt, ea, la = (project(r["avail"], dl_, evp, H_), project(r["avail"], dl_ + sdv, eva, H_), project(r["avail"], max(dl_ - sdv, 0), evp, H_)) if ok else (None, None, None)
        within = sum(q for o_, q in evp if o_ <= r["rlt"]) if ok else 0.0
        rows.append(dict(component_id=c, so_pt=np.nan if pt is None else pt, so_early=np.nan if ea is None else ea, so_late=np.nan if la is None else la, shortfall=max(0.0, dl_ * r["rlt"] - r["avail"] - within) if ok else np.nan))
    g = g.join(pd.DataFrame(rows).set_index("component_id")).join(cm[["component_name", "category", "criticality", "unit_cost"]]); g["cover"] = np.where(g.daily > 0, g.avail / g.daily.replace(0, np.nan), np.nan); g["short_val"] = g.shortfall * g.unit_cost
    g["below_ss"] = (g.safety > 0) & (g.avail < g.safety); g["below_rop"] = (g.rop > 0) & ((g.avail + g.inb) <= g.rop)
    def stat(r):
        if pd.isna(r["daily"]) or r["daily"] <= 0: return "No recent demand data"
        if r["avail"] <= 0: return "Already short"
        if pd.notna(r["so_pt"]): return "Projected short before next receipt" if (pd.isna(r["nxt"]) or r["so_pt"] < (r["nxt"] - asof).days) else "Projected short despite inbound"
        return "Below safety stock" if r["below_ss"] else "OK"
    g["status"] = g.apply(stat, axis=1); return g.reset_index()

# ------------------------------ production impact (BOM propagation, no double counting) ------------------------------
def events(X, mode, spec):
    asof = X["asof"]; ev = {}
    for e in X["ib"].itertuples():
        if e.supplier_id == spec.get("fail_sup") or str(e.ship) == spec.get("drop_ship", "~"): continue
        d = e.d_a if mode == "adj" else e.d_p; q = e.qty_a if mode == "adj" else e.qty
        if e.supplier_id == spec.get("delay_sup") or str(e.ship) == spec.get("delay_ship", "~"): d = d + Td(spec.get("delay_days", 0))
        if e.component_id == spec.get("defect_comp"): q = q * (1 - spec.get("defect_pct", 0) / 100)
        if str(e.ship) == spec.get("exp_ship", "~"): d = min(d, asof + Td(spec.get("exp_days", 3)))
        if e.purchase_order_id in spec.get("exp", {}): d = min(d, spec["exp"][e.purchase_order_id])
        ev.setdefault(e.component_id, []).append([d, float(q)])
    for c, q, d in spec.get("extra", []): ev.setdefault(c, []).append([d, float(q)])
    for v in ev.values(): v.sort(key=lambda e: e[0])
    return ev
OC = ["order", "product", "priority", "quantity", "start", "completion", "due", "status", "short_comps", "binding", "delay", "unq", "new_completion", "due_exposed", "cost_day", "delay_cost"]; LC = ["order", "product", "component_id", "need", "shortage", "delay", "start", "unq", "priority"]
def propagate(X, mode="adj", spec=None):
    spec = spec or {}; asof = X["asof"]; avail = X["inv"].set_index("component_id").avail.to_dict(); ev = events(X, mode, spec)
    for c in avail: ev.setdefault(c, [])
    bom = {}
    for r in X["T"]["bom"].itertuples(): bom.setdefault(r.finished_product_id, []).append((r.component_id, r.quantity_required_per_unit))
    pr = X["T"]["pr"]; st = pr.status.fillna("").astype(str).str.lower(); pr = pr[~st.str.contains("progress|complete|cancel") & pr.actual_completion_date.isna()]
    pr = pr.sort_values(["customer_due_date", "priority"] if spec.get("seq") == "due" else ["priority", "planned_start_date"], kind="mergesort"); dm = spec.get("dm", {}); lines, res = [], []
    def take(c, need, st_):
        s = min(avail[c], need); avail[c] -= s; need -= s
        for e in ev[c]:
            if need <= 1e-9 or e[0] > st_: break
            t = min(e[1], need); e[1] -= t; need -= t
        if need <= 1e-9: return 0.0, 0
        short = need; last = None
        for e in ev[c]:
            if e[0] <= st_ or e[1] <= 1e-9: continue
            t = min(e[1], need); e[1] -= t; need -= t; last = e[0]
            if need <= 1e-9: break
        return short, ((last - st_).days if need <= 1e-9 and last is not None else None)
    for o in pr.itertuples():
        stt = max(o.planned_start_date, asof); mult = dm.get(o.finished_product_id, dm.get("All", 1.0)); ol = []
        for c, q in bom.get(o.finished_product_id, []):
            if c not in avail: continue
            need = q * o.quantity * mult; short, dly = take(c, need, stt)
            lines.append(dict(order=o.production_order_id, product=o.finished_product_id, component_id=c, need=need, shortage=short, delay=0.0 if short <= 1e-9 else (np.nan if dly is None else float(dly)), start=stt, unq=short > 1e-9 and dly is None, priority=o.priority))
            if short > 1e-9: ol.append((c, dly))
        unq = any(d is None for _, d in ol); worst = max([d for _, d in ol if d is not None], default=0); bind = max(ol, key=lambda t: 1e9 if t[1] is None else t[1])[0] if ol else None
        newc = pd.NaT if unq else (o.planned_completion_date + Td(worst) if ol else o.planned_completion_date); cd = o.shortage_cost_per_day
        res.append(dict(order=o.production_order_id, product=o.finished_product_id, priority=o.priority, quantity=o.quantity, start=stt, completion=o.planned_completion_date, due=o.customer_due_date, status="Blocked (no confirmed supply)" if unq else ("Delayed" if ol else "OK"), short_comps=", ".join(c for c, _ in ol), binding=bind,
                        delay=np.nan if (unq or not ol) else float(worst), unq=unq, new_completion=newc, due_exposed=bool(unq or (len(ol) > 0 and newc > o.customer_due_date)), cost_day=cd, delay_cost=worst * cd if (ol and not unq and pd.notna(cd)) else np.nan))
    return dict(orders=pd.DataFrame(res, columns=OC), lines=pd.DataFrame(lines, columns=LC))
def px_kpi(px):
    o, l = px["orders"], px["lines"]; s = l[l.shortage > 1e-9]
    return dict(n=len(o), exposed=int((o.status != "OK").sum()), blocked=int(o.unq.sum()), due=int(o.due_exposed.sum()), delay_days=float(o.delay.sum(skipna=True)), cost=float(o.delay_cost.sum(skipna=True)), comps=int(s.component_id.nunique()), qty=float(s.shortage.sum()), first=s.start.min() if len(s) else pd.NaT)

# ------------------------------ supplier risk index ------------------------------
RF = [("rel", "Recent delivery reliability (1 − on-time rate)"), ("vol", "Lead-time volatility (CV ÷ 0.5, capped)"), ("qual", "Quality and fill (defect + short-fill ÷ 12%, capped)"), ("openl", "Open delays (share of open POs late or delayed)"), ("crit", "Critical-part exposure (share with criticality ≥ 4)"), ("sole", "Sole-source exposure without an approved alternate")]
def risk_table(X):
    P = X["P"]; w = P["w"]; ss = X["ss"].set_index("supplier_id"); comp = X["T"]["comp"].set_index("component_id"); sup = X["T"]["sup"].set_index("supplier_id"); mit = X["T"]["mit"]; ib = X["ib"]; PXa = X["PX"]["adj"]; Ls = PXa["lines"]; Ls = Ls[Ls.shortage > 1e-9]; O = PXa["orders"].set_index("order"); apm = X["apm"]
    altc = {m.component_id for m in mit.itertuples() if str(m.qualification_status).lower() == "approved" and m.action_type == "Alternate supplier"}; rows = []
    for s in sup.index:
        cs = [c for c, v in apm.items() if s in v and c in comp.index]; n = max(len(cs), 1); st = ss.loc[s]; op = ib[ib.supplier_id == s]; ol = float(op.delayed.mean()) * min(1.0, len(op) / 2) if len(op) else 0.0
        rel = st.otd_r if st.n_r >= 3 and pd.notna(st.otd_r) else (st.otd if pd.notna(st.otd) else sup.historical_on_time_rate.get(s, np.nan)); dfc = st.defr_r if st.n_r >= 3 and pd.notna(st.defr_r) else (st.defr if pd.notna(st.defr) else 0.0); fl = st.fill_r if pd.notna(st.fill_r) else (st.fill if pd.notna(st.fill) else 1.0)
        f = dict(rel=np.nan if pd.isna(rel) else 1 - rel, vol=np.nan if pd.isna(st.cv) else min(st.cv / .5, 1), qual=min((dfc + max(0, 1 - fl)) / .12, 1), openl=ol, crit=sum(comp.criticality[c] >= 4 for c in cs) / n, sole=sum(1 for c in cs if apm[c] == [s] and c not in altc) / n)
        ok = [k for k in f if pd.notna(f[k])]; sw = sum(w[k] for k in ok) or 1.0; score = 100 * sum(w[k] * f[k] for k in ok) / sw; od = sorted(set(Ls[Ls.component_id.isin(cs)]["order"]))
        ev = "on-time %s (recent, n=%d); median lead %s d, CV %s; defects %s; %d open PO(s), %d late or delayed; %d of %d parts critical; %d sole-source without approved alternate" % (pc0(rel), st.n_r, fx(st.lead_med), fx(st.cv, 2), pc1(dfc), len(op), int(op.delayed.sum()) if len(op) else 0, sum(comp.criticality[c] >= 4 for c in cs), len(cs), sum(1 for c in cs if apm[c] == [s] and c not in altc))
        rows.append(dict(supplier_id=s, score=score, **{"c_" + k: (100 * w[k] * f[k] / sw if k in ok else 0.0) for k in f}, n_open=len(op), n_open_late=int(op.delayed.sum()) if len(op) else 0, n_sole=sum(1 for c in cs if apm[c] == [s] and c not in altc), n_orders=len(od), exp_cost=float(O.delay_cost.reindex(od).sum(skipna=True)) if od else 0.0, evidence=ev))
    return pd.DataFrame(rows)

# ------------------------------ early-warning alerts ------------------------------
def make_alerts(X):
    asof, ss, inv, ib, P = X["asof"], X["ss"].set_index("supplier_id"), X["inv"].set_index("component_id"), X["ib"], X["P"]; PXa = X["PX"]["adj"]; Ls = PXa["lines"]; Ls = Ls[Ls.shortage > 1e-9]; O = PXa["orders"].set_index("order"); apm = X["apm"]; A = []
    def add(typ, ent, sup, cl, base, why, nxt, conf):
        od = sorted(set(Ls[Ls.component_id.isin(cl)]["order"])); sev = "High" if any(bool(O.due_exposed.get(o, False)) for o in od) else ("Medium" if od else base)
        A.append(dict(type=typ, entity=ent, sup=sup, comp_list=list(cl), sev=sev, date=asof, why=why, orders=", ".join(od[:6]) + (" (+%d)" % (len(od) - 6) if len(od) > 6 else ""), n_orders=len(od), conseq=("%d production order(s) short on these components (risk-adjusted)" % len(od)) if od else "No production order is currently short on these components", nxt=nxt, conf=conf))
    for s, r in ss.iterrows():
        cl = list(ib[ib.supplier_id == s].component_id.unique()) or [c for c, v in apm.items() if s in v][:5]
        if pd.notna(r.z) and r.z >= 3 and r.det >= 2: add("Lead-time deterioration", s, s, cl, "Medium", "Mean lead time rose from %.1f to %.1f days (+%.1f; z = %.1f) in the last %d days versus this supplier's own earlier baseline (n = %d vs %d deliveries)." % (r.lead_b, r.lead_r, r.det, r.z, P["win"], r.n_r, r.n - r.n_r), "Ask for a recovery plan; review contractual lead time and buffer stock; line up an alternate.", "Supplier-specific comparison; moderate confidence with few recent deliveries")
        if r.last5 >= 3: add("Repeated late deliveries", s, s, cl, "Medium", "%d of the last 5 deliveries were late (average %.1f days late when late)." % (r.last5, r.late_days), "Escalate delivery performance and confirm open PO dates.", "Based on the last 5 deliveries only")
        if r.n_r >= 4 and pd.notna(r.short_r) and r.short_r >= .25: add("Short shipments", s, s, cl, "Medium", "%s of recent deliveries were short (mean fill %s)." % (pc0(r.short_r), pc0(r.fill_r)), "Confirm quantities and capacity; split orders across suppliers.", "n = %d recent deliveries" % r.n_r)
        if r.n_r >= 4 and pd.notna(r.defr_r) and r.defr_r >= max(.03, 2 * (r.defr_b if pd.notna(r.defr_b) else 0)): add("Rising defect rate", s, s, cl, "Medium", "Recent defect rate %s versus %s earlier." % (pc1(r.defr_r), pc1(r.defr_b)), "Tighten incoming inspection; open a corrective-action request.", "n = %d recent deliveries" % r.n_r)
    cw = X["cw"]
    for c, r in inv.iterrows():
        if pd.isna(r.daily) or r.daily <= 0: continue
        if r.cover < r.rlt: add("Coverage below replenishment lead time", c, "", [c], "Medium", "%.1f days of cover versus a %.0f-day replenishment lead time (available %s units, demand %.1f/day)." % (r.cover, r.rlt, nf(r.avail), r.daily), "Reorder now or expedite open supply.", "Demand averaged over the last %d weeks" % P["dw"])
        if pd.notna(r.so_early): add("Projected stockout", c, "", [c], "High" if r.criticality >= 4 else "Medium", "Stock-out projected between day %s and day %s (%s to %s) under the demand range and risk-adjusted arrivals; point estimate day %s." % (nf(r.so_early), nf(r.so_late) if pd.notna(r.so_late) else "beyond the horizon", dts(asof + Td(r.so_early)), dts(asof + Td(r.so_late)) if pd.notna(r.so_late) else "n/a", nf(r.so_pt) if pd.notna(r.so_pt) else "beyond"), "Secure supply before the earliest date (Mitigation Studio).", "A range, not a point forecast")
        if cw is not None and c in cw.index and cw.shape[1] >= 5:
            v = cw.loc[c].values; m2 = v[-2:].mean(); sd_ = v.std(ddof=1)
            if sd_ > 0 and (m2 - v.mean()) / (sd_ / math.sqrt(2)) >= 2 and m2 >= 1.25 * v.mean(): add("Consumption spike", c, "", [c], "Medium", "Last 2 weeks consumed %.0f units/week versus an %d-week mean of %.0f (+%.0f%%)." % (m2, len(v), v.mean(), 100 * (m2 / v.mean() - 1)), "Check one-off versus trend; review safety stock.", "Weekly demand derived from product demand × BOM")
        if r.safety > 0 and r.avail < r.safety and r.cover >= r.rlt: add("Safety-stock buffer eroded", c, "", [c], "Low", "Available %s units is below the %s-unit safety stock." % (nf(r.avail), nf(r.safety)), "Replenish to the reorder point.", "Latest inventory snapshot")
    for p, v in X["pdev"].items():
        if v >= .25: add("Demand above forecast", p, "", list(X["T"]["bom"][X["T"]["bom"].finished_product_id == p].component_id), "Medium", "Product %s actual demand ran %.0f%% above forecast over the last 4 weeks." % (p, 100 * v), "Update the forecast and re-check component cover.", "Last 4 weeks only")
    tr = X["T"]["tr"]; dn = tr[tr.actual_arrival.notna() & tr.actual_departure.notna()].copy(); dn["tt"] = (dn.actual_arrival - dn.actual_departure).dt.days; p90 = dn.groupby("transport_mode")["tt"].quantile(.9) if len(dn) else pd.Series(dtype=float); cnt = dn.groupby("transport_mode")["tt"].size() if len(dn) else pd.Series(dtype=float); trm = tr.drop_duplicates("purchase_order_id", keep="last").set_index("purchase_order_id")
    for e in ib[ib.ship.notna()].itertuples():
        t = trm.loc[e.purchase_order_id]; rs = []
        if pd.notna(t.planned_departure) and t.planned_departure < asof and pd.isna(t.actual_departure): rs.append("planned departure %s missed (no actual departure recorded)" % dts(t.planned_departure))
        if e.eta < asof: rs.append("expected arrival %s has passed without receipt" % dts(e.eta))
        elif e.eta > e.promised_date + Td(P["tol"]): rs.append("ETA %s is %d days after the promised date %s" % (dts(e.eta), (e.eta - e.promised_date).days, dts(e.promised_date)))
        if pd.notna(t.actual_departure) and t.transport_mode in p90.index and cnt[t.transport_mode] >= 10 and (asof - t.actual_departure).days > p90[t.transport_mode]: rs.append("in transit %d days versus a historical P90 of %.0f for %s" % ((asof - t.actual_departure).days, p90[t.transport_mode], t.transport_mode))
        if str(e.sstat).lower().startswith("delay") and not rs: rs.append("carrier status is Delayed")
        if rs: add("Shipment exception", e.ship, e.supplier_id, [e.component_id], "Low", "; ".join(rs) + " (carrier %s, origin %s)." % (e.carrier, e.origin), "Contact the carrier; evaluate expediting (Mitigation Studio).", "Status fields come from the uploaded data; no live tracking")
    crit = set(inv.index[inv.criticality >= 4]); oc = ib[ib.component_id.isin(crit) & ib.ship.notna()]
    if len(oc) >= 5:
        sh = oc.carrier.value_counts(normalize=True)
        if sh.iloc[0] >= .4: add("Carrier concentration", sh.index[0], "", list(oc[oc.carrier == sh.index[0]].component_id.unique()), "Medium", "%s carries %.0f%% of %d open shipments of critical components." % (sh.index[0], 100 * sh.iloc[0], len(oc)), "Diversify carriers or routes for critical parts.", "Open shipments only")
    return A
def build(D, P):
    X = dict(T=D, P=P, asof=D["asof"]); X["dl"] = deliv_frame(D["dl"], X["asof"], P["tol"]); X["ss"] = sup_stats(X); comp = D["comp"].set_index("component_id"); X["apm"] = {c: [s for s in str(v).split(";") if s] for c, v in comp.approved_supplier_ids.items()}
    X["ib"] = inbound(X); X["inv"] = inv_metrics(X); X["PX"] = dict(planned=propagate(X, "planned"), adj=propagate(X, "adj")); X["risk"] = risk_table(X); X["alerts"] = make_alerts(X); return X
def DX():
    if "X" not in _DEMO: _DEMO["X"] = build(get_demo(), DEF)
    return _DEMO["X"]

# ------------------------------ mitigation (deterministic heuristic) ------------------------------
ACOL = ["option_id", "action", "component_id", "supplier_id", "qty", "cost", "arrival", "timely", "qualification", "status"]
def mitigate(X, mode="adj", spec=None, allow_unq=False, budget=0.0):
    spec = dict(spec or {}); asof = X["asof"]; base = propagate(X, mode, spec); L = base["lines"]; sh = L[L.shortage > 1e-9]; inv = X["inv"].set_index("component_id"); mit = X["T"]["mit"]; ibi = X["ib"].set_index("purchase_order_id")
    acts, unres, extra, exp, spent = [], [], list(spec.get("extra", [])), dict(spec.get("exp", {})), 0.0; cap = {o.option_id: (np.inf if pd.isna(o.capacity_limit) else float(o.capacity_limit)) for o in mit.itertuples()}
    cg = sh.groupby("component_id").agg(q=("shortage", "sum"), need=("start", "min")).reset_index(); cg["crit"] = cg.component_id.map(inv.criticality); cg = cg.sort_values(["crit", "need"], ascending=[False, True]); qc = "qty_a" if mode == "adj" else "qty"; dc = "d_a" if mode == "adj" else "d_p"
    for c in cg.itertuples():
        rem = float(c.q); cand = []
        for o in mit[mit.component_id == c.component_id].itertuples():
            qual = str(o.qualification_status).lower() in ("approved", "qualified"); arr = asof + Td(o.estimated_lead_time)
            if (not qual and not allow_unq) or cap[o.option_id] <= 0: continue
            prem = 0.0 if pd.isna(o.unit_cost_premium) else float(o.unit_cost_premium); fixed = float(o.estimated_cost); exped = o.action_type == "Expedite shipment"
            if exped:
                po = str(o.purchase_order_id)
                if po not in ibi.index or arr >= ibi.loc[po, dc]: continue
                cover = min(rem, float(ibi.loc[po, qc]), cap[o.option_id])
            else: cover = min(rem, cap[o.option_id])
            if cover > 0: cand.append((bool(arr > c.need), (fixed + prem * cover) / cover, o, qual, arr, fixed, prem, exped))
        cand.sort(key=lambda t: (t[0], t[1]))
        for late, uc, o, qual, arr, fixed, prem, exped in cand:
            if rem <= 1e-9: break
            cover = min(rem, (float(ibi.loc[str(o.purchase_order_id), qc]) if exped else rem), cap[o.option_id]); cost = fixed + prem * cover
            if budget > 0 and spent + cost > budget:
                room = budget - spent - fixed
                if room <= 0 or prem <= 0: continue
                cover = min(cover, math.floor(room / prem)); cost = fixed + prem * cover
                if cover <= 0: continue
            spent += cost; rem -= cover; cap[o.option_id] -= cover
            if exped: exp[str(o.purchase_order_id)] = arr
            else: extra.append((c.component_id, cover, arr))
            acts.append(dict(option_id=o.option_id, action=o.action_type, component_id=c.component_id, supplier_id=o.supplier_id, qty=cover, cost=cost, arrival=arr, timely=not late, qualification="approved" if qual else "REQUIRES QUALIFICATION", status="Pending human approval"))
        if rem > 1e-9: unres.append(dict(component_id=c.component_id, qty=rem, need=c.need, reason="No feasible option within capacity, qualification or budget limits"))
    after = propagate(X, mode, dict(spec, extra=extra, exp=exp)); return dict(acts=pd.DataFrame(acts, columns=ACOL), unres=pd.DataFrame(unres, columns=["component_id", "qty", "need", "reason"]), base=base, after=after, spent=spent, kb=px_kpi(base), ka=px_kpi(after))

# ------------------------------ pages ------------------------------
def fa(A, sf, cf): return [a for a in A if (not sf or a["sup"] in sf) and (not cf or set(a["comp_list"]) & set(cf))]
bandf = lambda v: pill("High") if v >= 60 else (pill("Medium") if v >= 35 else pill("Low"))
@safe("hppp")
def render_ct(sf, cf, pf, d1, d2):
    X = G["X"]; rk = X["risk"]; ib = X["ib"]; inv = X["inv"]; A = fa(X["alerts"], sf, cf); kp, ka = px_kpi(X["PX"]["planned"]), px_kpi(X["PX"]["adj"])
    if sf: rk = rk[rk.supplier_id.isin(sf)]; ib = ib[ib.supplier_id.isin(sf)]
    if cf: inv = inv[inv.component_id.isin(cf)]; ib = ib[ib.component_id.isin(cf)]
    crit = inv[(inv.criticality >= 4) & inv.status.str.contains("Already|Projected")]
    h = banner() + "<div class='kg'>" + card("Open purchase orders", nf(len(ib)), "%d late or delayed" % int(ib.delayed.sum())) + card("High-risk suppliers", nf(int((rk.score >= 60).sum())), "of %d (index ≥ 60, descriptive)" % len(rk), C["co"]) + card("Critical component shortages", nf(len(crit)), "criticality ≥ 4, short or projected short", C["co"]) + \
        card("Production orders exposed", "%d / %d" % (kp["exposed"], ka["exposed"]), "planned / risk-adjusted, of %d open" % kp["n"], C["am"]) + card("Customer due dates exposed", "%d / %d" % (kp["due"], ka["due"]), "planned / risk-adjusted", C["am"]) + card("Median inventory cover", fx(inv.cover.median()) + " d", "available stock ÷ average daily demand") + \
        card("Quantified delay exposure", money(ka["cost"]), "risk-adjusted; %d order(s) have no confirmed supply and are unquantified" % ka["blocked"], C["co"]) + card("High-severity alerts", nf(sum(a["sev"] == "High" for a in A)), "of %d alerts" % len(A), C["vi"]) + "</div>"
    h += note("<b>Observed</b>: purchase orders, stock, shipments. <b>Calculated indicators</b>: supplier index, alerts, projected shortages. <b>Planned view</b> uses supplier ETAs; <b>risk-adjusted view</b> adds each supplier's typical lateness and fill/defect losses. Nothing here is a probability of disruption.", "info")
    if A: h += H("Highest-priority alerts") + tbl(pd.DataFrame(sorted(A, key=lambda a: ({"High": 0, "Medium": 1, "Low": 2}[a["sev"]], -a["n_orders"]))[:8]), [("sev", "Severity"), ("type", "Alert"), ("entity", "Entity"), ("why", "Why it triggered"), ("n_orders", "Orders at risk")], dict(sev=pill, n_orders=nf))
    t = rk.sort_values("score", ascending=False).head(12).iloc[::-1]; f1 = sty(go.Figure(go.Bar(y=t.supplier_id, x=t.score, orientation="h", marker_color=[C["co"] if v >= 60 else (C["am"] if v >= 35 else C["te"]) for v in t.score], text=[fx(v, 0) for v in t.score], textposition="outside")), 380, "Supplier risk index (0-100, descriptive)"); f1.update_xaxes(range=[0, 105])
    o1, o2 = X["PX"]["planned"]["orders"], X["PX"]["adj"]["orders"]; ss_ = ["OK", "Delayed", "Blocked (no confirmed supply)"]; f2 = go.Figure([go.Bar(x=ss_, y=[int((o.status == s).sum()) for s in ss_], name=n, marker_color=c) for o, n, c in ((o1, "Planned dates", C["mu"]), (o2, "Risk-adjusted", C["am"]))]); f2.update_layout(barmode="group"); f2 = sty(f2, 340, "Production orders by material status")
    cc = inv[(inv.criticality >= 4) & inv.daily.gt(0)]; f3 = empty("No critical components with demand")
    if len(cc): f3 = go.Figure(go.Scatter(x=cc.rlt, y=cc.cover, mode="markers+text", text=cc.component_id, textposition="top center", marker=dict(size=10, color=[C["co"] if s != "OK" else C["te"] for s in cc.status]))); f3.add_shape(type="line", x0=0, y0=0, x1=max(cc.rlt.max(), 1), y1=max(cc.rlt.max(), 1), line=dict(color=C["mu"], dash="dash")); f3 = sty(f3, 360, "Critical parts: cover vs replenishment lead time (below the line = cover shorter than lead time)"); f3.update_xaxes(title="Lead time (days)"); f3.update_yaxes(title="Cover (days)")
    return h, f1, f2, f3
@safe("hppp")
def render_sup(sf, cf, pf, d1, d2):
    X = G["X"]; rk = X["risk"].merge(X["T"]["sup"][["supplier_id", "region"]], on="supplier_id").merge(X["ss"], on="supplier_id")
    if sf: rk = rk[rk.supplier_id.isin(sf)]
    rk = rk.sort_values("score", ascending=False); w = X["P"]["w"]
    h = banner() + note("<b>Risk index (0-100)</b> = 100 × Σ(weight × factor) ÷ Σ weights over factors with data. Factors (each 0-1, weights editable in Settings): " + "; ".join("%s ×%.2f" % (n, w[k]) for k, n in RF) + ". Correlated signals are combined rather than counted twice. Deterioration is a separate <b>anomaly signal</b>. This is not a probability of disruption.", "info")
    h += tbl(rk, [("supplier_id", "Supplier"), ("region", "Region"), ("score", "Risk index"), ("otd_r", "On-time (recent)"), ("lead_med", "Median lead (d)"), ("cv", "Lead CV"), ("late_days", "Days late (when late)"), ("short", "Short-fill rate"), ("defr", "Defect rate"), ("det", "Lead change vs baseline (d)"), ("z", "z"), ("n_open", "Open POs"), ("n_open_late", "Late"), ("n_sole", "Sole-source parts"), ("n_orders", "Orders exposed"), ("evidence", "Evidence")],
             dict(score=lambda v: bandf(v) + " " + fx(v, 0), otd_r=pc0, lead_med=fx, cv=lambda v: fx(v, 2), late_days=fx, short=pc0, defr=pc1, det=lambda v: ("%+.1f" % v) if pd.notna(v) else "—", z=fx, n_open=nf, n_open_late=nf, n_sole=nf, n_orders=nf))
    t = rk.head(12).iloc[::-1]; f1 = go.Figure([go.Bar(y=t.supplier_id, x=t["c_" + k], orientation="h", name=n.split(" (")[0]) for k, n in RF]); f1.update_layout(barmode="stack"); f1 = sty(f1, 400, "What drives the risk index (points per factor, top 12)")
    f2 = go.Figure(go.Scatter(x=rk.otd_r.fillna(rk.otd), y=rk.cv, mode="markers+text", text=rk.supplier_id, textposition="top center", marker=dict(size=8 + rk.n.clip(upper=60) / 4, color=rk.score, colorscale=[[0, C["te"]], [.5, C["am"]], [1, C["co"]]], showscale=True, colorbar=dict(title="Index")))); f2 = sty(f2, 400, "Delivery reliability vs lead-time variability"); f2.update_xaxes(title="On-time rate", tickformat=".0%"); f2.update_yaxes(title="Lead-time CV")
    sel = sf[0] if sf else rk.supplier_id.iloc[0]; d = X["dl"][(X["dl"].supplier_id == sel) & X["dl"]["done"]]; D1 = pd.to_datetime(d1, errors="coerce") if d1 else pd.NaT; D2 = pd.to_datetime(d2, errors="coerce") if d2 else pd.NaT
    if pd.notna(D1): d = d[d.order_date >= D1]
    if pd.notna(D2): d = d[d.order_date <= D2]
    f3 = empty("No deliveries for the selected supplier")
    if len(d): m = d.assign(m=d.actual_delivery_date.dt.to_period("M").dt.to_timestamp()).groupby("m").agg(lead=("lead", "mean"), late=("late", "mean")).reset_index(); f3 = go.Figure([go.Scatter(x=m["m"], y=m["lead"], name="Mean lead time (days)", mode="lines+markers", line=dict(color=C["te"], width=3)), go.Scatter(x=m["m"], y=m["late"], name="Mean days late", mode="lines+markers", line=dict(color=C["co"]))]); f3 = sty(f3, 360, "Lead-time trend for supplier %s (by delivery month)" % sel)
    dd = X["ss"][X["ss"].z.notna()].sort_values("z", ascending=False).head(8); h += H("Recent deterioration vs each supplier's own baseline") + tbl(dd, [("supplier_id", "Supplier"), ("lead_b", "Baseline lead (d)"), ("lead_r", "Recent lead (d)"), ("det", "Change (d)"), ("z", "z-score"), ("n_r", "Recent deliveries")], dict(lead_b=fx, lead_r=fx, det=lambda v: "%+.1f" % v, z=fx)) + note("Needs at least 5 recent and 10 baseline deliveries. z ≥ 3 with a change of 2+ days raises an alert.", "info")
    h += H("Evidence drill-down: latest deliveries of %s" % sel) + tbl(d.sort_values("actual_delivery_date", ascending=False).head(15), [("purchase_order_id", "PO"), ("component_id", "Component"), ("order_date", "Ordered"), ("promised_date", "Promised"), ("actual_delivery_date", "Delivered"), ("lead", "Lead (d)"), ("late", "Days late"), ("fill", "Fill"), ("defr", "Defect rate")], dict(order_date=dts, promised_date=dts, actual_delivery_date=dts, lead=lambda v: fx(v, 0), late=lambda v: fx(v, 0), fill=pc0, defr=pc1))
    return h, f1, f2, f3
def trajectory(X, c, mode, mult=1.0):
    r = X["inv"].set_index("component_id").loc[c]; H_ = X["P"]["hor"]; ib = X["ib"][X["ib"].component_id == c]; arr = np.zeros(H_ + 1)
    for a, q in zip(ib["d_a" if mode == "adj" else "d_p"], ib["qty_a" if mode == "adj" else "qty"]):
        o = (a - X["asof"]).days
        if 0 <= o <= H_: arr[o] += q
    return r.avail + np.cumsum(arr) - (0 if pd.isna(r.daily) else r.daily * mult) * np.arange(H_ + 1)
@safe("hppp")
def render_inv(sf, cf, pf, d1, d2):
    X = G["X"]; inv = X["inv"]; order = {"Already short": 0, "Projected short before next receipt": 1, "Projected short despite inbound": 2, "Below safety stock": 3, "OK": 4, "No recent demand data": 5}
    if cf: inv = inv[inv.component_id.isin(cf)]
    inv = inv.assign(o=inv.status.map(order)).sort_values(["o", "criticality"], ascending=[True, False])
    h = banner() + note("<b>Formulas.</b> Available = on hand − reserved − allocated (clipped at 0; inbound is <b>not</b> added, so nothing is double counted). Cover = available ÷ average daily demand (last %d weeks of product demand × BOM). Stock-out days come from a daily projection with confirmed inbound: <b>earliest</b> = demand +1σ with risk-adjusted arrivals; <b>latest</b> = demand −1σ with planned arrivals. Components without demand data show no cover instead of zero." % X["P"]["dw"], "info")
    h += tbl(inv.head(80), [("component_id", "Component"), ("criticality", "Crit."), ("status", "Status"), ("on_hand", "On hand"), ("avail", "Available"), ("inb", "Confirmed inbound"), ("nxt", "Next arrival"), ("daily", "Daily demand"), ("cover", "Cover (d)"), ("rlt", "Lead time (d)"), ("so_early", "Stock-out: earliest (day)"), ("so_late", "latest (day)"), ("shortfall", "Shortfall over lead time"), ("short_val", "Shortfall value")],
                    dict(status=lambda v: pill(v, C["co"] if v.startswith(("Already", "Projected")) else (C["am"] if v.startswith("Below") else C["te"])), on_hand=nf, avail=nf, inb=nf, nxt=dts, daily=fx, cover=fx, rlt=lambda v: fx(v, 0), so_early=nf, so_late=nf, shortfall=nf, short_val=money))
    if X["inv"].negs.any(): h += note("%d component(s) have reserved + allocated stock above on hand: available is clipped at 0 (check the source)." % int(X["inv"].negs.sum()), "warn")
    t = inv[inv.daily.gt(0)].sort_values("cover").head(20); f1 = empty("No demand data")
    if len(t): f1 = go.Figure([go.Bar(x=t.component_id, y=t.cover, name="Cover (days)", marker_color=C["te"]), go.Bar(x=t.component_id, y=t.rlt, name="Lead time (days)", marker_color=C["mu"])]); f1.update_layout(barmode="group"); f1 = sty(f1, 380, "Lowest cover vs replenishment lead time")
    c = cf[0] if cf else (inv.component_id.iloc[0] if len(inv) else None); f2 = empty("No component selected"); f3 = empty("No component selected")
    if c and c in set(X["inv"].component_id):
        xs = [X["asof"] + Td(i) for i in range(X["P"]["hor"] + 1)]; r = X["inv"].set_index("component_id").loc[c]; sd_ = 0 if pd.isna(r.dsd) else r.dsd; f2 = go.Figure([go.Scatter(x=xs, y=trajectory(X, c, "planned"), name="Planned arrivals, average demand", line=dict(color=C["te"], width=3)), go.Scatter(x=xs, y=trajectory(X, c, "adj", 1 + (sd_ / r.daily if r.daily and r.daily > 0 else 0)), name="Risk-adjusted arrivals, demand +1σ", line=dict(color=C["co"], dash="dot"))])
        f2.add_hline(y=0, line_color=C["mu"]); f2 = sty(f2, 380, "Projected stock for %s (stock-out when the line crosses zero)" % c); f2.update_yaxes(title="Units")
        w = X["T"]["inv"]; w = w[(w.component_id == c) & (w.snapshot_date == w.snapshot_date.max())]; f3 = go.Figure([go.Bar(x=w.warehouse_id, y=w[k], name=n) for k, n in (("on_hand_quantity", "On hand"), ("reserved_quantity", "Reserved"), ("allocated_quantity", "Allocated"), ("inbound_quantity", "Inbound (recorded)"))]); f3.update_layout(barmode="group"); f3 = sty(f3, 320, "Stock by warehouse: " + c)
    return h, f1, f2, f3
@safe("hpp")
def render_prod(sf, cf, pf, d1, d2):
    X = G["X"]; P1, P2 = X["PX"]["planned"], X["PX"]["adj"]; o = P2["orders"].merge(P1["orders"][["order", "status", "delay"]], on="order", suffixes=("", "_p")); L = P2["lines"]
    if pf: o = o[o["product"].isin(pf)]; L = L[L["product"].isin(pf)]
    if cf: L = L[L.component_id.isin(cf)]; o = o[o["order"].isin(L[L.shortage > 1e-9]["order"])]
    k1, k2 = px_kpi(P1), px_kpi(P2)
    h = banner() + "<div class='kg'>" + card("Orders exposed", "%d / %d" % (k1["exposed"], k2["exposed"]), "planned / risk-adjusted, of %d open orders" % k1["n"], C["am"]) + card("No confirmed supply", "%d / %d" % (k1["blocked"], k2["blocked"]), "delay cannot be quantified", C["co"]) + card("Customer due dates exposed", "%d / %d" % (k1["due"], k2["due"]), "planned / risk-adjusted", C["co"]) + card("Components short", "%d / %d" % (k1["comps"], k2["comps"]), "units short: %s / %s" % (nf(k1["qty"]), nf(k2["qty"])), C["am"]) + card("Quantified delay cost", money(k2["cost"]), "risk-adjusted; delay days × order cost/day", C["co"]) + "</div>"
    h += note("<b>Method.</b> Open orders not yet in progress are processed by priority (1 = highest) then start date. Each takes stock, then inbound arriving by its start; any remainder is covered by the earliest later inbound, which is then <b>consumed</b>, so no unit is counted for two orders. A delay is stated only when confirmed inbound covers the shortage; otherwise the order is 'Blocked (no confirmed supply)' and no days are invented. In-progress orders and products without a BOM are not assessed.", "info")
    ox = o[o.status != "OK"].sort_values(["priority", "start"])
    h += H("Exposed production orders (risk-adjusted view, planned view alongside)") + (tbl(ox.head(60), [("order", "Order"), ("product", "Product"), ("priority", "Prio"), ("start", "Start"), ("due", "Customer due"), ("status", "Status (risk-adj.)"), ("status_p", "Status (planned)"), ("short_comps", "Short components"), ("binding", "Binding constraint"), ("delay", "Delay (d)"), ("new_completion", "New completion"), ("due_exposed", "Due date at risk"), ("delay_cost", "Delay cost")],
                                                                                            dict(start=dts, due=dts, status=lambda v: pill(v, C["co"] if v.startswith("Blocked") else C["am"]), delay=lambda v: fx(v, 0), new_completion=dts, due_exposed=lambda v: pill("Yes", C["co"]) if v else "no", delay_cost=money)) if len(ox) else note("No production order is short on materials in this view.", "ok"))
    sh = L[L.shortage > 1e-9]; ib = X["ib"]; f2 = empty("No shortages to map")
    if len(sh):
        c = sh.groupby("component_id").agg(orders=("order", "nunique"), short=("shortage", "sum"), first_d=("start", "min")).reset_index(); c["suppliers"] = c.component_id.map(lambda x: ", ".join(sorted(set(ib[ib.component_id == x].supplier_id))) or "no open PO"); c["pos"] = c.component_id.map(lambda x: ", ".join(ib[ib.component_id == x].purchase_order_id.head(3)) or "—"); c["ships"] = c.component_id.map(lambda x: ", ".join(ib[(ib.component_id == x) & ib.ship.notna()].ship.head(3)) or "—")
        h += H("Dependency chain: Supplier → PO / shipment → Component → shortage → orders → customer") + tbl(c.sort_values("first_d"), [("suppliers", "Supplier(s) with open POs"), ("pos", "Purchase orders"), ("ships", "Shipments"), ("component_id", "Component"), ("short", "Units short"), ("orders", "Orders affected"), ("first_d", "First shortage date")], dict(short=nf, orders=nf, first_d=dts))
        two = sh.groupby("order").component_id.nunique(); mc = two[two >= 2]
        if len(mc): h += note("%d order(s) are jointly constrained by two or more components (e.g. %s): fixing one component alone will not release them." % (len(mc), ", ".join(mc.index[:4])), "warn")
        e = sh.groupby(["component_id", "order"]).shortage.sum().reset_index().sort_values("shortage", ascending=False).head(40); L_ = list(pd.unique(list(e.component_id) + list(e["order"]))); ix = {n: i for i, n in enumerate(L_)}
        f2 = go.Figure(go.Sankey(node=dict(label=L_, color=C["vi"], pad=12), link=dict(source=[ix[a] for a in e.component_id], target=[ix[b] for b in e["order"]], value=list(e.shortage), color="rgba(240,191,120,.4)"))); f2 = sty(f2, 480, "BOM dependency flow: short components → production orders they hold up (units short)")
    f1 = empty("No exposed orders")
    if len(ox): t = ox.sort_values("priority").head(25); f1 = go.Figure(go.Bar(y=t["order"], x=t.quantity, orientation="h", marker_color=[C["co"] if u else C["am"] for u in t.unq], customdata=t.short_comps, hovertemplate="%{y}: %{x} units, short on %{customdata}<extra></extra>")); f1 = sty(f1, 460, "Exposed production quantity by order (coral = no confirmed supply)"); f1.update_yaxes(autorange="reversed")
    return h, f1, f2
@safe("hpp")
def render_log(sf, cf, pf, d1, d2):
    X = G["X"]; tr = X["T"]["tr"]; ib = X["ib"].copy()
    if sf: ib = ib[ib.supplier_id.isin(sf)]
    if cf: ib = ib[ib.component_id.isin(cf)]
    if tr.empty: return note("No transportation table loaded: logistics monitoring is unavailable.", "warn"), empty("No data"), empty("No data")
    dn = tr[tr.actual_arrival.notna()].copy(); dn["late"] = (dn.actual_arrival - dn.expected_arrival).dt.days.clip(lower=0); dn["tt"] = (dn.actual_arrival - dn.actual_departure).dt.days
    h = banner() + note("Shipment status comes from the uploaded transportation table; this build does not track shipments live.", "info")
    if len(dn): car = dn.groupby("carrier_id").agg(n=("shipment_id", "size"), ontime=("late", lambda s: (s <= X["P"]["tol"]).mean()), late=("late", "mean"), tt=("tt", "mean")).reset_index(); h += H("Delivery performance by carrier (delivered shipments)") + tbl(car, [("carrier_id", "Carrier"), ("n", "Shipments"), ("ontime", "On-time vs ETA"), ("late", "Mean days late"), ("tt", "Mean transit (d)")], dict(n=nf, ontime=pc0, late=fx, tt=fx))
    op = ib[ib.ship.notna()].merge(X["inv"][["component_id", "criticality", "status"]].rename(columns={"status": "cstatus"}), on="component_id"); op["slip"] = (op.eta - op.promised_date).dt.days
    h += H("Open shipments and their component impact") + tbl(op.sort_values("slip", ascending=False).head(40), [("ship", "Shipment"), ("purchase_order_id", "PO"), ("supplier_id", "Supplier"), ("component_id", "Component"), ("criticality", "Crit."), ("carrier", "Carrier"), ("origin", "Origin"), ("sstat", "Status"), ("promised_date", "Promised"), ("eta", "Current ETA"), ("slip", "Slip (d)"), ("cstatus", "Component status")],
                                                                    dict(promised_date=dts, eta=dts, slip=lambda v: "%+.0f" % v, sstat=lambda v: pill(v, C["co"] if str(v).lower().startswith("delay") else C["te"]), cstatus=lambda v: pill(v, C["co"] if v.startswith(("Already", "Projected")) else C["te"])))
    f1 = empty("No delivered shipments")
    if len(dn): f1 = go.Figure([go.Histogram(x=d.tt, name=m, opacity=.7) for m, d in dn.groupby("transport_mode")]); f1.update_layout(barmode="overlay"); f1 = sty(f1, 340, "Transit-time distribution by mode (delivered shipments)"); f1.update_xaxes(title="Days")
    f2 = empty("No open shipments")
    if len(op): e = op.groupby(["carrier", "origin"]).size().reset_index(name="n"); e["lab"] = e.carrier.astype(str) + " / " + e.origin.astype(str); f2 = sty(go.Figure(go.Bar(x=e.lab, y=e.n, marker_color=[C["co"] if v >= max(3, .25 * len(op)) else C["te"] for v in e.n])), 340, "Open-shipment exposure by carrier and route (coral = concentration)"); f2.update_yaxes(title="Open shipments")
    return h, f1, f2
@safe("hpp")
def render_risk(sf, cf, pf, d1, d2):
    X = G["X"]; A = fa(X["alerts"], sf, cf); h = banner() + note("<b>Alerts</b> use supplier-specific baselines, rolling windows and robust comparisons rather than one universal threshold. They are <b>risk indicators</b>, not probabilities. <b>Supervised disruption model: not included in this build</b> (it needs labelled historical outcomes and time-aware validation); only transparent rules and anomaly signals are used.", "ai"); cnt = pd.DataFrame(columns=["type", "sev", "n"])
    if A:
        ad = pd.DataFrame(A).assign(o=lambda d: d.sev.map({"High": 0, "Medium": 1, "Low": 2})).sort_values(["o", "n_orders"], ascending=[True, False]); cnt = ad.groupby(["type", "sev"]).size().reset_index(name="n")
        h += H("Alert log (%d alerts, observation date %s)" % (len(ad), dts(X["asof"]))) + tbl(ad.head(80), [("sev", "Severity"), ("type", "Alert"), ("entity", "Entity"), ("date", "Observed"), ("why", "Why it triggered"), ("orders", "Affected orders"), ("conseq", "Potential consequence"), ("nxt", "Suggested next step"), ("conf", "Confidence / data limits")], dict(sev=pill, date=dts))
    else: h += note("No alerts triggered.", "ok")
    f1 = empty("No alerts")
    if len(cnt): f1 = go.Figure([go.Bar(x=d.type, y=d.n, name=s, marker_color=SEVC[s]) for s, d in cnt.groupby("sev")]); f1.update_layout(barmode="stack"); f1 = sty(f1, 360, "Alerts by type and severity"); f1.update_xaxes(tickangle=-25)
    rk = X["risk"].sort_values("score", ascending=False).head(10); inv = X["inv"]; cs = list(inv[(inv.criticality >= 4) & (inv.status != "OK")].sort_values("criticality", ascending=False).component_id.head(12)); f2 = empty("No at-risk critical components")
    if cs: z = [[r.score if r.supplier_id in X["apm"][c] else np.nan for c in cs] for r in rk.itertuples()]; f2 = go.Figure(go.Heatmap(z=z, x=cs, y=list(rk.supplier_id), colorscale=[[0, C["sf"]], [.5, C["am"]], [1, C["co"]]], colorbar=dict(title="Supplier index"), hovertemplate="%{y} supplies %{x}: index %{z:.0f}<extra></extra>")); f2 = sty(f2, 380, "Risk heatmap: top-risk suppliers × at-risk critical components (blank = not an approved supplier)")
    return h, f1, f2
@safe("hp")
def render_mit(sf, cf, pf, d1, d2, mode, allow, budget):
    X = G["X"]; m = "adj" if mode and mode.startswith("Risk") else "planned"; R = mitigate(X, m, None, bool(allow), float(budget or 0)); a, u, kb, ka = R["acts"], R["unres"], R["kb"], R["ka"]
    h = banner() + note("<b>Heuristic, not a proven optimum.</b> For each short component (most critical first) options are ranked by arrival before the shortage date, then by all-in cost per unit; capacity, qualification and an optional budget are enforced. OR-Tools is not used in this build, so the plan may not be globally optimal. <b>Nothing is executed</b>: every action needs human approval; unqualified suppliers appear only if you allow them and are labelled.", "warn")
    h += "<div class='kg'>" + card("Actions proposed", nf(len(a)), "cost %s" % money(R["spent"])) + card("Orders exposed", "%d → %d" % (kb["exposed"], ka["exposed"]), "before → after (residual risk)", C["am"]) + card("No confirmed supply", "%d → %d" % (kb["blocked"], ka["blocked"]), "unquantified exposure", C["co"]) + card("Quantified delay cost", "%s → %s" % (money(kb["cost"]), money(ka["cost"])), "estimated, not realised savings", C["vi"]) + card("Unresolved shortages", nf(len(u)), "no feasible option", C["co"]) + "</div>"
    if len(a): h += H("Recommended actions (pending human approval)") + tbl(a, [("option_id", "Option"), ("action", "Action"), ("component_id", "Component"), ("supplier_id", "Supplier"), ("qty", "Units"), ("cost", "Estimated cost"), ("arrival", "Arrives"), ("timely", "Before shortage date"), ("qualification", "Qualification"), ("status", "Approval")], dict(qty=nf, cost=money, arrival=dts, timely=lambda v: pill("Yes", C["te"]) if v else pill("Late: reduces delay only", C["am"]), qualification=lambda v: pill(v, C["te"] if v == "approved" else C["co"])))
    if len(u): h += H("Unresolved: no feasible plan within constraints") + tbl(u, [("component_id", "Component"), ("qty", "Units still short"), ("need", "Needed by"), ("reason", "Reason")], dict(qty=nf, need=dts))
    if not len(a) and not len(u): h += note("No component is short in this view: no mitigation is needed.", "ok")
    h += note("Dependencies and assumptions: lead times and costs come from the mitigation_options table; expedite only helps if it arrives before the current ETA; warehouse transfers and substitutions are <b>not</b> optimised here; the exposure reduction is the change in the production propagation (an estimate).", "info")
    pts = [("Do nothing", 0.0, kb["exposed"])]
    for lab, au in (("Approved suppliers only", False), ("Also unqualified suppliers", True)): x = mitigate(X, m, None, au, float(budget or 0)); pts.append((lab, x["spent"], x["ka"]["exposed"]))
    f = go.Figure([go.Scatter(x=[c], y=[r], mode="markers+text", text=[n], textposition="top center", marker=dict(size=16), showlegend=False) for n, c, r in pts]); f = sty(f, 360, "Cost vs residual exposure (orders still exposed)"); f.update_xaxes(title="Mitigation cost"); f.update_yaxes(title="Orders exposed after plan"); return h, f
def spec_text(s):
    t = []
    if "delay_sup" in s: t.append("supplier %s +%d d" % (s["delay_sup"], s["delay_days"]))
    if "delay_ship" in s: t.append("shipment %s +%d d" % (s["delay_ship"], s["delay_days"]))
    if "fail_sup" in s: t.append("supplier %s fails to deliver" % s["fail_sup"])
    if "dm" in s: t.append("demand %+.0f%% (%s)" % (100 * (list(s["dm"].values())[0] - 1), list(s["dm"].keys())[0]))
    if "drop_ship" in s: t.append("shipment %s unavailable" % s["drop_ship"])
    if "defect_comp" in s: t.append("%s inbound loss +%.0f%%" % (s["defect_comp"], s["defect_pct"]))
    if "extra" in s: t.append("extra supply %s × %s" % (s["extra"][0][0], nf(s["extra"][0][1])))
    if "exp_ship" in s: t.append("shipment %s expedited to %d d" % (s["exp_ship"], s["exp_days"]))
    if s.get("seq") == "due": t.append("resequenced by customer due date")
    return "; ".join(t) or "no changes (baseline)"
def make_spec(X, dsup, ddays, dship, fail, dpct, dprod, drop, dfp, dcp, xc, xq, xd, es, ed, seq):
    s = {}
    if ddays:
        if dsup: s["delay_sup"] = dsup; s["delay_days"] = int(ddays)
        elif dship: s["delay_ship"] = dship; s["delay_days"] = int(ddays)
    if fail: s["fail_sup"] = fail
    if dpct: s["dm"] = {(dprod or "All"): 1 + float(dpct) / 100}
    if drop: s["drop_ship"] = drop
    if dfp and dcp: s["defect_comp"] = dcp; s["defect_pct"] = float(dfp)
    if xc and xq: s["extra"] = [(xc, float(xq), X["asof"] + Td(xd or 0))]
    if es: s["exp_ship"] = es; s["exp_days"] = int(ed or 3)
    if seq and seq.startswith("Customer"): s["seq"] = "due"
    return s
def scn_kpis(X, mode, spec, with_mit=False):
    k = px_kpi(propagate(X, mode, spec)); k["mit_cost"] = np.nan; k["mit_resid"] = np.nan
    if with_mit: R = mitigate(X, mode, spec, False); k["mit_cost"] = R["spent"]; k["mit_resid"] = R["ka"]["exposed"]
    return k
@safe("hp")
def render_scn(mode, dsup, ddays, dship, fail, dpct, dprod, drop, dfp, dcp, xc, xq, xd, es, ed, seq, wm):
    X = G["X"]; m = "adj" if mode and mode.startswith("Risk") else "planned"; spec = make_spec(X, dsup, ddays, dship, fail, dpct, dprod, drop, dfp, dcp, xc, xq, xd, es, ed, seq); kb = scn_kpis(X, m, {}, bool(wm)); ks = scn_kpis(X, m, spec, bool(wm)); G["scn"] = dict(spec=spec, text=spec_text(spec), kb=kb, ks=ks, mode=m)
    rows = [("Components short", nf(kb["comps"]), nf(ks["comps"])), ("Production orders exposed", nf(kb["exposed"]), nf(ks["exposed"])), ("Orders with no confirmed supply", nf(kb["blocked"]), nf(ks["blocked"])), ("Customer due dates at risk", nf(kb["due"]), nf(ks["due"])), ("Units short", nf(kb["qty"]), nf(ks["qty"])), ("Quantified delay (days, known only)", nf(kb["delay_days"]), nf(ks["delay_days"])),
            ("Quantified delay cost", money(kb["cost"]), money(ks["cost"])), ("First shortage date", dts(kb["first"]), dts(ks["first"]))] + ([("Mitigation cost (heuristic, approved suppliers)", money(kb["mit_cost"]), money(ks["mit_cost"])), ("Orders exposed after mitigation (residual)", nf(kb["mit_resid"]), nf(ks["mit_resid"]))] if wm else [])
    h = banner() + note("<b>Hypothetical scenario: not an actual event and not a forecast.</b> Changed assumptions: <b>%s</b>. Arrival basis: %s." % (esc(spec_text(spec)), "risk-adjusted" if m == "adj" else "planned dates"), "warn") + tbl(pd.DataFrame(rows, columns=["m", "b", "s"]), [("m", "Metric"), ("b", "Baseline"), ("s", "Scenario")], dict(b=str, s=str))
    h += note("This lab recalculates production exposure through the BOM with the same no-double-counting allocation. Stock is pooled across warehouses (transfers are not modelled). Component stock-out dates are on the Inventory Radar.", "info")
    f = go.Figure([go.Bar(x=["Components short", "Orders exposed", "Blocked", "Due dates at risk"], y=[kb["comps"], kb["exposed"], kb["blocked"], kb["due"]], name="Baseline", marker_color=C["mu"]), go.Bar(x=["Components short", "Orders exposed", "Blocked", "Due dates at risk"], y=[ks["comps"], ks["exposed"], ks["blocked"], ks["due"]], name="Scenario", marker_color=C["am"])]); f.update_layout(barmode="group"); return h, sty(f, 360, "Baseline vs scenario")
def save_scn():
    if "scn" not in G: return note("Run a scenario first.", "info")
    G.setdefault("saved", []).append(dict(name="Scenario %d" % (len(G["saved"]) + 1), text=G["scn"]["text"], exposed=G["scn"]["ks"]["exposed"], blocked=G["scn"]["ks"]["blocked"], due=G["scn"]["ks"]["due"], cost=G["scn"]["ks"]["cost"]))
    return note("Saved (kept for this session only).", "ok") + tbl(pd.DataFrame(G["saved"]), [("name", "Name"), ("text", "Assumptions"), ("exposed", "Orders exposed"), ("blocked", "Blocked"), ("due", "Due dates at risk"), ("cost", "Delay cost")], dict(cost=money))
@safe("hh")
def render_dq():
    D = G["D"]; h = banner() + note("Rows read per table: " + ", ".join("%s %s" % (TN[k], nf(v)) for k, v in D["rows_in"].items()) + ". As-of date = latest inventory snapshot (%s). Raw uploads stay unchanged; a validated copy is analysed. Excluded rows: <b>%d</b> (listed; nothing is dropped silently)." % (dts(D["asof"]), sum(c for _, _, c in D["excluded"])), "ok")
    h += "".join(note(esc(m), "err" if l == "error" else "warn" if l == "warn" else "info") for l, m in D["issues"]) or note("No validation issues.", "ok")
    if D["excluded"]: h += H("Excluded rows by reason") + tbl(pd.DataFrame(D["excluded"], columns=["t", "w", "c"]), [("t", "Table"), ("w", "Reason"), ("c", "Rows")], dict(c=nf))
    return h, H("Self-test results (run at start-up)") + "".join(note(("PASS " if ok else "FAIL ") + esc(g + ": " + n) + " — " + esc(d), "ok" if ok else "err") for g, n, ok, d in TESTS)

# ------------------------------ ORBIT Strategist ------------------------------
def opt_table(X, c):
    mit = X["T"]["mit"]; mit = mit[mit.component_id == c]; L = X["PX"]["adj"]["lines"]; need = L[(L.component_id == c) & (L.shortage > 1e-9)].start.min(); rows = []
    for o in mit.itertuples(): arr = X["asof"] + Td(o.estimated_lead_time); rows.append("%s %s (%s): arrives %s%s, fixed %s + %s/unit, capacity %s" % (o.option_id, o.action_type, o.qualification_status, dts(arr), (" — before the %s shortage" % dts(need) if pd.notna(need) and arr <= need else (" — after the %s shortage" % dts(need) if pd.notna(need) else "")), money(o.estimated_cost), fx(0 if pd.isna(o.unit_cost_premium) else o.unit_cost_premium, 2), nf(o.capacity_limit)))
    return rows
def ask(q, use_llm=False):
    if "X" not in G: return "Load data first."
    X = G["X"]; q = (q or "").strip() or "Which supplier poses the greatest immediate production risk?"; ql = q.lower(); parts = []; ids = {k: re.findall(p, q, re.I) for k, p in dict(s=r"\bS\d{2}\b", c=r"\bC\d{3}\b", sh=r"\bSH\d{4}\b").items()}; P2 = X["PX"]["adj"]; ko = P2["orders"]
    if re.search(r"supplier.*(risk|greatest)|greatest.*risk", ql) and not ids["s"]: r = X["risk"].sort_values("score", ascending=False).head(3); parts.append(("supplier_risk", "Top suppliers by risk index: " + "; ".join("%s (index %.0f; %d order(s) exposed) — %s" % (x.supplier_id, x.score, x.n_orders, x.evidence) for x in r.itertuples()) + ". The index is descriptive, not a probability."))
    if ids["s"]: x = X["risk"].set_index("supplier_id").loc[ids["s"][0].upper()]; parts.append(("supplier_detail", "%s: risk index %.0f; %s." % (ids["s"][0].upper(), x.score, x.evidence)))
    if re.search(r"stop|next week|production", ql) and re.search(r"component|stop|week", ql):
        L = P2["lines"]; s = L[(L.shortage > 1e-9) & (L.start <= X["asof"] + Td(10))]; g = s.groupby("component_id").agg(o=("order", "nunique"), q=("shortage", "sum"), f=("start", "min")).sort_values("f").head(6); parts.append(("production_impact", "Components short for orders starting within 10 days (risk-adjusted): " + ("; ".join("%s: %s units short, %d order(s), first %s" % (c, nf(r["q"]), r["o"], dts(r["f"])) for c, r in g.iterrows()) if len(g) else "none") + "."))
    m = re.search(r"(\d+)\s*days?", ql)
    if re.search(r"what happens|what if|delayed", ql) and m and (ids["sh"] or ids["s"]):
        sp = dict(delay_days=int(m.group(1))); (sp.__setitem__("delay_ship", ids["sh"][0].upper()) if ids["sh"] else sp.__setitem__("delay_sup", ids["s"][0].upper())); kb, ks = scn_kpis(X, "adj", {}), scn_kpis(X, "adj", sp); parts.append(("scenario_simulation", "Hypothetical: %s. Orders exposed %d → %d; due dates at risk %d → %d; units short %s → %s; quantified delay cost %s → %s." % (spec_text(sp), kb["exposed"], ks["exposed"], kb["due"], ks["due"], nf(kb["qty"]), nf(ks["qty"]), money(kb["cost"]), money(ks["cost"]))))
    if re.search(r"expedite|alternate", ql):
        cs = [c.upper() for c in ids["c"]] or list(P2["lines"][P2["lines"].shortage > 1e-9].component_id.value_counts().head(1).index)
        for c in cs[:1]: parts.append(("mitigation_options", "Options for %s: " % c + (" | ".join(opt_table(X, c)) or "none in the mitigation table") + ". Unqualified suppliers need qualification and human approval."))
    if re.search(r"single.?source|sole", ql): inv = X["inv"].set_index("component_id"); s = [(c, inv.criticality[c]) for c, v in X["apm"].items() if len(v) == 1 and c in inv.index]; s.sort(key=lambda t: -t[1]); parts.append(("single_source", "%d single-source components; most critical: " % len(s) + "; ".join("%s (crit %d, supplier %s, status %s)" % (c, k, X["apm"][c][0], inv.status[c]) for c, k in s[:6]) + "."))
    if re.search(r"lowest.?cost|cheapest|mitigation plan", ql): R = mitigate(X, "adj"); parts.append(("mitigation_plan", "Lowest-cost feasible plan (heuristic, approved suppliers only): %d action(s), cost %s; orders exposed %d → %d; %d component(s) unresolved." % (len(R["acts"]), money(R["spent"]), R["kb"]["exposed"], R["ka"]["exposed"], len(R["unres"]))))
    if re.search(r"customer|deliver.*exposed|due", ql): d = ko[ko.due_exposed].sort_values("due").head(6); parts.append(("customer_exposure", "%d customer due date(s) at risk (risk-adjusted): " % int(ko.due_exposed.sum()) + "; ".join("%s (%s) due %s, %s" % (r.order, r.product, dts(r.due), r.status) for r in d.itertuples()) + "."))
    if re.search(r"limit|caveat|trust", ql): parts.append(("limitations", "Synthetic or uploaded data only; no live feeds; risk index and alerts are indicators, not probabilities; delays are quantified only where confirmed inbound exists; heuristics may not be optimal; recommendations need human approval."))
    if not parts: k = px_kpi(X["PX"]["planned"]); ka = px_kpi(P2); parts = [("summary", "%d open production orders; exposed %d (planned) / %d (risk-adjusted); %d component(s) short; %d alerts (%d high)." % (k["n"], k["exposed"], ka["exposed"], ka["comps"], len(X["alerts"]), sum(a["sev"] == "High" for a in X["alerts"])))]
    ctx = "\n".join("[%s] %s" % (n, t) for n, t in parts); out = "### Answer (deterministic, computed by analytical tools)\n" + "\n".join("- **%s**: %s" % (n, t) for n, t in parts) + "\n\n*Every figure comes from the loaded dataset or is labelled hypothetical. Recommendations need human review.*"
    if not use_llm: return out
    k = os.environ.get("ANTHROPIC_API_KEY")
    if not k: return out + "\n\n*External LLM disabled: no ANTHROPIC_API_KEY environment variable is set. The answer above is complete.*"
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json={"model": "claude-sonnet-5-5", "max_tokens": 700, "system": "You are a supply chain analytics assistant. Answer ONLY from the TOOL RESULTS. Never invent suppliers, shipments, quantities or costs. Be concise.", "messages": [{"role": "user", "content": "TOOL RESULTS:\n" + ctx + "\n\nQUESTION: " + q}]}, timeout=60); r.raise_for_status()
        return "### LLM-written answer (aggregated tool results sent after you ticked the box)\n" + "".join(b.get("text", "") for b in r.json().get("content", [])) + "\n\n---\n" + out
    except Exception as e: return out + "\n\n*LLM call failed (%s); deterministic answer shown.*" % type(e).__name__

# ------------------------------ exports ------------------------------
def export_all():
    if "X" not in G: return None, note("Load data first.", "info")
    X = G["X"]; out = []
    def w(df, fn):
        df.to_csv(fn, index=False)
        if os.path.exists(fn): out.append(fn)
    rk = X["risk"].merge(X["T"]["sup"][["supplier_id", "region"]], on="supplier_id"); w(rk, "orbit_supplier_risk.csv"); ib = X["ib"]; w(ib[ib.delayed][["purchase_order_id", "supplier_id", "component_id", "promised_date", "eta", "d_p", "d_a", "qty", "ship", "sstat"]], "orbit_po_delays.csv")
    inv = X["inv"]; w(inv[inv.status != "OK"], "orbit_inventory_shortages.csv"); fc = inv[["component_id", "avail", "daily", "cover", "rlt", "so_early", "so_pt", "so_late"]].copy()
    for c in ("so_early", "so_pt", "so_late"): fc[c + "_date"] = fc[c].map(lambda v: dts(X["asof"] + Td(v)) if pd.notna(v) else "")
    w(fc, "orbit_stockout_forecast.csv"); o = X["PX"]["adj"]["orders"]; w(o[o.status != "OK"], "orbit_orders_exposed.csv"); ad = pd.DataFrame(X["alerts"]); ad = ad.assign(comp_list=ad.comp_list.map(lambda l: ";".join(l))) if len(ad) else ad; w(ad, "orbit_alerts.csv"); w(ad[ad.type == "Shipment exception"] if len(ad) else ad, "orbit_shipment_exceptions.csv")
    R = mitigate(X, "adj"); w(R["acts"], "orbit_mitigation_actions.csv")
    if "scn" in G: s = G["scn"]; w(pd.DataFrame([dict(metric=k, baseline=s["kb"][k], scenario=s["ks"][k], assumptions=s["text"]) for k in ("comps", "exposed", "blocked", "due", "qty", "delay_days", "cost")]), "orbit_scenario_comparison.csv")
    kp, ka = px_kpi(X["PX"]["planned"]), px_kpi(X["PX"]["adj"]); top = rk.sort_values("score", ascending=False).head(5)
    md = ["# ORBIT AI — Executive report", "", "_Synthetic data; planted disruptions._" if G.get("demo") else "", "", "## Most critical risks"] + ["- Supplier %s: index %.0f — %s." % (r.supplier_id, r.score, r.evidence) for r in top.itertuples()] + ["", "## Exposed production orders and customer commitments", "%d of %d open orders exposed (planned) / %d (risk-adjusted); %d customer due dates at risk; %d orders have no confirmed supply." % (kp["exposed"], kp["n"], ka["exposed"], ka["due"], ka["blocked"]), ""] + ["- %s (%s) due %s: %s, short on %s" % (r.order, r.product, dts(r.due), r.status, r.short_comps) for r in o[o.due_exposed].sort_values("due").head(10).itertuples()] + ["", "## Recommended actions (pending human approval)"] + ["- %s %s for %s: %s units, cost %s, arrives %s, qualification %s" % (r.action, r.option_id, r.component_id, nf(r.qty), money(r.cost), dts(r.arrival), r.qualification) for r in R["acts"].itertuples()] + ["", "Estimated cost %s; orders exposed %d → %d after the plan (residual risk); %d unresolved component(s)." % (money(R["spent"]), R["kb"]["exposed"], R["ka"]["exposed"], len(R["unres"])), "", "## Assumptions and limitations", "Risk-adjusted view adds each supplier's typical lateness and fill/defect losses. Delays are quantified only where confirmed inbound exists. Heuristic mitigation, no OR-Tools. Scenarios are hypothetical. No live feeds. No PDF export in this build."]
    open("orbit_executive_report.md", "w", encoding="utf-8").write("\n".join(md)); out.append("orbit_executive_report.md"); css = "body{font-family:Inter,Arial,sans-serif;background:#14252D;color:#F1F5F4;max-width:980px;margin:30px auto;padding:0 18px}h1{color:#80E0C0}"
    open("orbit_executive_report.html", "w", encoding="utf-8").write("<html><head><meta charset='utf-8'><title>ORBIT AI</title><style>" + css + "</style></head><body><h1>ORBIT AI — Executive report</h1>" + "".join("<p>%s</p>" % esc(x) for x in md[2:] if x) + "</body></html>"); out.append("orbit_executive_report.html")
    return [f for f in out if os.path.exists(f)], note("Generated %d files from the active dataset." % len(out), "ok")

# ------------------------------ self-tests ------------------------------
def mini():
    A0 = pd.Timestamp("2026-03-20"); d = pd.Timestamp
    sup = pd.DataFrame(dict(supplier_id=["SA", "SB"], supplier_name=["A", "B"], region=["x", "y"], material_categories=["m", "m"], standard_lead_time_days=[10, 10], contractual_lead_time_days=[10, 10], minimum_order_quantity=[1, 1], unit_cost_multiplier=[1, 1], capacity_limit=[1000, 1000], quality_rate=[.99, .9], historical_on_time_rate=[.9, .9], alternate_supplier_status=["approved", "approved"]))
    comp = pd.DataFrame(dict(component_id=["CA", "CB"], component_name=["a", "b"], category=["m", "m"], unit_cost=[10.0, 20.0], criticality=[5, 3], shelf_life_days=[np.nan, np.nan], minimum_order_quantity=[1, 1], standard_replenishment_days=[10, 10], approved_supplier_ids=["SA", "SA;SB"]))
    rows = [("PO1", "SA", "2026-01-01", "2026-01-11", "2026-01-11", 100, 100, 0), ("PO2", "SA", "2026-01-15", "2026-01-25", "2026-01-25", 100, 100, 0), ("PO3", "SA", "2026-02-01", "2026-02-11", "2026-02-13", 100, 90, 9), ("PO4", "SA", "2026-02-20", "2026-03-02", "2026-03-06", 100, 100, 0), ("PO5", "SB", "2026-01-05", "2026-01-15", "2026-01-15", 100, 100, 0)]
    dl = pd.DataFrame([dict(purchase_order_id=a, supplier_id=b, component_id="CA", order_date=d(c), promised_date=d(e), actual_delivery_date=d(f), ordered_quantity=g, received_quantity=h, defect_quantity=i, delivery_status="Delivered") for a, b, c, e, f, g, h, i in rows])
    dl = pd.concat([dl, pd.DataFrame([dict(purchase_order_id="PO6", supplier_id="SA", component_id="CA", order_date=d("2026-03-10"), promised_date=d("2026-03-25"), actual_delivery_date=pd.NaT, ordered_quantity=50, received_quantity=0, defect_quantity=0, delivery_status="Open")])], ignore_index=True)
    inv = pd.DataFrame([dict(component_id="CA", warehouse_id="W1", snapshot_date=A0, on_hand_quantity=60, reserved_quantity=6, allocated_quantity=3, inbound_quantity=50, safety_stock=20, reorder_point=30, storage_capacity=500), dict(component_id="CA", warehouse_id="W2", snapshot_date=A0, on_hand_quantity=40, reserved_quantity=4, allocated_quantity=2, inbound_quantity=0, safety_stock=0, reorder_point=0, storage_capacity=500), dict(component_id="CB", warehouse_id="W1", snapshot_date=A0, on_hand_quantity=40, reserved_quantity=0, allocated_quantity=0, inbound_quantity=0, safety_stock=0, reorder_point=0, storage_capacity=500)])
    pr = pd.DataFrame([dict(production_order_id="MO1", finished_product_id="PA", quantity=50, planned_start_date=d("2026-03-21"), planned_completion_date=d("2026-03-25"), priority=1, status="Planned", customer_due_date=d("2026-03-30"), shortage_cost_per_day=1000), dict(production_order_id="MO2", finished_product_id="PA", quantity=50, planned_start_date=d("2026-03-22"), planned_completion_date=d("2026-03-26"), priority=2, status="Planned", customer_due_date=d("2026-04-05"), shortage_cost_per_day=1000)])
    bom = pd.DataFrame([dict(finished_product_id="PA", component_id="CA", quantity_required_per_unit=1)]); dem = pd.DataFrame([dict(product_id="PA", period=A0 - Td(7 * (8 - k)), actual_demand=70, forecast_demand=70) for k in range(8)])
    mit = pd.DataFrame([dict(option_id="M1", component_id="CA", supplier_id="SB", action_type="Alternate supplier", estimated_lead_time=5, estimated_cost=100, capacity_limit=10, qualification_status="requires_qualification", unit_cost_premium=1), dict(option_id="M2", component_id="CA", supplier_id="SB", action_type="Alternate supplier", estimated_lead_time=5, estimated_cost=50, capacity_limit=8, qualification_status="approved", unit_cost_premium=1)])
    return dict(sup=sup, comp=comp, dl=dl, inv=inv, pr=pr, bom=bom, tr=None, dem=dem, mit=mit)
def run_selftests(verbose=True):
    if TESTS: return TESTS
    T = []; saved = dict(G)
    def chk(g, n, fn):
        try: ok, det = fn(); T.append((g, n, bool(ok), det))
        except Exception as e: T.append((g, n, False, type(e).__name__ + ": " + str(e)[:90]))
    MX = lambda: build(load_all(mini()), DEF)
    def t_v1():
        r = mini(); r["comp"] = r["comp"].drop(columns=["unit_cost"])
        try: load_all(r); return False, "no error"
        except ValueError as e: return "unit_cost" in str(e), "missing required column reported with guidance"
    def t_v2():
        r = mini(); d = r["dl"]; r["dl"] = pd.concat([d, d.iloc[[0]].assign(supplier_id="SX", purchase_order_id="PX1"), d.iloc[[0]], d.iloc[[1]].assign(purchase_order_id="PX2", ordered_quantity=-5), d.iloc[[1]].assign(purchase_order_id="PX3", received_quantity=500)], ignore_index=True); D = load_all(r); w = " | ".join(m for _, m in D["issues"])
        return "unknown supplier_id" in w and "duplicate" in w and "negative" in w and (D["dl"].purchase_order_id == "PX3").any() and not (D["dl"].purchase_order_id == "PX1").any(), "unknown supplier, duplicate id and negative quantity excluded; received > ordered kept as an exception"
    def t_m(): s = MX()["ss"].set_index("supplier_id").loc["SA"]; return abs(s["otd"] - .5) < 1e-9 and abs(s["lead_mean"] - 11.5) < 1e-9 and abs(s["defr"] - 9 / 390) < 1e-9 and abs(s["short"] - .25) < 1e-9, "on-time 50%, mean lead 11.5 d, defect 2.31%, short-fill 25%"
    def t_i(): r = MX()["inv"].set_index("component_id").loc["CA"]; return r["avail"] == 85 and r["inb"] == 50 and abs(r["cover"] - 8.5) < 1e-9, "available 85 (inbound 50 not added), cover 8.5 days"
    def t_p(): return project(100, 10, [], 120) == 10 and project(85, 10, [(5, 50)], 120) == 14 and project(100, 0, [], 120) is None, "stock-out day 10 without inbound, day 14 with 50 arriving on day 5, none with zero demand"
    def t_dbl():
        X = MX(); o = X["PX"]["planned"]["orders"].set_index("order"); l = X["PX"]["planned"]["lines"]; return o.status["MO1"] == "OK" and o.status["MO2"] == "Delayed" and o.delay["MO2"] == 3 and abs(l[l["order"] == "MO2"].shortage.iloc[0] - 15) < 1e-9, "two orders share 85 units: the second is 15 short and delayed 3 days until the inbound; no unit used twice"
    def t_unq(): k = propagate(MX(), "planned", dict(fail_sup="SA"))["orders"].set_index("order"); return bool(k.unq["MO2"]) and pd.isna(k.delay["MO2"]) and pd.isna(k.delay_cost["MO2"]), "no confirmed supply: delay stays unquantified instead of invented"
    def t_mi():
        X = MX(); sp = dict(fail_sup="SA"); R = mitigate(X, "planned", sp, False); R2 = mitigate(X, "planned", sp, True); return R["acts"].qty.sum() <= 8 + 1e-9 and "M1" not in set(R["acts"].option_id) and abs(R["unres"].qty.sum() - 7) < 1e-9 and R2["unres"].empty and (R2["acts"].groupby("option_id").qty.sum() <= pd.Series({"M1": 10, "M2": 8})).all(), "capacity respected; unqualified supplier excluded by default (7 units unresolved); allowed explicitly it closes the gap"
    def t_mb(): R = mitigate(MX(), "planned", dict(fail_sup="SA"), True, 60.0); return R["spent"] <= 60 + 1e-9, "budget cap respected (spent %s)" % money(R["spent"])
    def t_s(): X = MX(); b = propagate(X, "planned")["orders"].set_index("order"); s1 = propagate(X, "planned", dict(delay_sup="SA", delay_days=10))["orders"].set_index("order"); return b.delay["MO2"] == 3 and s1.delay["MO2"] == 13, "a 10-day supplier delay moves the order delay from 3 to 13 days"
    def t_r(): X = DX(); s = X["risk"].score; return s.between(0, 100).all() and len(s) == 40, "40 supplier scores within 0-100 (S03 index %.0f, median %.0f)" % (X["risk"].set_index("supplier_id").score["S03"], s.median())
    def t_mp(): X = DX(); c = X["PX"]["adj"]["lines"]; c = c[(c.component_id == "C017") & (c.shortage > 1e-9)]; st = X["inv"].set_index("component_id").status["C017"]; return c["order"].nunique() >= 2 and st != "OK", "planted single-source C017 (status '%s') threatens %d production orders" % (st, c["order"].nunique())
    def t_x():
        s2 = dict(G); X = DX(); G.clear(); G.update(X=X, D=get_demo(), demo=True); f, _ = export_all(); n = len(pd.read_csv("orbit_alerts.csv")); G.clear(); G.update(s2); return n == len(X["alerts"]) and "orbit_executive_report.md" in f, "%d files; alerts export has %d rows matching the analysis" % (len(f), n)
    def t_l(): s2 = dict(G); G.clear(); G.update(X=MX(), D=None, demo=False); a = ask("What are the limitations?", False); G.clear(); G.update(s2); return "deterministic" in a, "assistant answers from tools without any API key"
    for g, n, f in [("validation", "missing required column", t_v1), ("validation", "foreign keys, duplicates, negatives", t_v2), ("metrics", "on-time, lead time, defects, short-fill", t_m), ("inventory", "availability and coverage", t_i), ("inventory", "stock-out projection incl. zero demand", t_p), ("production", "no double-counted inventory", t_dbl),
                    ("production", "unquantified delay stays unquantified", t_unq), ("mitigation", "capacity, qualification, infeasibility", t_mi), ("mitigation", "budget constraint", t_mb), ("scenario", "delay propagation", t_s), ("risk", "score bounds", t_r), ("production", "planted shortage propagates", t_mp), ("reporting", "CSV consistency", t_x), ("strategist", "works without an API key", t_l)]: chk(g, n, f)
    G.clear(); G.update(saved); TESTS[:] = T
    if verbose:
        for g, n, ok, d in T: print(("PASS " if ok else "FAIL ") + g + ": " + n + " :: " + d)
        print("Result: %d of %d self-tests passed." % (sum(1 for t in T if t[2]), len(T)))
    return TESTS

# ------------------------------ project export ------------------------------
METH = """### Methodology
- **Supplier risk index** (0-100, descriptive): weighted blend of reliability, lead-time volatility, quality and fill, open delays, critical-part and sole-source exposure; missing factors are skipped and weights renormalised. Deterioration (recent vs earlier lead times) is a separate anomaly signal. Not a probability.
- **Inventory:** available = on hand − reserved − allocated; cover = available ÷ daily demand (product demand × BOM); stock-out range from a daily projection with confirmed inbound; inbound is never added to available.
- **Planned vs risk-adjusted:** planned uses ETAs; risk-adjusted adds the supplier's median lateness and expected fill/defect losses.
- **Production propagation:** orders by priority (1 = highest); each takes stock then earlier inbound, then later inbound which is consumed. Delays only where confirmed inbound covers the shortage; otherwise 'no confirmed supply'.
- **Mitigation:** deterministic heuristic (timely first, then cost per unit; capacity, qualification and budget enforced). Not OR-Tools; may not be optimal. Human approval required.
- **Not included:** supervised disruption model, OR-Tools, PDF export, optimised warehouse transfers and substitutions, live data.
"""
LICENSE = "MIT License\n\nCopyright (c) 2026 ORBIT AI contributors\n\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the \"Software\"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\n\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\n\nTHE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n"
README = """# ORBIT AI — Supply Chain Risk & Resilience Intelligence
See the disruption before it hits production.

Connects supplier signals, inventory, shipments and bills of materials to show which production orders and customer deliveries a disruption threatens, then proposes and simulates mitigations. Bundled data is **fictional synthetic data** with planted disruptions; nothing is live.

## Architecture
@@@mermaid
flowchart LR
  A[CSV or synthetic data] --> B[Validation + FK checks]
  B --> C[Supplier stats + inbound]
  C --> D[Inventory projection]
  D --> E[BOM propagation: planned and risk-adjusted]
  C --> F[Risk index + alerts]
  E --> G[Mitigation heuristic]
  E --> H[Scenario lab]
  G --> I[Strategist, exports, report]
  H --> I
  F --> I
@@@

## Run
@@@
pip install -r requirements.txt
python app.py
@@@
In Google Colab paste `app.py` into one cell. The `src/` modules in the brief are consolidated into `app.py`.

## Tests, docs, privacy
`pip install pytest && pytest tests` runs the built-in self-tests. See `docs/`. Optional LLM: set `ANTHROPIC_API_KEY` (see `.env.example`); off by default. Not included: supervised model, OR-Tools, PDF. Never commit real company data or keys. Add screenshots to `screenshots/`.
""".replace("@@@", "`" * 3)
TFILE = "from app import run_selftests\n\n\ndef test_%s():\n    res = [r for r in run_selftests(verbose=False) if r[0] in %s]\n    assert res and all(r[2] for r in res), res\n"
def _src():
    try: return open(__file__, encoding="utf-8").read()
    except Exception: pass
    try:
        for s in list(get_ipython().user_ns.get("In") or [])[::-1]:
            if "ORBIT AI — Supply Chain Risk" in s and "def main" in s: return s
    except Exception: pass
    return None
def write_samples():
    raw = get_demo_raw(); os.makedirs("sample_data", exist_ok=True); out = []
    for k, n in TN.items(): p = "sample_data/%s.csv" % n; raw[k].to_csv(p, index=False); out.append(p)
    return out
def build_project(files):
    root = "orbit-ai-supply-chain-resilience"
    for d in ["sample_data", "tests", "docs", "screenshots"]: os.makedirs(os.path.join(root, d), exist_ok=True)
    src = _src()
    if src: open(root + "/app.py", "w", encoding="utf-8").write(src)
    for f in files: open(os.path.join(root, f), "wb").write(open(f, "rb").read())
    dd = "All sample files are synthetic. Tables: suppliers, components (approved_supplier_ids separated by ';'), supplier_deliveries, inventory (weekly snapshots), production_orders (optional shortage_cost_per_day; priority 1 = highest), bills_of_materials, transportation, demand_history (weekly), mitigation_options (optional unit_cost_premium, purchase_order_id).\n"
    W = {"requirements.txt": "gradio>=4.44,<6\nplotly\nrequests\npandas\nnumpy\n", "README.md": README, "LICENSE": LICENSE, ".env.example": "# Optional. Leave empty to keep the external LLM disabled.\nANTHROPIC_API_KEY=\n", ".gitignore": ".env\n*.key\nsecrets*\n__pycache__/\n.ipynb_checkpoints/\n*.zip\norbit_*.csv\norbit_*.md\norbit_*.html\n",
         "docs/methodology.md": METH, "docs/data_dictionary.md": "# Data dictionary\n" + dd, "docs/risk_scoring.md": "# Risk scoring\nindex = 100 x sum(w_k f_k) / sum(w_k) over available factors: rel, vol, qual, openl, crit, sole. Descriptive, not a probability.\n",
         "docs/mitigation_optimization.md": "# Mitigation\nHeuristic: capacity, qualification and budget constraints; ranked by arrival before the shortage date, then cost per unit. Unmet quantity is reported as unresolved. Not OR-Tools.\n", "docs/responsible_ai.md": "# Responsible use\nDecision support only; nothing is executed. Scores use delivery data alone. Verify data quality before acting.\n",
         "docs/limitations.md": "# Limitations\nSynthetic data with planted disruptions; no live monitoring; indicators are not probabilities; heuristic mitigation; in-progress orders assumed to have issued material; stock pooled across warehouses.\n", "screenshots/README.md": "# Screenshots\nAdd your own screenshots here. None are included.\n"}
    for nm, g in [("data_validation", "validation"), ("supplier_analytics", "metrics"), ("inventory_analytics", "inventory"), ("risk_scoring", "risk"), ("production_impact", "production"), ("mitigation_engine", "mitigation"), ("scenario_simulator", "scenario"), ("reporting", "reporting")]: W["tests/test_%s.py" % nm] = TFILE % (nm, "('%s',)" % g)
    for fn, tx in W.items(): open(os.path.join(root, fn), "w", encoding="utf-8").write(tx)
    z = "orbit_ai_project.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for dp, _, fs in os.walk(root):
            for f in fs: zf.write(os.path.join(dp, f))
    return z, bool(src)

# ------------------------------ UI ------------------------------
CSS = """
.gradio-container{background:#14252D!important;color:#F1F5F4!important;font-family:Inter,system-ui,-apple-system,sans-serif!important;max-width:1380px!important}
.hdr{display:flex;justify-content:space-between;align-items:flex-end;flex-wrap:wrap;gap:14px;padding:26px 30px;border-radius:14px;background:#253842;border:1px solid #ffffff1a;border-left:4px solid #80E0C0;margin-bottom:12px}
.brand{display:flex;gap:16px;align-items:center}.logo{width:50px;height:50px;border-radius:50%;border:2px solid #80E0C0;color:#80E0C0;font-weight:800;font-size:20px;display:flex;align-items:center;justify-content:center}
.hdr h1{margin:0;font-size:30px;letter-spacing:3px;color:#F1F5F4}.hdr h1 span{color:#80E0C0}.hdr .sub{color:#D2B8FF;font-size:13px;letter-spacing:2px;text-transform:uppercase}.hdr p{margin:6px 0 0;color:#A5B6C0;font-size:15px;font-style:italic}
.badges span{display:inline-block;margin:3px;padding:4px 11px;border-radius:6px;background:#ffffff0d;border:1px solid #ffffff1a;color:#A5B6C0;font-size:12px}
.kg{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:10px 0}.kc{background:#253842;border:1px solid #ffffff14;border-radius:10px;padding:14px 16px}
.kl{color:#A5B6C0;font-size:11px;text-transform:uppercase;letter-spacing:1.2px}.kv{font-size:24px;font-weight:700;margin:6px 0 4px}.kd{color:#A5B6C0;font-size:12px}
.note{background:#253842;padding:10px 14px;border-radius:8px;margin:8px 0;color:#F1F5F4;font-size:14px;line-height:1.5}.sec{font-size:15px;font-weight:700;color:#D2B8FF;margin:18px 0 6px;text-transform:uppercase;letter-spacing:1px}
.pill{display:inline-block;border:1px solid;border-radius:99px;padding:1px 9px;font-size:11px;font-weight:600;margin:1px}.tw{overflow-x:auto;border-radius:8px;border:1px solid #ffffff14;margin:8px 0}table{border-collapse:collapse;width:100%;background:#253842;font-size:13px}
th{background:#2f4552;color:#80E0C0;text-align:left;padding:9px 10px;font-weight:600}td{padding:8px 10px;border-top:1px solid #ffffff10;color:#F1F5F4;vertical-align:top}tr:hover td{background:#80E0C00d}
button.primary{background:#80E0C0!important;color:#14252D!important;border:none!important;font-weight:700!important}@media(max-width:640px){.hdr h1{font-size:22px}.kv{font-size:20px}.hdr{padding:18px}}
"""
HEADER = ("<div class='hdr'><div class='brand'><div class='logo'>OB</div><div><h1>ORBIT <span>AI</span></h1><div class='sub'>Supply Chain Risk &amp; Resilience Intelligence</div><p>See the disruption before it hits production.</p></div></div>"
          "<div class='badges'><span>Indicators, not probabilities</span><span>Scenarios are hypothetical</span><span>Human approval required</span><span>No live feeds</span></div></div>")
SK = ["win", "tol", "dw", "w_rel", "w_vol", "w_qual", "w_openl", "w_crit", "w_sole"]
def mkP(*v):
    P = dict(DEF); d = dict(zip(SK, v)); P["w"] = {k[2:]: d.pop(k) for k in [x for x in SK if x.startswith("w_")]}; P.update(d); P["win"] = int(P["win"]); P["tol"] = int(P["tol"]); P["dw"] = int(P["dw"]); return P
def run_all(*a):
    n = len(SK)
    try:
        P = mkP(*a[:n]); files = a[n:n + 9]; mapping = a[n + 9]; demo = files[0] is None
        D = get_demo() if demo else load_all(dict(zip(TN.keys(), [read_csv_any(f) if f is not None else None for f in files])), mapping); X = build(D, P); keep = G.get("saved"); G.clear(); G.update(X=X, D=D, P=P, demo=demo)
        if keep: G["saved"] = keep
        k = px_kpi(X["PX"]["adj"]); return note(("Fictional demo data analysed. " if demo else "Your data analysed. ") + "%d suppliers, %d components, %d open production orders; %d exposed (risk-adjusted); %d alerts." % (len(D["sup"]), len(D["comp"]), k["n"], k["exposed"], len(X["alerts"])), "ok")
    except Exception as e: return note("Could not complete the analysis: " + esc(e), "err")
def refresh():
    if "X" not in G: return tuple(gr.update() for _ in range(11))
    X, D = G["X"], G["D"]; sc = [(s, s) for s in D["sup"].supplier_id]; cc = [(c, c) for c in D["comp"].component_id]; pc = [(p, p) for p in sorted(set(D["pr"].finished_product_id))]; sh = [(s, s) for s in X["ib"].ship.dropna().unique()]; no = [("(none)", "")]
    return (gr.update(choices=sc, value=[]), gr.update(choices=cc, value=[]), gr.update(choices=pc, value=[]), gr.update(choices=no + sc, value=""), gr.update(choices=no + sh, value=""), gr.update(choices=no + sc, value=""), gr.update(choices=[("All products", "")] + pc, value=""),
            gr.update(choices=no + sh, value=""), gr.update(choices=no + cc, value=""), gr.update(choices=no + cc, value=""), gr.update(choices=no + sh, value=""))
def build_ui(zip_path, sfiles):
    with gr.Blocks(css=CSS, title="ORBIT AI", theme=gr.themes.Base(primary_hue="teal", neutral_hue="slate")) as demo:
        gr.HTML(HEADER)
        with gr.Accordion("Settings (press Recalculate after changing)", open=False):
            with gr.Row():
                s1 = gr.Slider(30, 180, 90, step=15, label="Recent window for supplier trends (days)"); s2 = gr.Slider(0, 5, 0, step=1, label="On-time tolerance (days late)"); s3 = gr.Slider(4, 16, 8, step=1, label="Demand averaging window (weeks)")
            gr.Markdown("**Risk-index weights** (normalised automatically)")
            with gr.Row():
                w1 = gr.Slider(0, 1, .25, step=.05, label="Reliability"); w2 = gr.Slider(0, 1, .15, step=.05, label="Volatility"); w3 = gr.Slider(0, 1, .15, step=.05, label="Quality and fill"); w4 = gr.Slider(0, 1, .15, step=.05, label="Open delays"); w5 = gr.Slider(0, 1, .15, step=.05, label="Critical exposure"); w6 = gr.Slider(0, 1, .15, step=.05, label="Sole-source exposure")
            run_btn = gr.Button("Recalculate", variant="primary")
        with gr.Accordion("Filters (supplier, component, product, history dates; apply to every page)", open=True):
            with gr.Row():
                f_s = gr.Dropdown([], multiselect=True, label="Supplier"); f_c = gr.Dropdown([], multiselect=True, label="Component"); f_p = gr.Dropdown([], multiselect=True, label="Product"); f_d1 = gr.Textbox(label="History from (YYYY-MM-DD)"); f_d2 = gr.Textbox(label="History to (YYYY-MM-DD)"); ap_btn = gr.Button("Apply filters", variant="primary")
        status = gr.HTML(note("Loading the fictional demo supply chain and running self-tests (about 30-60 seconds)...", "info")); FIN = [f_s, f_c, f_p, f_d1, f_d2]
        with gr.Tabs():
            with gr.Tab("01 Control Tower"):
                ct_h = gr.HTML()
                with gr.Row():
                    ct1 = gr.Plot(); ct2 = gr.Plot()
                ct3 = gr.Plot()
            with gr.Tab("02 Supplier Intelligence"):
                su_h = gr.HTML()
                with gr.Row():
                    su1 = gr.Plot(); su2 = gr.Plot()
                su3 = gr.Plot()
            with gr.Tab("03 Inventory Radar"):
                iv_h = gr.HTML()
                with gr.Row():
                    iv1 = gr.Plot(); iv2 = gr.Plot()
                iv3 = gr.Plot()
            with gr.Tab("04 Production Impact"):
                pi_h = gr.HTML()
                with gr.Row():
                    pi1 = gr.Plot(); pi2 = gr.Plot()
            with gr.Tab("05 Logistics Monitor"):
                lg_h = gr.HTML()
                with gr.Row():
                    lg1 = gr.Plot(); lg2 = gr.Plot()
            with gr.Tab("06 Risk Intelligence"):
                rk_h = gr.HTML()
                with gr.Row():
                    rk1 = gr.Plot(); rk2 = gr.Plot()
            with gr.Tab("07 Mitigation Studio"):
                with gr.Row():
                    mt_mode = gr.Radio(["Risk-adjusted arrivals", "Planned dates"], value="Risk-adjusted arrivals", label="Planning basis"); mt_allow = gr.Checkbox(False, label="Also consider suppliers that still need qualification (labelled)"); mt_bud = gr.Number(0, label="Budget cap (0 = none)"); mt_btn = gr.Button("Build mitigation plan", variant="primary")
                mt_h = gr.HTML(); mt_f = gr.Plot()
            with gr.Tab("08 Scenario Lab"):
                gr.Markdown("Change assumptions and run. Results are **hypothetical** and recalculated through the BOM with the same no-double-counting allocation. Leave all levers empty to see the baseline.")
                with gr.Row():
                    sc_mode = gr.Radio(["Risk-adjusted arrivals", "Planned dates"], value="Risk-adjusted arrivals", label="Arrival basis"); sc_seq = gr.Radio(["Priority order", "Customer due date first"], value="Priority order", label="Production sequencing"); sc_wm = gr.Checkbox(False, label="Also build the mitigation plan for the scenario")
                with gr.Row():
                    sc_dsup = gr.Dropdown([], label="Delay all open POs of supplier"); sc_dship = gr.Dropdown([], label="...or delay one shipment"); sc_dd = gr.Slider(0, 30, 7, step=1, label="Delay (days)"); sc_fail = gr.Dropdown([], label="Supplier fails to deliver")
                with gr.Row():
                    sc_dp = gr.Slider(0, 100, 0, step=5, label="Demand increase (%)"); sc_dprod = gr.Dropdown([], label="Demand increase applies to"); sc_drop = gr.Dropdown([], label="Shipment becomes unavailable"); sc_df = gr.Slider(0, 30, 0, step=1, label="Loss rate rise on inbound (%)"); sc_dcp = gr.Dropdown([], label="...for component")
                with gr.Row():
                    sc_xc = gr.Dropdown([], label="Add supply for component (alternate supplier / safety stock)"); sc_xq = gr.Number(0, label="Quantity"); sc_xd = gr.Slider(0, 30, 7, step=1, label="Arrives in (days)"); sc_es = gr.Dropdown([], label="Expedite shipment"); sc_ed = gr.Slider(1, 14, 3, step=1, label="Expedited arrival (days)")
                with gr.Row():
                    sc_btn = gr.Button("Run scenario", variant="primary"); sv_btn = gr.Button("Save this scenario for comparison (session only)")
                sc_h = gr.HTML(); sc_f = gr.Plot(); sv_h = gr.HTML()
            with gr.Tab("09 Reports & Data"):
                gr.Markdown("Upload CSVs (suppliers, components, deliveries, inventory, production orders and BOM required; transportation, demand history and mitigation options optional). Leave empty for the fictional demo. Raw uploads are never modified; a validated copy is analysed.")
                up = []
                for i in range(0, 9, 3):
                    with gr.Row():
                        for k in list(TN)[i:i + 3]: up.append(gr.File(label=TN[k] + ".csv" + (" (optional)" if k in ("tr", "dem", "mit") else ""), file_types=[".csv"]))
                mp = gr.Textbox(label="Column mapping (only if auto-detect fails)", placeholder="supplier_id=vendor, expected_arrival=eta", lines=2); ld_btn = gr.Button("Validate and load uploaded data", variant="primary")
                gr.File(value=sfiles, label="Sample CSV templates (synthetic)", file_count="multiple", interactive=False); dq_h = gr.HTML(); t_h = gr.HTML()
                gr.Markdown("### Exports"); xp_btn = gr.Button("Generate exports and executive report", variant="primary"); xp_msg = gr.HTML(); xp_files = gr.File(label="Exports", file_count="multiple", interactive=False); gr.File(value=zip_path, label="Download GitHub-ready project (ZIP)", interactive=False)
            with gr.Tab("10 Methodology & Trust"):
                gr.Markdown(METH)
            with gr.Tab("ORBIT Strategist"):
                gr.Markdown("Answers come from analytical tools over the current data. Try: *Which supplier poses the greatest immediate production risk?* · *Which components could stop production next week?* · *What happens if shipment SH0100 is delayed by 7 days?* · *Should we expedite or use an alternate supplier for C017?* · *Which components are single-source?* · *What is the lowest-cost feasible mitigation plan?* · *Which customer deliveries are most exposed?*")
                ag_q = gr.Textbox(label="Ask a question"); ag_llm = gr.Checkbox(False, label="Use external LLM (off by default; sends only aggregated results; needs ANTHROPIC_API_KEY in the environment; check your data policy first)"); ag_btn = gr.Button("Ask", variant="primary"); ag_out = gr.Markdown()
        SETIN = [s1, s2, s3, w1, w2, w3, w4, w5, w6]; RUN = SETIN + up + [mp]; MIT_IN = [mt_mode, mt_allow, mt_bud]
        SCN_IN = [sc_mode, sc_dsup, sc_dd, sc_dship, sc_fail, sc_dp, sc_dprod, sc_drop, sc_df, sc_dcp, sc_xc, sc_xq, sc_xd, sc_es, sc_ed, sc_seq, sc_wm]; REF_OUT = [f_s, f_c, f_p, sc_dsup, sc_dship, sc_fail, sc_dprod, sc_drop, sc_dcp, sc_xc, sc_es]
        def pages(e):
            e = e.then(render_ct, FIN, [ct_h, ct1, ct2, ct3]).then(render_sup, FIN, [su_h, su1, su2, su3]).then(render_inv, FIN, [iv_h, iv1, iv2, iv3]).then(render_prod, FIN, [pi_h, pi1, pi2]).then(render_log, FIN, [lg_h, lg1, lg2])
            return e.then(render_risk, FIN, [rk_h, rk1, rk2]).then(render_mit, FIN + MIT_IN, [mt_h, mt_f]).then(render_scn, SCN_IN, [sc_h, sc_f]).then(render_dq, None, [dq_h, t_h])
        def full(ev): return pages(ev.then(refresh, None, REF_OUT))
        full(run_btn.click(run_all, RUN, [status], show_progress="full")); full(ld_btn.click(run_all, RUN, [status], show_progress="full")); full(demo.load(run_all, RUN, [status]))
        ap_btn.click(render_ct, FIN, [ct_h, ct1, ct2, ct3]).then(render_sup, FIN, [su_h, su1, su2, su3]).then(render_inv, FIN, [iv_h, iv1, iv2, iv3]).then(render_prod, FIN, [pi_h, pi1, pi2]).then(render_log, FIN, [lg_h, lg1, lg2]).then(render_risk, FIN, [rk_h, rk1, rk2]).then(render_mit, FIN + MIT_IN, [mt_h, mt_f])
        mt_btn.click(render_mit, FIN + MIT_IN, [mt_h, mt_f], show_progress="full"); sc_btn.click(render_scn, SCN_IN, [sc_h, sc_f], show_progress="full"); sv_btn.click(save_scn, None, sv_h); xp_btn.click(export_all, None, [xp_files, xp_msg], show_progress="full")
        ag_btn.click(ask, [ag_q, ag_llm], ag_out, show_progress="full"); ag_q.submit(ask, [ag_q, ag_llm], ag_out)
    return demo
def main():
    get_demo(); sf = write_samples(); zp, saved = build_project(sf)
    print("=" * 78); print("ORBIT AI starting. Demo data is FICTIONAL with planted disruptions. Core analytics need no API key."); print("Running self-tests (about 30-60 seconds):")
    run_selftests(verbose=True); demo = build_ui(zp, sf)
    print("Project ZIP:", zp, "| standalone app.py included:", "yes" if saved else "NO (create app.py yourself by pasting this cell into it)")
    print("Not included / not tested: supervised disruption model, OR-Tools, PDF export, uploads of your own CSVs, the optional LLM. The public Gradio link is open to anyone: do not load confidential data unless access is restricted.")
    print("=" * 78); demo.queue().launch(debug=False, show_error=True)
if __name__ == "__main__" or "google.colab" in sys.modules:
    main()