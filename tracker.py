"""
Attention tracking logic using MediaPipe Face Landmarker.

Detects whether the user is paying attention to the screen (face toward camera,
eyes open, not looking down) and maintains session statistics with temporal
smoothing to reduce flicker.
"""

import json
import os
import threading
import time
import urllib.request
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision
from tkinter import messagebox

from config import load_config, save_config, DEFAULT_CONFIG, CONFIG_PATH, BASE_DIR


# Model download URL; file is stored in BASE_DIR (next to exe when frozen)
FACE_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
LOG_FILE_PATH = os.path.join(BASE_DIR, "attention_log.json")
SESSIONS_FILE_PATH = os.path.join(BASE_DIR, "attention_sessions.json")
SAMPLE_INTERVAL_SEC = 10  # time-series sample every N seconds for analytics charts


def ensure_face_landmarker_model():
    """Return path to face_landmarker.task, downloading if missing."""
    path = os.path.join(BASE_DIR, "face_landmarker.task")
    if not os.path.isfile(path):
        try:
            urllib.request.urlretrieve(FACE_LANDMARKER_MODEL_URL, path)
        except Exception as e:
            raise FileNotFoundError(
                f"Could not download face_landmarker.task. "
                f"Download manually from {FACE_LANDMARKER_MODEL_URL} and place in {BASE_DIR}"
            ) from e
    return path


