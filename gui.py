"""
GUI for the Attention Tracker.

Uses a side-by-side layout: video preview on the left, controls and stats
on the right so everything stays visible without fullscreen.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import cv2
from PIL import Image, ImageTk

from config import save_config
from tracker import AttentionTracker


# Preview size (right panel stays visible; video is scaled to fit)
VIDEO_MAX_WIDTH = 640
VIDEO_MAX_HEIGHT = 360
VIDEO_UPDATE_MS = 33
STATS_UPDATE_MS = 500


class GUI:
    """Main window: video left, controls and stats right."""

    def __init__(self, tracker: AttentionTracker):
        self.tracker = tracker
        self.tracker.root = self

        self.root = tk.Tk()
        self.root.title("Attention Tracker")
        self.root.minsize(900, 420)
        self.root.geometry("1000x440")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self._current_photo = None
        self._build_ui()
        self._update_timer()
        self._update_video()

    def _build_ui(self):
        """Build side-by-side layout: video (left) | controls + stats (right)."""
        self.root.columnconfigure(0, weight=0, minsize=VIDEO_MAX_WIDTH + 20)
        self.root.columnconfigure(1, weight=1, minsize=260)
        self.root.rowconfigure(0, weight=1)

        # —— Left: video ——
        video_frame = ttk.Frame(self.root, padding=5)
        video_frame.grid(row=0, column=0, sticky="nsew")
        self.video_label = tk.Label(
            video_frame,
            text="Camera preview\n(click Start to begin)",
            bg="#2b2b2b",
            fg="#888",
            font=("Segoe UI", 11),
        )
        self.video_label.pack(fill="both", expand=True)

        # —— Right: controls and stats ——
        right = ttk.Frame(self.root, padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        # Status
        self.status_var = tk.StringVar(value="Status: Stopped")
        status_lbl = ttk.Label(right, textvariable=self.status_var, font=("Segoe UI", 12, "bold"))
        status_lbl.grid(row=0, column=0, sticky="w", pady=(0, 10))

        # Stats (compact grid)
        stats_frame = ttk.LabelFrame(right, text="Session stats", padding=5)
        stats_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        stats_frame.columnconfigure(1, weight=1)

        self.stats_vars = {}
        labels = [
            "Total time",
            "Attentive",
            "Distracted",
            "Current span",
            "Distracted count",
            "Focus %",
        ]
        for i, label in enumerate(labels):
            ttk.Label(stats_frame, text=label + ":").grid(row=i, column=0, sticky="w", padx=(0, 8))
            self.stats_vars[label] = tk.StringVar(value="0")
            ttk.Label(stats_frame, textvariable=self.stats_vars[label]).grid(
                row=i, column=1, sticky="e"
            )

        # Buttons
        btn_frame = ttk.Frame(right)
        btn_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        ttk.Button(btn_frame, text="Start", command=self._start_tracker).grid(
            row=0, column=0, padx=2, pady=2, sticky="ew"
        )
        ttk.Button(btn_frame, text="Stop", command=self._stop_tracker).grid(
            row=0, column=1, padx=2, pady=2, sticky="ew"
        )
        ttk.Button(btn_frame, text="Reset", command=self._reset_tracker).grid(
            row=1, column=0, padx=2, pady=2, sticky="ew"
        )
        ttk.Button(btn_frame, text="Calibrate", command=self._calibrate_tracker).grid(
            row=1, column=1, padx=2, pady=2, sticky="ew"
        )

        # Debug overlay
        self.debug_var = tk.BooleanVar(value=getattr(self.tracker, "debug_overlay", False))

        def on_debug():
            self.tracker.debug_overlay = self.debug_var.get()
            self.tracker._config["debug_overlay"] = self.tracker.debug_overlay
            save_config(self.tracker._config)

        ttk.Checkbutton(right, text="Debug overlay", variable=self.debug_var, command=on_debug).grid(
            row=3, column=0, sticky="w", pady=(0, 8)
        )

        # Hint
        hint = "Start tracking, then Calibrate (5s) to auto-tune. Keep face visible and centered."
        ttk.Label(right, text=hint, font=("Segoe UI", 9), foreground="gray", wraplength=240).grid(
            row=4, column=0, sticky="w"
        )

    def _start_tracker(self):
        self.tracker.reset()
        self.tracker.start()
        self.status_var.set("Status: Tracking…")

    def _stop_tracker(self):
        self.tracker.stop()
        self.tracker.latest_frame = None
        self.status_var.set("Status: Stopped")
        self._refresh_stats()

    def _reset_tracker(self):
        self.tracker.reset()
        self.status_var.set("Status: Reset")
        self._refresh_stats()

    def _calibrate_tracker(self):
        if not self.tracker.running:
            messagebox.showinfo(
                "Calibrate",
                "Start tracking first, then click Calibrate.\nLook at the screen for 5 seconds.",
            )
            return
        self.tracker.start_calibration()
        self.status_var.set("Status: Calibrating… (5s)")

    def _refresh_stats(self):
        stats = self.tracker.get_stats()
        mapping = {
            "Total time": stats["total_time"],
            "Attentive": stats["attentive_time"],
            "Distracted": stats["distracted_time"],
            "Current span": stats["current_span"],
            "Distracted count": str(stats["distracted_count"]),
            "Focus %": f"{stats['attention_percentage']}%",
        }
        for label, value in mapping.items():
            self.stats_vars[label].set(value)

    def _update_timer(self):
        if self.tracker.running:
            self._refresh_stats()
            if getattr(self.tracker, "calibration_done", False):
                self.tracker.calibration_done = False
                self.status_var.set("Status: Tracking… (calibrated)")
        self.root.after(STATS_UPDATE_MS, self._update_timer)

    def _update_video(self):
        """Copy latest_frame to the video label (main thread only)."""
        frame = self.tracker.latest_frame
        if frame is not None:
            h, w = frame.shape[:2]
            scale = min(VIDEO_MAX_WIDTH / w, VIDEO_MAX_HEIGHT / h, 1.0)
            if scale < 1.0:
                nw, nh = int(w * scale), int(h * scale)
                frame = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            self._current_photo = ImageTk.PhotoImage(image=img)
            self.video_label.config(image=self._current_photo, text="")
        else:
            self.video_label.config(image="", text="Camera preview\n(click Start to begin)")
        self.root.after(VIDEO_UPDATE_MS, self._update_video)

    def _on_closing(self):
        self.tracker.stop()
        self.root.destroy()
