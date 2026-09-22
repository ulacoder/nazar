"""Environment-backed configuration, with paths relative to the project."""
from dataclasses import dataclass
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]

def _path(name, default):
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else ROOT / value

def _bool(name, default):
    return os.getenv(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}

@dataclass
class Settings:
    input_source: str = "CAMERA"
    video_path: str = ""
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    camera_fps: int = 30
    camera_device_id: str = ""
    ai_interval: float = 0.0
    pose_conf: float = 0.35
    device: str = "auto"
    actions_enabled: bool = True
    actions_ab_enabled: bool = False
    head_enabled: bool = True
    boxes_overlay: bool = True
    skeleton_overlay: bool = False
    attributes_overlay: bool = True
    overlay_debug: bool = False
    overlay_language: str = "en"
    event_min_duration: float = 0.8
    event_cooldown: float = 4.0
    writing_model_min: float = 0.45
    writing_motion_min: float = 0.025
    writing_temporal_min: float = 0.52
    track_max_gap_s: float = 2.5
    track_stationary_prior: bool = True
    track_home_alpha: float = .015
    track_ambiguity_margin: float = .08
    tracking_debug_dir: Path = ROOT / 'data/tracking_debug'
    evidence_pre_s: float = 3.0
    evidence_post_s: float = 3.0
    evidence_dir: Path = ROOT / "data/evidence"
    timelapse_enabled: bool = True
    timelapse_interval: float = 2.0
    timelapse_fps: float = 12.0
    timelapse_overlay: bool = False
    pose_weights: Path = ROOT / "models/yolo11n-pose.pt"
    action_weights: Path = ROOT / "models/actions_v4_epoch_1.pt"
    head_weights: Path = ROOT / "models/headpose_v2_best.pt"
    action_config: Path = ROOT / "models/actions_v2_reference_config.json"
    actions_ab_weights: Path = Path(r"C:\Users\Abik\Projects\yolo-pose-demo\experiments\nazar_actions_v2_real\nazar_actions_v2_real.pt")
    actions_ab_config: Path = Path(r"C:\Users\Abik\Projects\yolo-pose-demo\experiments\nazar_actions_v2_real\config.json")
    actions_ab_output_dir: Path = ROOT / "data/ab_tests"
    head_config: Path = ROOT / "models/head_direction_config.json"
    database: Path = ROOT / "data/nazar.sqlite3"
    sessions_dir: Path = ROOT / "data/sessions"
    video_import_dir: Path = ROOT / "data/imports"

    @classmethod
    def from_env(cls):
        return cls(
            input_source=os.getenv("NAZAR_INPUT_SOURCE", "CAMERA").strip().upper(),
            video_path=os.getenv("NAZAR_VIDEO_PATH", ""),
            camera_index=int(os.getenv("NAZAR_CAMERA_INDEX", "0")),
            camera_width=int(os.getenv("NAZAR_CAMERA_WIDTH", "1280")),
            camera_height=int(os.getenv("NAZAR_CAMERA_HEIGHT", "720")),
            camera_fps=int(os.getenv("NAZAR_CAMERA_FPS", "30")),
            camera_device_id=os.getenv("NAZAR_CAMERA_DEVICE_ID", ""),
            ai_interval=float(os.getenv("NAZAR_AI_INTERVAL", "0")),
            pose_conf=float(os.getenv("NAZAR_POSE_CONF", "0.35")),
            device=os.getenv("NAZAR_DEVICE", "auto"),
            actions_enabled=_bool("NAZAR_ACTIONS_ENABLED", True),
            actions_ab_enabled=_bool("NAZAR_ACTIONS_AB_ENABLED", False),
            head_enabled=_bool("NAZAR_HEAD_ENABLED", True),
            timelapse_enabled=_bool("NAZAR_TIMELAPSE_ENABLED", True),
            timelapse_interval=float(os.getenv("NAZAR_TIMELAPSE_INTERVAL", "2")),
            timelapse_fps=float(os.getenv("NAZAR_TIMELAPSE_OUTPUT_FPS", "12")),
            timelapse_overlay=_bool("NAZAR_TIMELAPSE_OVERLAY", False),
            writing_model_min=float(os.getenv("NAZAR_WRITING_MODEL_MIN", "0.45")),
            writing_motion_min=float(os.getenv("NAZAR_WRITING_MOTION_MIN", "0.025")),
            writing_temporal_min=float(os.getenv("NAZAR_WRITING_TEMPORAL_MIN", "0.52")),
            track_max_gap_s=float(os.getenv("NAZAR_TRACK_MAX_GAP_S", "2.5")),
            track_stationary_prior=_bool('NAZAR_TRACK_STATIONARY_PRIOR',True),
            track_home_alpha=float(os.getenv('NAZAR_TRACK_HOME_ALPHA','.015')),
            track_ambiguity_margin=float(os.getenv('NAZAR_TRACK_AMBIGUITY_MARGIN','.08')),
            overlay_debug=_bool("NAZAR_OVERLAY_DEBUG", False),
            overlay_language=os.getenv("NAZAR_OVERLAY_LANGUAGE", "en").lower(),
            evidence_pre_s=float(os.getenv("NAZAR_EVIDENCE_PRE_S", "3.0")),
            evidence_post_s=float(os.getenv("NAZAR_EVIDENCE_POST_S", "3.0")),
            evidence_dir=_path("NAZAR_EVIDENCE_DIR", "data/evidence"),
            pose_weights=_path("NAZAR_POSE_WEIGHTS", "models/yolo11n-pose.pt"),
            action_weights=_path("NAZAR_ACTION_WEIGHTS", "models/actions_v4_epoch_1.pt"),
            head_weights=_path("NAZAR_HEAD_WEIGHTS", "models/headpose_v2_best.pt"),
            action_config=_path("NAZAR_ACTION_CONFIG", "models/actions_v2_reference_config.json"),
            actions_ab_weights=_path("NAZAR_ACTIONS_AB_WEIGHTS", r"C:\Users\Abik\Projects\yolo-pose-demo\experiments\nazar_actions_v2_real\nazar_actions_v2_real.pt"),
            actions_ab_config=_path("NAZAR_ACTIONS_AB_CONFIG", r"C:\Users\Abik\Projects\yolo-pose-demo\experiments\nazar_actions_v2_real\config.json"),
            actions_ab_output_dir=_path("NAZAR_ACTIONS_AB_OUTPUT_DIR", "data/ab_tests"),
            head_config=_path("NAZAR_HEAD_CONFIG", "models/head_direction_config.json"),
            database=_path("NAZAR_DATABASE", "data/nazar.sqlite3"),
            sessions_dir=_path("NAZAR_SESSIONS_DIR", "data/sessions"),
            video_import_dir=_path("NAZAR_VIDEO_IMPORT_DIR", "data/imports"),
        )
