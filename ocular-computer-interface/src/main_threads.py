import time
import threading
import cv2
from time import sleep

from cameras.picam import PiCam
from cameras.thermal import ThermalCam
from display.stereo_display import StereoDisplay
from controls.switch import get_position
from controls.rotary import get_rotation, is_pressed

# --- SETTINGS ---
FRAME_WIDTH = 800
FRAME_HEIGHT = 480
BORDER_PX = 10

# Map switch positions to camera modes
SWITCH_CAMERA_MAP = {
    1: "picam",
    2: "picam_noir",
    3: "thermal",
    4: "overlay_picam",
    5: "overlay_picam_noir"
}

# --- Shared frame buffers ---
frames = {
    "picam": None,
    "picam_noir": None,
    "thermal": None,
}

# --- Capture worker ---
def capture_worker(name, cam_class, kwargs):
    cam = cam_class(**kwargs)
    while True:
        try:
            frame = cam.capture()
            frames[name] = frame
        except Exception as e:
            print(f"[{name}] capture error: {e}")
            time.sleep(0.1)

# --- Main ---
def main():
    display = StereoDisplay(width=FRAME_WIDTH, height=FRAME_HEIGHT, border_px=BORDER_PX)

    # Start all capture threads
    threading.Thread(
        target=capture_worker,
        args=("picam", PiCam, {"camera_num": 1, "width": FRAME_WIDTH, "height": FRAME_HEIGHT}),
        daemon=True,
    ).start()

    threading.Thread(
        target=capture_worker,
        args=("picam_noir", PiCam, {"camera_num": 0, "width": FRAME_WIDTH, "height": FRAME_HEIGHT}),
        daemon=True,
    ).start()

    threading.Thread(
        target=capture_worker,
        args=("thermal", ThermalCam, {"width": FRAME_WIDTH // 2, "height": FRAME_HEIGHT}),
        daemon=True,
    ).start()

    current_mode = None
    zoom_factor = 1.0
    encoder_message = ""
    encoder_timer = 0

    try:
        while True:
            # --- Check switch ---
            switch_pos = get_position()
            if switch_pos in SWITCH_CAMERA_MAP:
                selected_mode = SWITCH_CAMERA_MAP[switch_pos]
                current_mode = selected_mode

            # --- Get frame ---
            frame = None
            if current_mode in ("picam", "picam_noir", "thermal"):
                frame = frames.get(current_mode)

            elif current_mode == "overlay_picam":
                base = frames.get("picam")
                overlay = frames.get("thermal")
                if base is not None and overlay is not None:
                    # Resize overlay to match FOV ratio (55 vs 75 deg)
                    scale = 75.0 / 55.0
                    h, w = overlay.shape[:2]
                    overlay_resized = cv2.resize(
                        overlay,
                        (int(w * scale), int(h * scale)),
                        interpolation=cv2.INTER_LINEAR
                    )
                    # Center crop overlay to base size
                    oh, ow = overlay_resized.shape[:2]
                    y0 = (oh - base.shape[0]) // 2
                    x0 = (ow - base.shape[1]) // 2
                    overlay_cropped = overlay_resized[y0:y0+base.shape[0], x0:x0+base.shape[1]]
                    frame = cv2.addWeighted(base, 0.7, overlay_cropped, 0.3, 0)

            elif current_mode == "overlay_picam_noir":
                base = frames.get("picam_noir")
                overlay = frames.get("thermal")
                if base is not None and overlay is not None:
                    scale = 75.0 / 55.0
                    h, w = overlay.shape[:2]
                    overlay_resized = cv2.resize(
                        overlay,
                        (int(w * scale), int(h * scale)),
                        interpolation=cv2.INTER_LINEAR
                    )
                    oh, ow = overlay_resized.shape[:2]
                    y0 = (oh - base.shape[0]) // 2
                    x0 = (ow - base.shape[1]) // 2
                    overlay_cropped = overlay_resized[y0:y0+base.shape[0], x0:x0+base.shape[1]]
                    frame = cv2.addWeighted(base, 0.7, overlay_cropped, 0.3, 0)

            # Skip if no frame available yet
            if frame is None:
                sleep(0.01)
                continue

            # --- Encoder ---
            rotation = get_rotation()
            button_pressed = is_pressed()

            if rotation != 0:
                step = 0.1
                zoom_factor = max(1.0, zoom_factor + step * rotation)
                encoder_message = f"Zoom: {zoom_factor:.1f}x"
                encoder_timer = 1.0
            elif button_pressed:
                zoom_factor = 1.0
                encoder_message = "Zoom reset"
                encoder_timer = 1.0

            # --- Overlay text ---
            text_lines = []
            if switch_pos:
                text_lines.append(f"Switch: {switch_pos}")
            if encoder_timer > 0:
                text_lines.append(encoder_message)

            y0 = FRAME_HEIGHT // 2 - (len(text_lines) * 20)
            for i, line in enumerate(text_lines):
                (text_w, text_h), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
                x = (FRAME_WIDTH - text_w) // 2
                y = y0 + i * (text_h + 10)
                cv2.putText(frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

            if encoder_timer > 0:
                encoder_timer -= 0.01
            else:
                encoder_message = ""

            # Show frame
            display.show(frame)
            sleep(0.01)

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        display.close()


if __name__ == "__main__":
    main()
