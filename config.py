"""
Configuration for the Attention Tracker.

Loads and saves thresholds and options to a JSON file so tuning and
calibration persist across runs.
"""

import json
import os
import sys

# When built with PyInstaller, write next to the .exe; otherwise next to the package
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "attention_config.json")

DEFAULT_CONFIG = {
    "camera_placement": "center",
    "eye_ar_thresh": 0.20,
    "ear_blink_thresh": 0.18,
    "head_turn_frac": 0.28,
    "head_down_nose_y": 0.58,
    "head_up_nose_y": 0.35,
    "mar_yawn_thresh": 0.35,
    "yaw_margin": 0.08,
    "history_len": 9,
    "frames_attentive_to_switch": 4,
    "frames_distracted_to_switch": 5,
    "no_face_push_every_n": 3,
    "ear_smooth_len": 3,
    "debug_overlay": False,
    "calibrated": False,
}


def load_config():
    """Load config from JSON; use defaults if missing or invalid."""
    if not os.path.isfile(CONFIG_PATH):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_CONFIG)


def save_config(cfg):
    """Save config to JSON."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
