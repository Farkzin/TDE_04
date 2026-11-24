"""Single entry point for the Delivery and Logistics workflow (ST4 + ST5).

    python run_pipeline.py                       # full run: local batch + weather API (auto mode)
    python run_pipeline.py --source-mode cache   # same, using the saved API response (offline)
    python run_pipeline.py --st4-only            # only the ST4 batch, workbook and report
    python run_pipeline.py --status              # latest successful run and recent history

Exit code 0 = SUCCESS (results in outputs/runs/<run_id>), 1 = FAILED (nothing published).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from delivery_pipeline import runlog  # noqa: E402
from delivery_pipeline.config import ProjectPaths  # noqa: E402
from delivery_pipeline.errors import PipelineError  # noqa: E402
from delivery_pipeline.workflow import run_workflow  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Delivery batch + weather integration workflow")
    parser.add_argument("--input-dir", type=Path, help="folder with deliveries_*.csv (default: data/raw)")
    parser.add_argument("--source-mode", choices=["auto", "live", "cache"], default="auto",
                        help="weather source: live API, saved response, or live with cache fallback (default)")
    parser.add_argument("--st4-only", action="store_true", help="run only the ST4 batch stages")
    parser.add_argument("--status", action="store_true", help="show the latest successful run and exit")
    return parser.parse_args()


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    paths = ProjectPaths.default()
    if args.input_dir:
        paths = ProjectPaths(args.input_dir.resolve(), paths.output_root, paths.external_dir, paths.logs_dir)
    if args.status:
        print(runlog.read_status(paths.output_root))
        return 0
    try:
        folder = run_workflow(paths, source_mode=args.source_mode, st4_only=args.st4_only)
    except PipelineError as error:
        print(f"\nRUN FAILED - {type(error).__name__}: {error}\nNothing was published; see outputs/run_history.csv")
        return 1
    print(f"\nRUN SUCCESS - results in {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