class AttentionTracker:
    """
    Tracks attention state from webcam frames using face landmarks.

    Uses eye aspect ratio (EAR), head pose (yaw / nose position), and
    mouth aspect ratio (MAR) to decide attentive vs distracted, with
    temporal smoothing over the last N frames.
    """

    def __init__(self):
        self._config = load_config()
        self._apply_config()

        model_path = ensure_face_landmarker_model()
        base_options = mp_tasks.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            num_faces=1,
            min_face_detection_confidence=0.5,
            running_mode=vision.RunningMode.VIDEO,
        )
        self.face_landmarker = vision.FaceLandmarker.create_from_options(options)
        self._frame_timestamp_ms = 0

        self.cap = None
        self.running = False
        self.thread = None

        self.state = "IDLE"
        self.session_start_time = None
        self.attention_start_time = None
        self.current_attention_span = 0
        self.total_attentive_time = 0
        self.total_distracted_time = 0
        self.distracted_count = 0
        self.session_data = []
        self._session_events = []   # {t, from_state, to_state, span_sec?}
        self._session_samples = []  # {elapsed_sec, attentive_sec, distracted_sec, focus_pct}
        self._last_sample_time = None

        self.latest_frame = None
        self._ear_history = deque(maxlen=max(1, getattr(self, "_ear_smooth_len", 3)))
        self._no_face_count = 0

        self.calibrating = False
        self._calibration_start = None
        self._calibration_samples = []
        self.calibration_done = False

        self._last_ear = 0.0
        self._last_mar = 0.0
        self._last_nose_xy = (0.5, 0.5)
        self._last_raw_attentive = False

    def _apply_config(self):
        """Apply config dict to instance thresholds and history size."""
        c = self._config
        self.EYE_AR_THRESH = c.get("eye_ar_thresh", DEFAULT_CONFIG["eye_ar_thresh"])
        self.EAR_BLINK_THRESH = c.get("ear_blink_thresh", DEFAULT_CONFIG["ear_blink_thresh"])
        self.HEAD_TURN_FRAC = c.get("head_turn_frac", DEFAULT_CONFIG["head_turn_frac"])
        self.HEAD_DOWN_NOSE_Y = c.get("head_down_nose_y", DEFAULT_CONFIG["head_down_nose_y"])
        self.HEAD_UP_NOSE_Y = c.get("head_up_nose_y", DEFAULT_CONFIG["head_up_nose_y"])
        self.MAR_YAWN_THRESH = c.get("mar_yawn_thresh", DEFAULT_CONFIG["mar_yawn_thresh"])
        self.YAW_MARGIN = c.get("yaw_margin", DEFAULT_CONFIG["yaw_margin"])
        history_len = c.get("history_len", DEFAULT_CONFIG["history_len"])
        self._raw_attention_history = deque(maxlen=history_len)
        self._frames_attentive_to_switch = c.get(
            "frames_attentive_to_switch", DEFAULT_CONFIG["frames_attentive_to_switch"]
        )
        self._frames_distracted_to_switch = c.get(
            "frames_distracted_to_switch", DEFAULT_CONFIG["frames_distracted_to_switch"]
        )
        self._no_face_push_every_n = c.get(
            "no_face_push_every_n", DEFAULT_CONFIG["no_face_push_every_n"]
        )
        self._ear_smooth_len = c.get("ear_smooth_len", DEFAULT_CONFIG["ear_smooth_len"])
        self.debug_overlay = c.get("debug_overlay", DEFAULT_CONFIG["debug_overlay"])

    @staticmethod
    def eye_aspect_ratio(landmarks, eye_indices):
        """Compute eye aspect ratio (EAR) from 6 landmarks per eye; low = closed."""
        pts = np.array([[landmarks[i].x, landmarks[i].y] for i in eye_indices])
        A = np.linalg.norm(pts[1] - pts[5])
        B = np.linalg.norm(pts[2] - pts[4])
        C = np.linalg.norm(pts[0] - pts[3])
        return (A + B) / (2.0 * C)

    @staticmethod
    def mouth_aspect_ratio(landmarks):
        """Mouth aspect ratio; high when mouth open (e.g. yawn). Indices 13,14=lip, 81,82=corners."""
        try:
            v = abs(landmarks[14].y - landmarks[13].y)
            w = abs(landmarks[82].x - landmarks[81].x)
            return v / w if w >= 1e-5 else 0.0
        except (IndexError, AttributeError):
            return 0.0

    def _raw_attention(self, landmarks, frame_width, frame_height):
        """Per-frame decision: True = attentive, False = distracted (no temporal smoothing)."""
        left_eye_idx = [362, 385, 387, 263, 373, 380]
        right_eye_idx = [33, 160, 158, 133, 153, 144]

        left_ear = self.eye_aspect_ratio(landmarks, left_eye_idx)
        right_ear = self.eye_aspect_ratio(landmarks, right_eye_idx)
        ear_raw = (left_ear + right_ear) / 2.0
        self._ear_history.append(ear_raw)
        ear = sum(self._ear_history) / len(self._ear_history)
        self._last_ear = ear

        if ear < self.EAR_BLINK_THRESH or ear < self.EYE_AR_THRESH:
            return False

        mar = self.mouth_aspect_ratio(landmarks)
        self._last_mar = mar
        if mar > self.MAR_YAWN_THRESH:
            return False

        nose = landmarks[1]
        self._last_nose_xy = (nose.x, nose.y)

        left_outer_x = landmarks[362].x
        right_outer_x = landmarks[133].x
        margin = self.YAW_MARGIN
        if nose.x < (left_outer_x - margin) or nose.x > (right_outer_x + margin):
            return False
        if abs(nose.x - 0.5) > self.HEAD_TURN_FRAC:
            return False

        placement = self._config.get("camera_placement", "center")
        if placement == "below":
            head_bad = nose.y < self.HEAD_UP_NOSE_Y
        elif placement == "above":
            head_bad = nose.y > self.HEAD_DOWN_NOSE_Y
        else:
            head_bad = nose.y > self.HEAD_DOWN_NOSE_Y or nose.y < self.HEAD_UP_NOSE_Y
        if head_bad:
            return False

        return True

    def process_frame(self, frame):
        """Process one frame; return 'ATTENTIVE' or 'DISTRACTED' with temporal smoothing."""
        frame_height, frame_width = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        self._frame_timestamp_ms += 33
        result = self.face_landmarker.detect_for_video(mp_image, self._frame_timestamp_ms)

        if not result.face_landmarks:
            self._no_face_count += 1
            if self._no_face_count % self._no_face_push_every_n == 0:
                self._raw_attention_history.append(False)
            self._last_raw_attentive = False
        else:
            self._no_face_count = 0
            landmarks = result.face_landmarks[0]
            raw = self._raw_attention(landmarks, frame_width, frame_height)
            self._raw_attention_history.append(raw)
            self._last_raw_attentive = raw
            if getattr(self, "calibrating", False):
                self._calibration_samples.append({
                    "nose_x": self._last_nose_xy[0],
                    "nose_y": self._last_nose_xy[1],
                    "ear": self._last_ear,
                })

        n = len(self._raw_attention_history)
        if n < self._frames_attentive_to_switch:
            return "DISTRACTED"
        att = sum(1 for x in self._raw_attention_history if x)
        distracted_count = n - att
        if distracted_count >= self._frames_distracted_to_switch:
            return "DISTRACTED"
        if att >= self._frames_attentive_to_switch:
            return "ATTENTIVE"
        return "ATTENTIVE" if att > distracted_count else "DISTRACTED"

    def main_loop(self):
        """Capture loop: read webcam, process frames, update state and latest_frame."""
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Error", "Could not open webcam!")
            self.running = False
            return

        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break

            new_state = self.process_frame(frame)
            current_time = time.time()

            if getattr(self, "calibrating", False) and self._calibration_start is not None:
                if current_time - self._calibration_start >= 5.0:
                    self._finish_calibration()
                    self.calibrating = False
                    self._calibration_start = None

            prev_state = self.state
            if self.state == "IDLE" and new_state == "ATTENTIVE":
                self.state = "ATTENTIVE"
                self.attention_start_time = current_time
                self.session_start_time = current_time
                self._session_events.append({"t": current_time, "from_state": "IDLE", "to_state": "ATTENTIVE"})
                self._last_sample_time = current_time
            elif self.state == "ATTENTIVE":
                if new_state == "DISTRACTED":
                    span = current_time - self.attention_start_time
                    self._session_events.append({
                        "t": current_time, "from_state": "ATTENTIVE", "to_state": "DISTRACTED",
                        "span_sec": round(span, 2),
                    })
                    self.state = "DISTRACTED"
                    if span > 1:
                        self.current_attention_span = span
                        self.distracted_count += 1
                        self.log_attention_span(span)
                    self.total_attentive_time += span
                    self.attention_start_time = None
                else:
                    self.current_attention_span = current_time - self.attention_start_time
            elif self.state == "DISTRACTED":
                if new_state == "ATTENTIVE":
                    self.state = "ATTENTIVE"
                    self.attention_start_time = current_time
                    self._session_events.append({"t": current_time, "from_state": "DISTRACTED", "to_state": "ATTENTIVE"})
                else:
                    self.total_distracted_time += 0.1

            # Time-series sample every SAMPLE_INTERVAL_SEC for charts
            if self.session_start_time is not None and self._last_sample_time is not None:
                if current_time - self._last_sample_time >= SAMPLE_INTERVAL_SEC:
                    elapsed = current_time - self.session_start_time
                    att = self.total_attentive_time
                    if self.state == "ATTENTIVE" and self.attention_start_time:
                        att += current_time - self.attention_start_time
                    dist = elapsed - att
                    pct = (att / elapsed * 100) if elapsed > 0 else 0
                    self._session_samples.append({
                        "elapsed_sec": round(elapsed, 1),
                        "attentive_sec": round(att, 1),
                        "distracted_sec": round(dist, 1),
                        "focus_pct": round(pct, 1),
                    })
                    self._last_sample_time = current_time

            display = frame.copy()
            color = (
                (0, 255, 0)
                if self.state == "ATTENTIVE"
                else (0, 0, 255)
                if self.state == "DISTRACTED"
                else (128, 128, 128)
            )
            cv2.putText(display, self.state, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            if getattr(self, "debug_overlay", False):
                h = display.shape[0]
                cv2.putText(
                    display, f"EAR:{self._last_ear:.2f} MAR:{self._last_mar:.2f}",
                    (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1
                )
                cv2.putText(
                    display,
                    f"nose:({self._last_nose_xy[0]:.2f},{self._last_nose_xy[1]:.2f}) raw:{self._last_raw_attentive}",
                    (10, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1
                )
            if getattr(self, "calibrating", False):
                cv2.putText(
                    display, "Calibrating... Look at screen",
                    (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                )
            self.latest_frame = display
            time.sleep(0.1)

        self.cap.release()
        self.latest_frame = None
        self._save_session()

    def _save_session(self):
        """Append current session summary to sessions file (one JSON line)."""
        if self.session_start_time is None:
            return
        session_end = time.time()
        elapsed = session_end - self.session_start_time
        att = self.total_attentive_time
        dist = elapsed - att
        pct = (att / elapsed * 100) if elapsed > 0 else 0
        spans_sec = [e["attention_span_seconds"] for e in self.session_data]
        session_record = {
            "session_start_iso": datetime.fromtimestamp(self.session_start_time).isoformat(),
            "session_end_iso": datetime.fromtimestamp(session_end).isoformat(),
            "duration_sec": round(elapsed, 1),
            "attentive_sec": round(att, 1),
            "distracted_sec": round(dist, 1),
            "focus_pct": round(pct, 1),
            "distraction_count": self.distracted_count,
            "spans_sec": spans_sec,
            "avg_span_sec": round(sum(spans_sec) / len(spans_sec), 1) if spans_sec else 0,
            "max_span_sec": round(max(spans_sec), 1) if spans_sec else 0,
            "samples": self._session_samples,
            "events_count": len(self._session_events),
        }
        try:
            with open(SESSIONS_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(session_record) + "\n")
        except OSError:
            pass

    def log_attention_span(self, span):
        """Append one attention-span entry to the log file."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "attention_span_seconds": round(span, 2),
            "duration_human_readable": self.format_time(span),
        }
        self.session_data.append(entry)
        with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    @staticmethod
    def format_time(seconds):
        """Format seconds as e.g. '2m 30s' or '1h 0m 0s'."""
        hrs = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if hrs > 0:
            return f"{hrs}h {mins}m {secs}s"
        if mins > 0:
            return f"{mins}m {secs}s"
        return f"{secs}s"

    def get_stats(self):
        """Return current session stats (total/attentive/distracted time, count, %)."""
        if self.session_start_time is None:
            return {
                "total_time": "0s",
                "attentive_time": "0s",
                "distracted_time": "0s",
                "current_span": "0s",
                "distracted_count": 0,
                "attention_percentage": 0,
            }
        total_time = time.time() - self.session_start_time
        attentive = self.total_attentive_time
        if self.state == "ATTENTIVE" and self.attention_start_time:
            attentive += time.time() - self.attention_start_time
        distracted = total_time - attentive
        percentage = (attentive / total_time * 100) if total_time > 0 else 0
        return {
            "total_time": self.format_time(total_time),
            "attentive_time": self.format_time(attentive),
            "distracted_time": self.format_time(distracted),
            "current_span": self.format_time(self.current_attention_span),
            "distracted_count": self.distracted_count,
            "attention_percentage": round(percentage, 1),
        }

    def get_analytics(self):
        """Return stats plus analytics for charts: avg/max span, streak, spans list, time-series samples."""
        stats = self.get_stats()
        spans_sec = [e["attention_span_seconds"] for e in self.session_data]
        avg_span = round(sum(spans_sec) / len(spans_sec), 1) if spans_sec else 0
        max_span = round(max(spans_sec), 1) if spans_sec else 0
        if self.state == "ATTENTIVE" and self.attention_start_time is not None:
            current_streak = round(time.time() - self.attention_start_time, 1)
        else:
            current_streak = 0
        stats["avg_span_sec"] = avg_span
        stats["max_span_sec"] = max_span
        stats["current_streak_sec"] = current_streak
        stats["longest_streak_sec"] = max_span
        stats["spans_sec"] = spans_sec
        stats["samples"] = list(self._session_samples)
        stats["events_count"] = len(self._session_events)
        return stats

    def start(self):
        """Start the capture/processing loop in a background thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self.main_loop, daemon=True)
            self.thread.start()

    def stop(self):
        """Stop the loop and wait for the thread to finish (up to 2s)."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def reset(self):
        """Reset session stats and smoothing buffers."""
        self.state = "IDLE"
        self.session_start_time = None
        self.attention_start_time = None
        self.current_attention_span = 0
        self.total_attentive_time = 0
        self.total_distracted_time = 0
        self.distracted_count = 0
        self.session_data = []
        self._session_events.clear()
        self._session_samples.clear()
        self._last_sample_time = None
        self._raw_attention_history.clear()
        self._ear_history.clear()

    def start_calibration(self):
        """Start a 5-second calibration; thresholds will be updated from observed range."""
        self.calibrating = True
        self._calibration_start = time.time()
        self._calibration_samples = []

    def _finish_calibration(self):
        """Compute thresholds from calibration samples and save to config."""
        if len(self._calibration_samples) < 10:
            return
        nose_x = [s["nose_x"] for s in self._calibration_samples]
        nose_y = [s["nose_y"] for s in self._calibration_samples]
        ears = [s["ear"] for s in self._calibration_samples]
        self._config["head_turn_frac"] = float(
            np.percentile(np.abs(np.array(nose_x) - 0.5), 90)
        ) * 1.2
        self._config["head_down_nose_y"] = float(np.percentile(nose_y, 95)) + 0.05
        self._config["head_up_nose_y"] = float(np.percentile(nose_y, 5)) - 0.05
        self._config["eye_ar_thresh"] = float(np.percentile(ears, 10)) * 0.9
        self._config["ear_blink_thresh"] = float(np.percentile(ears, 5)) * 0.85
        self._config["calibrated"] = True
        save_config(self._config)
        self._apply_config()
        self.calibration_done = True
