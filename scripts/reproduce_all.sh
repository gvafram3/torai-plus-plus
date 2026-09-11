#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${DATA_ROOT:-data/RE3}"
RESULTS_ROOT="${RESULTS_ROOT:-output/results}"
SRC_DIR="${SRC_DIR:-src}"

echo "==> 1. Reconstruct missing TORAI preprocessing on RE3"
python "${SRC_DIR}/convert_re3_to_torai_format.py" --data-dir "${DATA_ROOT}/RE3-OB"
python "${SRC_DIR}/convert_re3_to_torai_format.py" --data-dir "${DATA_ROOT}/RE3-TT"

echo "==> 2. Run TORAI baseline"
python main.py --method torai --dataset re3-ob --length 10
python main.py --method torai --dataset re3-tt --length 10

echo "==> 3. Run TORAI++ re-ranker"
python "${SRC_DIR}/torai_plus_plus.py" --data-root "${DATA_ROOT}" --results-root "${RESULTS_ROOT}"

echo "==> Done."
