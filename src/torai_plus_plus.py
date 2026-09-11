"""
TORAI++ v3 : fast, cached, conditional re-ranking.

Key fix: parse each case's traces.csv ONCE, cache the call graph,
then sweep hyperparameters on the cache. Reduces 3600 parses to 60.
"""
import os, json, glob, argparse, time
from collections import defaultdict
import pandas as pd


# ----------------------------------------------------------------------
# FAST call graph: vectorized, no iterrows
# ----------------------------------------------------------------------
def build_call_graph_fast(traces_path):
    if not os.path.exists(traces_path):
        return {}, {}
    try:
        t = pd.read_csv(
            traces_path,
            usecols=lambda c: c in {"serviceName", "spanID", "parentSpanID"},
            dtype={"spanID": str, "parentSpanID": str, "serviceName": str},
        )
    except Exception:
        return {}, {}

    if not {"serviceName", "spanID", "parentSpanID"}.issubset(t.columns):
        return {}, {}

    # Drop rows with no parent
    t = t.dropna(subset=["parentSpanID", "serviceName"])
    t = t[t["parentSpanID"] != ""]

    # Map spanID -> serviceName (vectorized)
    span_to_svc = dict(zip(t["spanID"], t["serviceName"]))

    # Vectorized parent lookup
    t = t.copy()
    t["parent_service"] = t["parentSpanID"].map(span_to_svc)

    # Drop unresolved parents and self-calls
    t = t.dropna(subset=["parent_service"])
    t = t[t["parent_service"] != t["serviceName"]]

    # Group once
    edges = t[["parent_service", "serviceName"]].drop_duplicates()

    callers, callees = defaultdict(set), defaultdict(set)
    for parent, child in edges.itertuples(index=False, name=None):
        callees[parent].add(child)
        callers[child].add(parent)

    return dict(callers), dict(callees)


# ----------------------------------------------------------------------
# Cached case loader: parse traces ONCE, keep call graph in memory
# ----------------------------------------------------------------------
def load_cases(data_root, results_root):
    """
    Returns list of dicts:
      {
        service, system, torai_top5, callers, callees
      }
    Parses each traces.csv exactly once.
    """
    result_files = sorted(glob.glob(os.path.join(results_root, "*.json")))
    print(f"Loading {len(result_files)} cases...")

    cases = []
    t0 = time.time()
    for i, rf in enumerate(result_files):
        fname = os.path.basename(rf)
        service, rest = parse_filename(fname)
        with open(rf) as f:
            data = json.load(f)
        top5 = [strip_suffix(p) for p in data.get("0", [])]
        if not top5:
            continue

        parts = rest.rsplit("_", 1)
        if len(parts) != 2:
            continue
        fault, case = parts

        cands = glob.glob(os.path.join(data_root, "*", f"{service}_{fault}", case))
        traces_path = os.path.join(cands[0], "traces.csv") if cands else None
        callers, callees = build_call_graph_fast(traces_path) if traces_path else ({}, {})

        system = "RE3-TT" if service.startswith("ts-") else "RE3-OB"
        cases.append({
            "service": service,
            "system": system,
            "torai_top5": top5,
            "callers": callers,
            "callees": callees,
        })

        if (i + 1) % 10 == 0:
            print(f"  loaded {i+1}/{len(result_files)}  "
                  f"({time.time()-t0:.1f}s)")

    print(f"Loaded {len(cases)} cases in {time.time()-t0:.1f}s")
    return cases


# ----------------------------------------------------------------------
# Scoring + reranking (operates on cached cases)
# ----------------------------------------------------------------------
def score_candidates(topk, callers, callees, topk_window=5,
                     min_anomalous_callees=2):
    scores = {}
    topk_set = set(topk[:topk_window])
    for svc in topk:
        cal = callees.get(svc, set())
        n_callees = len(cal)
        n_callers = len(callers.get(svc, set()))
        anomalous = cal & topk_set
        n_anom = len(anomalous)
        if n_anom < min_anomalous_callees or n_callees == 0:
            scores[svc] = 0.0
            continue
        agg = n_anom / n_callees
        entry = 1.0 if n_callers == 0 else 1.0 / (n_callers + 1)
        scores[svc] = 0.6 * agg + 0.4 * entry
    return scores


