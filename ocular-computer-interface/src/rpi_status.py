import time
import cv2
import threading
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
ZOOM_STEP = 0.1

# Camera FOVs
PICAM_FOV = 75  # degrees
THERMAL_FOV = 55  # degrees
FOV_SCALE = THERMAL_FOV / PICAM_FOV  # scaling factor for overlay

# Map switch positions to camera modes
SWITCH_CAMERA_MAP = {
    1: "picam",
    2: "picam_noir",
    3: "thermal",
    4: "overlay_picam",
    5: "overlay_noir",
}

# --- Global storage for thermal frames ---
thermal_frame = None
thermal_lock = threading.Lock()


def thermal_thread_worker():
    """Background thermal capture thread."""
    global thermal_frame
    cam = ThermalCam(width=FRAME_WIDTH // 2, height=FRAME_HEIGHT)

    while True:
        frame = cam.capture()
        if frame is not None:
            with thermal_lock:
                thermal_frame = frame
        sleep(0.01)  # don't hog CPU


def create_camera(mode):
    if mode in ["picam", "picam_noir"]:
        camera_num = 0 if mode == "picam_noir" else 1
        for attempt in range(3):
            try:
                return PiCam(camera_num=camera_num, width=FRAME_WIDTH, height=FRAME_HEIGHT)
            except RuntimeError:
                print(f"Failed to open {mode}, retrying... ({attempt+1}/3)")
                time.sleep(0.2)
        raise RuntimeError(f"Unable to open camera {mode}")
    return None


def overlay_thermal(base_frame, thermal_frame):
    """Overlay thermal frame onto picam frame, FOV-adjusted with upscaling."""
    if thermal_frame is None:
        return base_frame

    h, w = base_frame.shape[:2]

    # Upscale thermal to screen size first
    upscale = cv2.resize(
        thermal_frame, (w, h), interpolation=cv2.INTER_CUBIC
    )

    # Scale to FOV
    target_w = int(w * FOV_SCALE)
    target_h = int(h * FOV_SCALE)
    resized = cv2.resize(upscale, (target_w, target_h), interpolation=cv2.INTER_CUBIC)

    # Center it
    x_offset = (w - target_w) // 2
    y_offset = (h - target_h) // 2
    overlay = base_frame.copy()
    overlay[y_offset:y_offset+target_h, x_offset:x_offset+target_w] = cv2.addWeighted(
        base_frame[y_offset:y_offset+target_h, x_offset:x_offset+target_w], 0.5,
        resized, 0.5, 0
    )
    return overlay



def main():
    display = StereoDisplay(width=FRAME_WIDTH, height=FRAME_HEIGHT, border_px=BORDER_PX)

    # Start thermal thread
    threading.Thread(target=thermal_thread_worker, daemon=True).start()

    current_mode = None
    cam = None
    zoom_factor = 1.0
    encoder_message = ""
    encoder_timer = 0

    try:
        while True:
            # --- Switch handling ---
            switch_pos = get_position()
            if switch_pos in SWITCH_CAMERA_MAP:
                selected_mode = SWITCH_CAMERA_MAP[switch_pos]

                # Switch PiCam only if needed
                if selected_mode != current_mode:
                    print(f"Switching camera to: {selected_mode}")
                    if cam and hasattr(cam, "stop"):
                        cam.stop()
                        cam = None

                    if selected_mode in ["picam", "picam_noir"]:
                        cam = create_camera(selected_mode)
                        cam.set_zoom(zoom_factor)

                    current_mode = selected_mode

            if not current_mode:
                sleep(0.05)
                continue

            frame = None
            if current_mode in ["picam", "picam_noir"]:
                frame = cam.capture()

            elif current_mode == "thermal":
                with thermal_lock:
                    frame = thermal_frame.copy() if thermal_frame is not None else None

            elif current_mode in ["overlay_picam", "overlay_noir"]:
                if cam is None:
                    cam = create_camera("picam" if current_mode == "overlay_picam" else "picam_noir")
                    cam.set_zoom(zoom_factor)
                frame = cam.capture()
                with thermal_lock:
                    if thermal_frame is not None:
                        frame = overlay_thermal(frame, thermal_frame)

            if frame is None:
                continue

            # --- Encoder handling ---
            rotation = get_rotation()
            button_pressed = is_pressed()
            if rotation:
                zoom_factor = max(1.0, zoom_factor + ZOOM_STEP * rotation)
                if isinstance(cam, PiCam):
                    cam.set_zoom(zoom_factor)
                encoder_message = f"Zoom: {zoom_factor:.1f}x"
                encoder_timer = 1.0
            elif button_pressed:
                zoom_factor = 1.0
                if isinstance(cam, PiCam):
                    cam.set_zoom(zoom_factor)
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
                (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
                x = (FRAME_WIDTH - tw) // 2
                y = y0 + i * (th + 10)
                cv2.putText(frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

            if encoder_timer > 0:
                encoder_timer -= 0.01
            else:
                encoder_message = ""

            display.show(frame)
            sleep(0.01)

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        if cam and hasattr(cam, "stop"):
            cam.stop()
        display.close()


if __name__ == "__main__":
    main()
