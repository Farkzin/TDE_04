"""Run management: unique run id, log file, staging area, atomic publication and run history.

Layout under outputs/:
    runs/<run_id>/          completed (published) runs - never overwritten
    _incomplete/<run_id>/   staging while a run is in progress
    _failed/<run_id>/       partial files of failed runs, kept apart from completed results
    LATEST_SUCCESSFUL_RUN.txt, run_history.csv
"""

import csv
import logging
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

HISTORY_FIELDS = ["run_id", "started_at", "finished_at", "status", "source_mode", "input_files",
                  "valid_deliveries", "output_folder", "message"]


@dataclass
class RunContext:
    run_id: str
    started_at: datetime
    output_root: Path
    staging_dir: Path
    log_file: Path
    logger: logging.Logger
    source_mode: str = "n/a"
    input_files: list[str] = field(default_factory=list)
    valid_deliveries: int | None = None


def start_run(output_root: Path, logs_dir: Path) -> RunContext:
    started = datetime.now().astimezone()
    run_id = f"{started:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    staging = output_root / "_incomplete" / run_id
    staging.mkdir(parents=True, exist_ok=False)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"run_{run_id}.log"

    logger = logging.getLogger(f"delivery_pipeline.{run_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in (logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()):
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    logger.info("RUN %s STARTED", run_id)
    return RunContext(run_id, started, output_root, staging, log_file, logger)


def _append_history(ctx: RunContext, status: str, folder: Path | None, message: str) -> None:
    history = ctx.output_root / "run_history.csv"
    new_file = not history.exists()
    with history.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=HISTORY_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({
            "run_id": ctx.run_id,
            "started_at": ctx.started_at.isoformat(timespec="seconds"),
            "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": status,
            "source_mode": ctx.source_mode,
            "input_files": ";".join(ctx.input_files),
            "valid_deliveries": "" if ctx.valid_deliveries is None else ctx.valid_deliveries,
            "output_folder": "" if folder is None else folder.relative_to(ctx.output_root).as_posix(),
            "message": message.replace("\n", " ")[:300],
        })


def _close(ctx: RunContext) -> None:
    for handler in list(ctx.logger.handlers):
        handler.close()
        ctx.logger.removeHandler(handler)


def publish_run(ctx: RunContext) -> Path:
    """Move the complete staging folder to runs/ in one rename, then update the pointers."""
    final_dir = ctx.output_root / "runs" / ctx.run_id
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    ctx.logger.info("RUN %s SUCCESS -> %s", ctx.run_id, final_dir)
    _close(ctx)
    shutil.copy2(ctx.log_file, ctx.staging_dir / ctx.log_file.name)
    ctx.staging_dir.rename(final_dir)
    (ctx.output_root / "LATEST_SUCCESSFUL_RUN.txt").write_text(
        f"{ctx.run_id}\nfolder: runs/{ctx.run_id}\nsource_mode: {ctx.source_mode}\n"
        f"finished_at: {datetime.now().astimezone().isoformat(timespec='seconds')}\n", encoding="utf-8")
    _append_history(ctx, "SUCCESS", final_dir, "all stages completed and verified")
    return final_dir


def fail_run(ctx: RunContext, error: Exception) -> Path:
    """Keep partial files in _failed/ (never in runs/) and leave earlier successful runs untouched."""
    ctx.logger.error("RUN %s FAILED: %s: %s", ctx.run_id, type(error).__name__, error)
    ctx.logger.error("Nothing was published. Latest successful run is unchanged.")
    _close(ctx)
    failed_dir = ctx.output_root / "_failed" / ctx.run_id
    failed_dir.parent.mkdir(parents=True, exist_ok=True)
    (ctx.staging_dir / "ERROR.txt").write_text(f"{type(error).__name__}: {error}\n", encoding="utf-8")
    shutil.copy2(ctx.log_file, ctx.staging_dir / ctx.log_file.name)
    ctx.staging_dir.rename(failed_dir)
    _append_history(ctx, "FAILED", failed_dir, f"{type(error).__name__}: {error}")
    return failed_dir


def read_status(output_root: Path, last: int = 5) -> str:
    latest = output_root / "LATEST_SUCCESSFUL_RUN.txt"
    lines = ["Latest successful run:", latest.read_text(encoding="utf-8").strip() if latest.exists() else "  (none)"]
    history = output_root / "run_history.csv"
    if history.exists():
        with history.open(encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))[-last:]
        lines.append(f"\nLast {len(rows)} runs (newest last):")
        for r in rows:
            lines.append(f"  {r['run_id']}  {r['status']:<7}  mode={r['source_mode']:<5}  "
                         f"valid={r['valid_deliveries'] or '-':<4}  {r['message'][:90]}")
    return "\n".join(lines)
