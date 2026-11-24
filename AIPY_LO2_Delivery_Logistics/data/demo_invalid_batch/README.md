# Demo: rejected batch

`deliveries_2026-10-12_to_2026-10-18.csv` in this folder has no `package_weight_kg` column.
Running

```powershell
python run_pipeline.py --input-dir data/demo_invalid_batch
```

must stop the whole batch with rule **V1**, publish nothing in `outputs/runs/`, keep the partial files in
`outputs/_failed/<run_id>/` and leave `outputs/LATEST_SUCCESSFUL_RUN.txt` unchanged.