def rerank(topk, victim_scores, penalty, thresh):
    adjusted = []
    for i, svc in enumerate(topk):
        v = victim_scores.get(svc, 0.0)
        eff = v if v >= thresh else 0.0
        adjusted.append((svc, i + penalty * eff))
    adjusted.sort(key=lambda x: x[1])
    return [s for s, _ in adjusted]


# ----------------------------------------------------------------------
# Evaluation on cached cases (fast)
# ----------------------------------------------------------------------
def evaluate_cached(cases, penalty, thresh, min_anom, topk_window=5):
    by_system = defaultdict(lambda: {"n": 0, "r1": 0, "r3": 0, "r5": 0})
    overall = {"n": 0, "r1": 0, "r3": 0, "r5": 0}

    for c in cases:
        topk = c["torai_top5"]
        vs = score_candidates(topk, c["callers"], c["callees"],
                              topk_window=topk_window,
                              min_anomalous_callees=min_anom)
        reranked = rerank(topk, vs, penalty, thresh)
        rank = next((i + 1 for i, p in enumerate(reranked[:5]) if p == c["service"]), None)

        overall["n"] += 1
        by_system[c["system"]]["n"] += 1
        if rank == 1:
            overall["r1"] += 1; by_system[c["system"]]["r1"] += 1
        if rank is not None and rank <= 3:
            overall["r3"] += 1; by_system[c["system"]]["r3"] += 1
        if rank is not None and rank <= 5:
            overall["r5"] += 1; by_system[c["system"]]["r5"] += 1

    return overall, by_system


# ----------------------------------------------------------------------
# Filename helpers
# ----------------------------------------------------------------------
def parse_filename(fname):
    base = fname.replace(".json", "")
    if base.startswith("ts-auth-service_"):
        return "ts-auth-service", base[len("ts-auth-service_"):]
    if base.startswith("ts-route-service_"):
        return "ts-route-service", base[len("ts-route-service_"):]
    if base.startswith("ts-"):
        p = base.split("_")
        return p[0], "_".join(p[1:])
    return base.split("_", 1)


def strip_suffix(p):
    return p.rsplit("_", 1)[0] if "_" in p else p


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", default="data/RE3")
    ap.add_argument("--results-root", default="output/results")
    args = ap.parse_args()

    cases = load_cases(args.data_root, args.results_root)
    print()

    print(f"{'penalty':>8} {'thresh':>8} {'minAnom':>8}  |  "
          f"{'OB AC@1':>8} {'TT AC@1':>8} {'All AC@1':>9}")
    print("-" * 72)

    best = None
    for penalty in [0.5, 1.0, 2.0, 3.0, 5.0]:
        for thresh in [0.0, 0.3, 0.5, 0.7]:
            for min_anom in [1, 2, 3]:
                overall, by_system = evaluate_cached(
                    cases, penalty, thresh, min_anom
                )
                n = overall["n"]
                ac1 = overall["r1"] / n if n else 0
                ob = by_system.get("RE3-OB", {"n": 1, "r1": 0})
                tt = by_system.get("RE3-TT", {"n": 1, "r1": 0})
                ob_ac1 = ob["r1"] / ob["n"] if ob["n"] else 0
                tt_ac1 = tt["r1"] / tt["n"] if tt["n"] else 0

                if best is None or ac1 > best["ac1"]:
                    best = {"penalty": penalty, "thresh": thresh,
                            "min_anom": min_anom,
                            "ac1": ac1, "ob_ac1": ob_ac1, "tt_ac1": tt_ac1}

                print(f"{penalty:>8.2f} {thresh:>8.2f} {min_anom:>8}  |  "
                      f"{ob_ac1:>8.2f} {tt_ac1:>8.2f} {ac1:>9.2f}")

    print()
    print("=" * 60)
    print("BEST CONFIGURATION")
    print("=" * 60)
    print(json.dumps(best, indent=2))
