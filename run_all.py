"""One command for the whole evaluation.

  python run_all.py --offline    rescore everything from the stored answers and run the tests (no model calls)
  python run_all.py              rebuild the items (needs the source projects and datasets), send every stage
                                 that is not finished yet, then rescore. Finished requests are never sent again.

The model stages read the API key from the file named by EVAL_ENV_FILE (see .env.example) and use the
Message Batches API. Stages: items -> flips -> dev -> adopt -> main, perturb, pair, list, qc -> (second judge: eval/second.py, run separately) -> score -> tables -> number check.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = [sys.executable, "-X", "utf8"]


def step(*args: str) -> None:
    print("\n$", " ".join(args), flush=True)
    r = subprocess.run([*PY, *args], cwd=ROOT)
    if r.returncode:
        raise SystemExit(r.returncode)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    if not a.offline:
        if (ROOT.parent / "ad-review-agent").exists() or os.environ.get("JC_SOURCES"):
            step("eval/build_items.py")
            step("eval/qc.py", "build")
        else:
            print("source projects not found: using the item files as they are")
        step("eval/gen_flips.py")
        step("eval/run.py", "dev")
        step("eval/score.py", "adopt")
        for s in ("main", "perturb", "pair", "list"):
            step("eval/run.py", s)
        step("eval/qc.py", "run")
    step("eval/freeze.py", "--check")
    step("eval/key_issues.py")
    step("eval/score.py")
    step("eval/report_tables.py")
    step("tools/check_numbers.py")
    step("-m", "unittest", "discover", "-s", "tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
