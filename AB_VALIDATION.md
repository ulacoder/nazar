# NAZAR Actions V1/V2 shadow A/B validation

This mode is disabled by default. Enable it with `NAZAR_ACTIONS_AB_ENABLED=true`; V1 remains the production action model and is the only source used by temporal state, events, and analytics.

## Models

- V1: `models/actions_v4_epoch_1.pt`, `models/actions_v2_reference_config.json`; thresholds READING 0.39 and WRITING 0.41.
- V2: `C:\Users\Abik\Projects\yolo-pose-demo\experiments\nazar_actions_v2_real\nazar_actions_v2_real.pt`, sibling `config.json`; thresholds READING/WRITING 0.50.

The pipeline creates each person crop once, passes the same crop list to V1 and V2, and keeps V2 scores in the diagnostic `actions_ab` field only. Pose and tracking execute once per AI frame.

## Outputs

With a running session, rows are written asynchronously to `data/ab_tests/<session_id>_actions_ab.csv`. Sparse disagreement person crops and `disagreements.csv` are written below `data/ab_tests/<session_id>/disagreements/`; the same track/class/prediction disagreement is limited to one crop per two seconds. `/api/actions-ab` and the live SHADOW / EXPERIMENTAL panel expose per-session model agreement counts, positive counts, average probabilities, and compared tracks.

## Performance sample

On the configured RTX 5060 Laptop GPU, a warm batch of two 224x224 crops measured V1 8.77–17.04 ms and V2 8.63–14.31 ms (three samples; total V1+V2 17.40–31.35 ms). This is the action-model overhead; integrated pose/head/total AI latency and AI FPS are recorded in every A/B CSV row and shown by `/api/status`.

## Launch

```powershell
$env:NAZAR_ACTIONS_AB_ENABLED="true"
py -3.14 serve.py
```

Disable by removing the variable or setting it to `false`; V2 is then not loaded and normal NAZAR behavior is unchanged.
