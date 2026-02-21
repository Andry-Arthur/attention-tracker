# Attention Tracker

A desktop app that uses your webcam to detect when you're **paying attention** to the screen (face toward camera, eyes open, not looking down) and when you're **distracted**. It shows live stats and can log attention spans to a file.

## Features

- **Live camera preview** with attention state overlay (Attentive / Distracted)
- **Session statistics**: total time, attentive time, distracted time, current span, focus %
- **Calibration**: 5-second “look at screen” calibration to auto-tune thresholds for your setup
- **Configurable thresholds** via `attention_config.json` (or run Calibrate once)
- **Optional debug overlay**: EAR, MAR, nose position, raw decision on the video
- **Logging**: attention spans appended to `attention_log.json` (one JSON object per line)

## Requirements

- Python 3.10+
- Webcam
- Windows / macOS / Linux

## Installation

1. Clone or download this project.
2. Create a virtual environment (recommended):

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # macOS/Linux
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. On first run, the app will download the MediaPipe face landmarker model (`face_landmarker.task`) into the project folder if it’s missing.

## Usage

1. Run the app:

   ```bash
   python attention_tracker.py
   ```

2. **Start** — begins webcam capture and attention detection. The video appears on the left; controls and stats on the right.
3. **Stop** — stops capture and keeps the last stats visible.
4. **Reset** — clears session stats and smoothing state.
5. **Calibrate** — run this while tracking is active. Look at the screen for 5 seconds; the app will set thresholds from your typical pose and save them to `attention_config.json`.
6. **Debug overlay** — checkbox toggles EAR, MAR, nose position and raw decision on the video (useful for tuning).

## Layout

- **Left**: Camera preview (scaled to fit, max 640×360). State (Attentive / Distracted) is drawn on the frame.
- **Right**: Status, session stats, Start/Stop/Reset/Calibrate, Debug overlay, and a short hint. Everything stays visible without fullscreen.

## Configuration

`attention_config.json` in the project directory holds all thresholds. You can edit it by hand or use **Calibrate** to fill it from your setup. Main keys:

| Key | Description |
|-----|-------------|
| `camera_placement` | `"center"`, `"above"`, or `"below"` (relative to screen) |
| `eye_ar_thresh` | Eye aspect ratio below this = eyes closed |
| `ear_blink_thresh` | Strong blink threshold |
| `head_turn_frac` | Nose distance from center (normalized) to count as “turned away” |
| `head_down_nose_y` | Nose Y above this = looking down |
| `head_up_nose_y` | Nose Y below this = looking up (used when camera is below screen) |
| `mar_yawn_thresh` | Mouth aspect ratio above this = mouth open (e.g. yawn) |
| `debug_overlay` | Show EAR/MAR/nose/raw on video |

After calibration, `calibrated` is set to `true` and the thresholds above are updated.

## Log file

When you switch from Attentive to Distracted, the last “attention span” (in seconds) is appended to `attention_log.json` as one JSON object per line, e.g.:

```json
{"timestamp": "2025-02-21T12:00:00", "attention_span_seconds": 45.2, "duration_human_readable": "45s"}
```

## Project structure

```
AttentionTracker/
├── attention_tracker.py   # Entry point
├── tracker.py             # Attention detection and capture loop
├── gui.py                 # Tkinter GUI (side-by-side layout)
├── config.py              # Load/save attention_config.json
├── attention_config.json  # Thresholds (created/updated by app or Calibrate)
├── attention_log.json     # Logged attention spans (created when first span is logged)
├── face_landmarker.task   # MediaPipe model (downloaded on first run)
├── requirements.txt
└── README.md
```

## How detection works

- **Face landmarks** from MediaPipe Face Landmarker (478 points) are used each frame.
- **Eye aspect ratio (EAR)** — low when eyes are closed or blinking.
- **Head pose** — nose position and eye corners determine if the face is turned away or looking down/up.
- **Mouth aspect ratio (MAR)** — high when mouth is open (e.g. yawning).
- **Temporal smoothing** — the last N frames are combined so that brief look-aways or blinks don’t flip the state; thresholds and history length are in config.

## License

Use and modify as you like. MediaPipe is under the Apache License 2.0.
