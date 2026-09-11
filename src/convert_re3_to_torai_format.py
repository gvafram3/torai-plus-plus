"""
Reconstruct the missing TORAI preprocessing.

Converts raw RE3 logs.csv / traces.csv into the format the authors'
torai-OB dataset uses:
  - logts.csv       : log-template counts per service per 15s window (via Drain)
  - tracets_err.csv : error counts per service+method per 15s window
  - tracets_lat.csv : mean latency per service+method per 15s window

This is Contribution 2 of the paper: reconstructing the missing
conversion step that the authors never published.
"""
import os
import sys
import pandas as pd
import numpy as np
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig


def build_drain_miner():
    """Build a Drain template miner for log parsing."""
    config = TemplateMinerConfig()
    config.drain_sim_th = 0.4
    config.drain_depth = 4
    config.drain_max_children = 100
    config.drain_max_clusters = None
    return TemplateMiner(config=config)


def convert_logs_to_logts(logs_path, out_path, window_seconds=15):
    """Convert raw logs.csv -> logts.csv (log-template counts per service per window)."""
    print(f"  [logts] reading {logs_path}")
    logs = pd.read_csv(logs_path)
    if logs.shape[0] == 0:
        pd.DataFrame({"time": []}).to_csv(out_path, index=False)
        return

    # Time: use the 'timestamp' column if present, else 'time'
    if "timestamp" in logs.columns:
        logs["ts_unix"] = pd.to_numeric(logs["timestamp"], errors="coerce") / 1e9
    else:
        logs["ts_unix"] = pd.to_numeric(logs["time"], errors="coerce")
    logs = logs.dropna(subset=["ts_unix"])

    if logs.shape[0] == 0:
        pd.DataFrame({"time": []}).to_csv(out_path, index=False)
        return

    # Parse each message with Drain; build a (service, template_id) column
    miner = build_drain_miner()
    template_ids = []
    for msg in logs["message"].astype(str).tolist():
        result = miner.add_log_message(msg)
        template_ids.append(result["cluster_id"])
    logs["template_id"] = template_ids

    # Column name = {container_name}_{template_id}
    logs["col"] = logs["container_name"].astype(str) + "_" + logs["template_id"].astype(str)

    # Bin time into window_seconds
    t0 = logs["ts_unix"].min()
    logs["window"] = ((logs["ts_unix"] - t0) // window_seconds).astype(int)
    logs["time"] = (t0 + logs["window"] * window_seconds).astype(int)

    # Pivot: rows = window, cols = (service, template), values = count
    counts = logs.groupby(["time", "col"]).size().unstack(fill_value=0)
    counts = counts.sort_index()
    counts.to_csv(out_path, index=True, index_label="time")
    print(f"  [logts] wrote {out_path}  shape={counts.shape}")


def convert_traces_to_tracets(traces_path, err_path, lat_path, window_seconds=15):
    """Convert raw traces.csv -> tracets_err.csv + tracets_lat.csv."""
    print(f"  [tracets] reading {traces_path}")
    traces = pd.read_csv(traces_path)
    if traces.shape[0] == 0:
        pd.DataFrame({"time": []}).to_csv(err_path, index=False)
        pd.DataFrame({"time": []}).to_csv(lat_path, index=False)
        return

    # Time: use startTimeMillis (ms) if present, else 'time'
    if "startTimeMillis" in traces.columns:
        traces["ts_unix"] = pd.to_numeric(traces["startTimeMillis"], errors="coerce") / 1000.0
    else:
        traces["ts_unix"] = pd.to_numeric(traces["time"], errors="coerce")
    traces = traces.dropna(subset=["ts_unix"])

    if traces.shape[0] == 0:
        pd.DataFrame({"time": []}).to_csv(err_path, index=False)
        pd.DataFrame({"time": []}).to_csv(lat_path, index=False)
        return

    # Column name = {serviceName}_{methodName|operationName|"unknown"}
    def colname(row):
        svc = str(row.get("serviceName", "unknown"))
        meth = row.get("methodName")
        if pd.isna(meth) or meth == "":
            op = row.get("operationName")
            if pd.isna(op) or op == "":
                meth = "unknown"
            else:
                meth = str(op).split("/")[-1]
        return f"{svc}_{meth}"

    traces["col"] = traces.apply(colname, axis=1)

    # Bin time into window_seconds
    t0 = traces["ts_unix"].min()
    traces["window"] = ((traces["ts_unix"] - t0) // window_seconds).astype(int)
    traces["time"] = (t0 + traces["window"] * window_seconds).astype(int)

    # Errors: statusCode != 0 (or != "" depending on format)
    if "statusCode" in traces.columns:
        traces["is_err"] = pd.to_numeric(traces["statusCode"], errors="coerce").fillna(0) != 0
    else:
        traces["is_err"] = False

    err_counts = traces.groupby(["time", "col"])["is_err"].sum().unstack(fill_value=0)
    err_counts = err_counts.sort_index()
    err_counts.to_csv(err_path, index=True, index_label="time")
    print(f"  [tracets_err] wrote {err_path}  shape={err_counts.shape}")

    # Latency: mean of 'duration' column
    if "duration" in traces.columns:
        traces["duration_s"] = pd.to_numeric(traces["duration"], errors="coerce")
        lat = traces.groupby(["time", "col"])["duration_s"].mean().unstack(fill_value=0)
    else:
        lat = traces.groupby(["time", "col"]).size().unstack(fill_value=0) * 0
    lat = lat.sort_index()
    lat.to_csv(lat_path, index=True, index_label="time")
    print(f"  [tracets_lat] wrote {lat_path}  shape={lat.shape}")


def convert_case(case_dir, window_seconds=15):
    """Convert one RE3 case directory in place."""
    logs_path = os.path.join(case_dir, "logs.csv")
    traces_path = os.path.join(case_dir, "traces.csv")

    if os.path.exists(logs_path):
        try:
            convert_logs_to_logts(logs_path, os.path.join(case_dir, "logts.csv"), window_seconds)
        except Exception as e:
            print(f"  [logts] FAILED: {e}")
    else:
        print(f"  [logts] no logs.csv")

    if os.path.exists(traces_path):
        try:
            convert_traces_to_tracets(
                traces_path,
                os.path.join(case_dir, "tracets_err.csv"),
                os.path.join(case_dir, "tracets_lat.csv"),
                window_seconds,
            )
        except Exception as e:
            print(f"  [tracets] FAILED: {e}")
    else:
        print(f"  [tracets] no traces.csv")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True, help="Root dir containing RE3 cases")
    parser.add_argument("--window-seconds", type=int, default=15)
    args = parser.parse_args()

    case_dirs = []
    for root, dirs, files in os.walk(args.data_dir):
        if "metrics.csv" in files:
            case_dirs.append(root)
    print(f"Found {len(case_dirs)} cases in {args.data_dir}")

    for i, case_dir in enumerate(sorted(case_dirs)):
        print(f"[{i+1}/{len(case_dirs)}] {case_dir}")
        convert_case(case_dir, args.window_seconds)


if __name__ == "__main__":
    main()
