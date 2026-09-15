#!/usr/bin/env bash
set -euo pipefail
python -m py_compile app.py database.py logic.py mobile_api.py export_utils.py scorer_seeds.py ui.py
for t in \
  tests/mobile_api_smoke.py \
  tests/big_patch_smoke.py \
  tests/swiss_smoke.py \
  tests/de9_de10_smoke.py \
  tests/smart_scheduler_smoke.py \
  tests/versioning_alias_smoke.py \
  tests/visible_draw_policy_smoke.py \
  tests/de456_draw_smoke.py \
  tests/wheel_shrink_smoke.py
do
  echo "=== $t ==="
  python "$t"
done
