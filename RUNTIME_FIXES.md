# NAZAR 2.0 runtime fixes

The observed ID churn came from treating `max_missed` as a frame count while ByteTrack source IDs could change after a detection gap. The tracker now keeps anonymous tracks for a configurable 2.5 seconds, applies conservative IoU/normalized-center/size gates, and bridges a changed detector ID to the existing session ID. Reassociations are logged with gap, IoU, center distance, and source IDs. It never merges a detection outside those gates.

Writing now retains raw sigmoid probabilities and a short per-person history. The fusion score combines the recent writing probability with normalized wrist movement. Head-down or sitting evidence alone cannot create WRITING; moderate neural evidence must persist with compatible movement. Strong raw writing remains possible, and READING/WRITING remain independent. Diagnostics are returned under `actions_temporal`. Defaults are configurable through `NAZAR_WRITING_MODEL_MIN=0.45`, `NAZAR_WRITING_MOTION_MIN=0.025`, and `NAZAR_WRITING_TEMPORAL_MIN=0.52`.

EXAM events now carry `duration_s`, `review_priority`, and `reason`. Sustained lateral directions receive `REVIEW`; repeated lateral/back observations within a 30-second rolling window can receive `HIGH_REVIEW`. TURNED_BACK uses the same temporal confirmation and does not create an event every frame. No cheating, suspicious, violation, guilt, or attention score is generated.

The existing V1/V2 shadow A/B mode remains isolated: V2 diagnostics never enter production attributes, events, or session analytics. Pose still runs once per AI frame.
