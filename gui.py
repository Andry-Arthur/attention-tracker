"""
GUI for the Attention Tracker.

Side-by-side layout: video preview on the left, controls and analytics on the right.
Uses a notebook with "Live" (session stats + controls) and "Analytics" (metrics + charts).
"""

import tkinter as tk
from tkinter import ttk, messagebox

import cv2
from PIL import Image, ImageTk

from config import save_config
from tracker import AttentionTracker


VIDEO_MAX_WIDTH = 640
VIDEO_MAX_HEIGHT = 360
VIDEO_UPDATE_MS = 33
STATS_UPDATE_MS = 500
# Max spans to show in bar chart
MAX_SPANS_CHART = 20


class GUI:
    """Main window: video left, notebook (Live | Analytics) right."""

    def __init__(self, tracker: AttentionTracker):
        self.tracker = tracker
        self.tracker.root = self

        self.root = tk.Tk()
        self.root.title("Attention Tracker")
        self.root.minsize(960, 520)
        self.root.geometry("1100x560")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self._current_photo = None
        self._analytics_canvas = None
        self._analytics_fig = None
        self._build_ui()
        self._update_timer()
        self._update_video()

    def _build_ui(self):
        """Build layout: video (left) | notebook with Live and Analytics (right)."""
        self.root.columnconfigure(0, weight=0, minsize=VIDEO_MAX_WIDTH + 20)
        self.root.columnconfigure(1, weight=1, minsize=320)
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

        # —— Right: notebook ——
        right = ttk.Frame(self.root, padding=8)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        self.status_var = tk.StringVar(value="Status: Stopped")
        ttk.Label(right, textvariable=self.status_var, font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        self.notebook = ttk.Notebook(right)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.notebook.columnconfigure(0, weight=1)
        self.notebook.rowconfigure(0, weight=1)

        # —— Tab: Live ——
        live_tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(live_tab, text="Live")
        live_tab.columnconfigure(0, weight=1)

        stats_frame = ttk.LabelFrame(live_tab, text="Session stats", padding=6)
        stats_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        stats_frame.columnconfigure(1, weight=1)

        self.stats_vars = {}
        for i, label in enumerate([
            "Total time", "Attentive", "Distracted",
            "Current span", "Distracted count", "Focus %",
        ]):
            ttk.Label(stats_frame, text=label + ":").grid(row=i, column=0, sticky="w", padx=(0, 8))
            self.stats_vars[label] = tk.StringVar(value="0")
            ttk.Label(stats_frame, textvariable=self.stats_vars[label]).grid(
                row=i, column=1, sticky="e"
            )

        btn_frame = ttk.Frame(live_tab)
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(0, 6))
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

        self.debug_var = tk.BooleanVar(value=getattr(self.tracker, "debug_overlay", False))

        def on_debug():
            self.tracker.debug_overlay = self.debug_var.get()
            self.tracker._config["debug_overlay"] = self.tracker.debug_overlay
            save_config(self.tracker._config)

        ttk.Checkbutton(live_tab, text="Debug overlay", variable=self.debug_var, command=on_debug).grid(
            row=2, column=0, sticky="w", pady=(0, 6)
        )
        ttk.Label(live_tab, text="Start tracking, then Calibrate (5s) to auto-tune. Keep face visible.",
                  font=("Segoe UI", 9), foreground="gray", wraplength=280).grid(row=3, column=0, sticky="w")

        # —— Tab: Analytics ——
        analytics_tab = ttk.Frame(self.notebook, padding=5)
        self.notebook.add(analytics_tab, text="Analytics")
        analytics_tab.columnconfigure(0, weight=1)
        analytics_tab.rowconfigure(2, weight=1)

        # Key metrics (2x3 grid)
        metrics_frame = ttk.LabelFrame(analytics_tab, text="Insights", padding=6)
        metrics_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        metrics_frame.columnconfigure(0, weight=1)
        metrics_frame.columnconfigure(1, weight=1)
        metrics_frame.columnconfigure(2, weight=1)

        self.metric_vars = {}
        metric_labels = [
            ("Avg span", "avg_span"),
            ("Max span", "max_span"),
            ("Distractions", "distractions"),
            ("Focus %", "focus_pct"),
            ("Current streak", "current_streak"),
            ("Longest streak", "longest_streak"),
        ]
        for i, (label, key) in enumerate(metric_labels):
            r, c = i // 3, (i % 3) * 2
            ttk.Label(metrics_frame, text=label + ":", font=("Segoe UI", 9)).grid(
                row=r, column=c, sticky="w", padx=(0, 4)
            )
            self.metric_vars[key] = tk.StringVar(value="—")
            ttk.Label(metrics_frame, textvariable=self.metric_vars[key], font=("Segoe UI", 10, "bold")).grid(
                row=r, column=c + 1, sticky="w"
            )

        ttk.Button(analytics_tab, text="Refresh charts", command=self._refresh_analytics).grid(
            row=1, column=0, sticky="w", pady=(0, 4)
        )

        # Charts container (matplotlib embedded here)
        charts_frame = ttk.LabelFrame(analytics_tab, text="Charts", padding=4)
        charts_frame.grid(row=2, column=0, sticky="nsew")
        charts_frame.columnconfigure(0, weight=1)
        charts_frame.rowconfigure(0, weight=1)
        self._charts_container = charts_frame

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        if event.widget.tab(event.widget.select(), "text") == "Analytics":
            self._refresh_analytics()

    def _refresh_analytics(self):
        """Update analytics metrics and redraw charts from tracker.get_analytics()."""
        a = self.tracker.get_analytics()
        # Metrics
        avg = a.get("avg_span_sec", 0)
        mx = a.get("max_span_sec", 0)
        self.metric_vars["avg_span"].set(f"{avg}s" if avg else "—")
        self.metric_vars["max_span"].set(f"{mx}s" if mx else "—")
        self.metric_vars["distractions"].set(str(a.get("distracted_count", 0)))
        self.metric_vars["focus_pct"].set(f"{a.get('attention_percentage', 0)}%")
        cur = a.get("current_streak_sec", 0)
        self.metric_vars["current_streak"].set(f"{cur}s" if cur else "—")
        self.metric_vars["longest_streak"].set(f"{mx}s" if mx else "—")

        # Charts with matplotlib
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            if not hasattr(self, "_matplotlib_warned"):
                self._matplotlib_warned = True
                messagebox.showinfo("Analytics", "Install matplotlib to see charts:\npip install matplotlib")
            return

        # Remove previous canvas
        for w in self._charts_container.winfo_children():
            w.destroy()

        fig = Figure(figsize=(4.2, 3.2), dpi=100, facecolor="#fafafa")
        samples = a.get("samples", [])
        spans = a.get("spans_sec", [])[-MAX_SPANS_CHART:]

        # 1) Focus over time (line)
        ax1 = fig.add_subplot(211)
        if samples:
            x = [s["elapsed_sec"] / 60 for s in samples]
            y = [s["focus_pct"] for s in samples]
            ax1.plot(x, y, color="#2e7d32", linewidth=2, marker="o", markersize=4)
            ax1.fill_between(x, y, alpha=0.2, color="#2e7d32")
            ax1.set_ylabel("Focus %")
            ax1.set_xlabel("Time (min)")
            ax1.set_title("Focus over time")
            ax1.set_ylim(0, 105)
            ax1.grid(True, alpha=0.3)
        else:
            ax1.text(0.5, 0.5, "No data yet.\nStart tracking and wait for samples (every 10s).",
                     ha="center", va="center", transform=ax1.transAxes, fontsize=9)
            ax1.set_title("Focus over time")

        # 2) Attention spans (bar)
        ax2 = fig.add_subplot(212)
        if spans:
            n = len(spans)
            ax2.bar(range(n), spans, color="#1565c0", alpha=0.8, edgecolor="#0d47a1")
            ax2.set_ylabel("Seconds")
            ax2.set_xlabel("Span # (most recent)")
            ax2.set_title("Attention span duration (last {} spans)".format(n))
            ax2.grid(True, axis="y", alpha=0.3)
        else:
            ax2.text(0.5, 0.5, "No attention spans yet.\nLook at the screen; spans log when you look away.",
                     ha="center", va="center", transform=ax2.transAxes, fontsize=9)
            ax2.set_title("Attention span duration")

        fig.tight_layout()
        self._analytics_fig = fig
        self._analytics_canvas = FigureCanvasTkAgg(fig, master=self._charts_container)
        self._analytics_canvas.draw()
        self._analytics_canvas.get_tk_widget().pack(fill="both", expand=True)

    def _start_tracker(self):
        self.tracker.reset()
        self.tracker.start()
        self.status_var.set("Status: Tracking…")

    def _stop_tracker(self):
        self.tracker.stop()
        self.tracker.latest_frame = None
        self.status_var.set("Status: Stopped")
        self._refresh_stats()
        self._refresh_analytics()

    def _reset_tracker(self):
        self.tracker.reset()
        self.status_var.set("Status: Reset")
        self._refresh_stats()
        self._refresh_analytics()

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
