"""
Attention Tracker — desktop app that detects when you're paying attention to the screen.

Uses the webcam and MediaPipe Face Landmarker to infer attention (face toward camera,
eyes open, not looking down). Session stats and attention spans are shown in the GUI
and optionally logged to a JSON file.

Run:
    python attention_tracker.py

Requires: opencv-python, mediapipe, numpy, pillow (see requirements.txt).
"""


def main():
    """Check dependencies, create tracker and GUI, run the main loop."""
    try:
        import cv2  # noqa: F401
        import mediapipe  # noqa: F401
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as e:
        print(f"Missing package: {e}")
        print("\nInstall dependencies with:")
        print("  pip install -r requirements.txt")
        return

    from tracker import AttentionTracker
    from gui import GUI

    tracker = AttentionTracker()
    gui = GUI(tracker)
    gui.root.mainloop()


if __name__ == "__main__":
    main()
