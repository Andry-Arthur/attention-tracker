# Attention Tracker

A desktop app that uses your webcam to detect when you're **paying attention** to the screen (face toward camera, eyes open, not looking down) and when you're **distracted**. It shows live stats and can log attention spans to a file.

## Try the app (no install required)

**Windows:** Download the latest release and run the app without installing Python or any dependencies.

1. Go to [**Releases**](https://github.com/YOUR_USERNAME/AttentionTracker/releases) and open the latest release.
2. Under **Assets**, download **AttentionTracker-Windows.zip**.
3. Unzip it somewhere on your PC, then run **AttentionTracker.exe** from inside the folder (keep all files together).
4. On first run, the app may download a small face-detection model and create a config file next to the exe. After that, click **Start** and allow webcam access to begin.

Replace `YOUR_USERNAME` in the Releases link with the repo owner's username, or use the **Releases** link from your repo's GitHub page.

## Features

- **Live camera preview** with attention state overlay (Attentive / Distracted)
- **Session statistics**: total time, attentive time, distracted time, current span, focus %
- **Analytics tab**: insights (avg/max span, distractions, focus %, current & longest streak) and **charts** — focus % over time (sampled every 10s) and attention-span duration (bar chart of last 20 spans). Requires `matplotlib`.
- **Calibration**: 5-second “look at screen” calibration to auto-tune thresholds for your setup
- **Configurable thresholds** via `attention_config.json` (or run Calibrate once)
- **Optional debug overlay**: EAR, MAR, nose position, raw decision on the video
- **Logging**: attention spans to `attention_log.json`; full session summaries (with samples and metrics) to `attention_sessions.json` (one JSON line per session)

## Requirements

- Webcam
- **To run the downloaded release:** Windows 10/11 (no Python required)
- **To run from source:** Python 3.10+, Windows / macOS / Linux

## Installation (run from source)

If you prefer to run the app from source (e.g. to modify it or on macOS/Linux):

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

## Building an executable (for distribution)

You can build a standalone executable so end users don't need Python or any packages installed.

1. Install dependencies and PyInstaller: `pip install -r requirements.txt` then `pip install pyinstaller`
2. Build from the project root: `pyinstaller --noconfirm attention_tracker.spec` (or run `build.bat` on Windows)
3. Output is in **`dist/AttentionTracker/`**. Run **`AttentionTracker.exe`** from that folder; distribute the whole folder.
4. On first run next to the .exe, the app creates `attention_config.json` and may download `face_landmarker.task`. Logs are written there too.

## Making a new release (after you've made changes)

To ship an updated executable on GitHub so the release reflects your latest code:

1. **Commit and push** your changes to your default branch (e.g. `main`):
   ```bash
   git add -A
   git commit -m "Describe your changes"
   git push
   ```

2. **Create a new release** on GitHub:
   - Open your repo → **Releases** → **Create a new release**
   - **Tag:** Choose a new version (e.g. `v1.0.1` for a small fix, `v1.1.0` for a new feature). Create the tag from the current branch (e.g. `main`).
   - **Title:** e.g. `v1.0.1` or `v1.0.1 – Fix calibration`
   - **Description:** Briefly say what changed. Remind users to download **AttentionTracker-Windows.zip** from Assets.

3. Click **Publish release**. The **Release** workflow runs, builds the executable from that commit, and attaches **AttentionTracker-Windows.zip** to this release.

4. In the **Actions** tab, wait for the workflow to finish. The zip will then appear under **Assets** on the release page.

Each release is tied to a specific tag/commit; the attached zip is built from that commit, so the release always matches the code at that version.

## Usage

1. Run the app:

   ```bash
   python attention_tracker.py
   ```

2. **Start** — begins webcam capture and attention detection. The video appears on the left; controls and stats on the right.
3. **Stop** — stops capture, keeps the last stats visible, and saves a session summary to `attention_sessions.json`.
4. **Reset** — clears session stats and smoothing state.
5. **Calibrate** — run this while tracking is active. Look at the screen for 5 seconds; the app will set thresholds from your typical pose and save them to `attention_config.json`.
6. **Analytics** tab — view insights (avg/max attention span, current and longest streak, focus %) and charts (focus over time, span durations). Click “Refresh charts” or switch to the tab to update.
7. **Debug overlay** — checkbox toggles EAR, MAR, nose position and raw decision on the video (useful for tuning).

## Layout

- **Left**: Camera preview (scaled to fit, max 640×360). State (Attentive / Distracted) is drawn on the frame.
- **Right**: Tabs **Live** and **Analytics**.
  - **Live**: Status, session stats, Start/Stop/Reset/Calibrate, Debug overlay, and a short hint.
  - **Analytics**: Insights (avg span, max span, distractions, focus %, current streak, longest streak), plus charts — focus % over time (every 10s) and attention-span durations (last 20 spans). Everything stays visible without fullscreen.

## Configuration

`attention_config.json` (in the project directory when running from source, or next to the .exe when running the built app) holds all thresholds. You can edit it by hand or use **Calibrate** to fill it from your setup. Main keys:

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

## Data and log files

- **attention_log.json** — When you switch from Attentive to Distracted, the last attention span (in seconds) is appended as one JSON object per line, e.g.  
  `{"timestamp": "2025-02-21T12:00:00", "attention_span_seconds": 45.2, "duration_human_readable": "45s"}`.
- **attention_sessions.json** — When you click **Stop**, a full session record is appended (one JSON line per session) with: `session_start_iso`, `session_end_iso`, `duration_sec`, `attentive_sec`, `distracted_sec`, `focus_pct`, `distraction_count`, `spans_sec`, `avg_span_sec`, `max_span_sec`, `samples` (time-series of focus every 10s), and `events_count`. Use this for deeper analysis or custom dashboards.

## Project structure

```
AttentionTracker/
├── attention_tracker.py   # Entry point
├── tracker.py             # Attention detection and capture loop
├── gui.py                 # Tkinter GUI (side-by-side layout)
├── config.py              # Load/save attention_config.json
├── attention_config.json   # Thresholds (created/updated by app or Calibrate)
├── attention_log.json      # Logged attention spans (created when first span is logged)
├── attention_sessions.json # Session summaries with metrics and samples (on Stop)
├── face_landmarker.task    # MediaPipe model (downloaded on first run)
├── attention_tracker.spec  # PyInstaller spec for building the executable
├── build.bat               # Windows build script
├── requirements.txt
├── README.md
└── LICENSE
```

## How detection works

- **Face landmarks** from MediaPipe Face Landmarker (478 points) are used each frame.
- **Eye aspect ratio (EAR)** — low when eyes are closed or blinking.
- **Head pose** — nose position and eye corners determine if the face is turned away or looking down/up.
- **Mouth aspect ratio (MAR)** — high when mouth is open (e.g. yawning).
- **Temporal smoothing** — the last N frames are combined so that brief look-aways or blinks don’t flip the state; thresholds and history length are in config.

## License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)** — a copyleft license. You may use, modify, and distribute it under the same license; derivative works must also be GPL-3.0 and source must be made available. See [LICENSE](LICENSE) and <https://www.gnu.org/licenses/gpl-3.0.html> for the full terms.

The MediaPipe Face Landmarker component is under the Apache License 2.0.
