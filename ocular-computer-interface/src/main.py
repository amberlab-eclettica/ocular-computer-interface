import time
from time import sleep
import cv2

from cameras.picam import PiCam
from cameras.thermal import ThermalCam
from display.stereo_display import StereoDisplay

from controls.switch import get_position
from controls.rotary import get_rotation, is_pressed

# --- SETTINGS ---
FRAME_WIDTH = 800
FRAME_HEIGHT = 480
BORDER_PX = 10

ZOOM_STEP = 0.1   # per encoder tick
ENCODER_MESSAGE_TIME = 1.0  # seconds

# FOV (approximate, horizontal)
FOV_PICAM = 75
FOV_THERMAL = 55

# Overlay blend weights
OVERLAY_ALPHA_PICAM = 0.7
OVERLAY_ALPHA_THERMAL = 0.3

# Thermal smoothing
THERMAL_SMOOTHING = True
SMOOTHING_KERNEL = (5, 5)
SMOOTHING_SIGMA = 1.5

# Overlay performance
THERMAL_UPDATE_INTERVAL = 10  # update thermal once every N PiCam frames

# Debug overlay alignment
ALIGN_DEBUG = False

# Map switch positions to camera modes
SWITCH_CAMERA_MAP = {
    1: "picam",
    2: "picam_noir",
    3: "thermal",
    4: "overlay_picam",       # PiCam + Thermal overlay
    5: "overlay_picam_noir"   # PiCam NoIR + Thermal overlay
}


def smooth_thermal(frame):
    if THERMAL_SMOOTHING:
        return cv2.GaussianBlur(frame, SMOOTHING_KERNEL, SMOOTHING_SIGMA)
    return frame


def overlay_thermal_on_picam(frame_picam, frame_thermal):
    """Resize + align thermal to match PiCam FOV before overlay."""
    h, w, _ = frame_picam.shape

    # Scale factor (thermal FOV is smaller → shrink thermal image)
    scale = FOV_THERMAL / FOV_PICAM
    new_w = int(frame_thermal.shape[1] * scale)
    new_h = int(frame_thermal.shape[0] * scale)
    thermal_scaled = cv2.resize(frame_thermal, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Place thermal at center of PiCam frame
    y_start = (h - new_h) // 2
    x_start = (w - new_w) // 2
    thermal_overlay = frame_picam.copy()
    thermal_overlay[y_start:y_start+new_h, x_start:x_start+new_w] = cv2.addWeighted(
        frame_picam[y_start:y_start+new_h, x_start:x_start+new_w],
        OVERLAY_ALPHA_PICAM,
        thermal_scaled,
        OVERLAY_ALPHA_THERMAL,
        0,
    )

    if ALIGN_DEBUG:
        cv2.rectangle(thermal_overlay, (x_start, y_start), (x_start+new_w, y_start+new_h), (0,255,0), 2)

    return thermal_overlay


def create_camera(mode):
    if mode == "thermal":
        return ThermalCam(width=FRAME_WIDTH//2, height=FRAME_HEIGHT)

    elif mode in ("overlay_picam", "overlay_picam_noir"):
        camera_num = 0 if mode == "overlay_picam_noir" else 1
        return {
            "picam": PiCam(camera_num=camera_num, width=FRAME_WIDTH, height=FRAME_HEIGHT),
            "thermal": ThermalCam(width=FRAME_WIDTH, height=FRAME_HEIGHT)
        }

    else:  # picam / picam_noir
        camera_num = 0 if mode == "picam_noir" else 1
        for attempt in range(3):
            try:
                return PiCam(camera_num=camera_num, width=FRAME_WIDTH, height=FRAME_HEIGHT)
            except RuntimeError:
                print(f"Failed to open camera, retrying... ({attempt+1}/3)")
                time.sleep(0.1)
        raise RuntimeError(f"Unable to open camera {mode}")


def main():
    display = StereoDisplay(width=FRAME_WIDTH, height=FRAME_HEIGHT, border_px=BORDER_PX)

    current_mode = None
    cam = None
    encoder_message = ""
    encoder_timer = 0
    zoom_factor = 1.0
    frame_counter = 0
    last_thermal_frame = None

    try:
        while True:
            # --- Switch handling ---
            switch_pos = get_position()
            if switch_pos in SWITCH_CAMERA_MAP:
                selected_mode = SWITCH_CAMERA_MAP[switch_pos]
                if selected_mode != current_mode:
                    print(f"Switching camera to: {selected_mode}")
                    if cam:
                        if isinstance(cam, dict):
                            for c in cam.values():
                                if hasattr(c, "stop"): c.stop()
                        elif hasattr(cam, "stop"):
                            cam.stop()
                        cam = None
                    cam = create_camera(selected_mode)
                    current_mode = selected_mode

                    # Restore zoom
                    if isinstance(cam, PiCam):
                        cam.set_zoom(zoom_factor)
                    elif isinstance(cam, dict) and "picam" in cam:
                        cam["picam"].set_zoom(zoom_factor)

            if not cam:
                sleep(0.05)
                continue

            # --- Capture ---
            if isinstance(cam, PiCam):
                frame = cam.capture()

            elif isinstance(cam, ThermalCam):
                frame = smooth_thermal(cam.capture())

            elif isinstance(cam, dict):
                frame_picam = cam["picam"].capture()

                # update thermal frame only every N iterations
                if frame_counter % THERMAL_UPDATE_INTERVAL == 0 or last_thermal_frame is None:
                    last_thermal_frame = smooth_thermal(cam["thermal"].capture())

                frame = overlay_thermal_on_picam(frame_picam, last_thermal_frame)

            else:
                frame = None

            if frame is None:
                continue

            # --- Encoder handling ---
            rotation = get_rotation()
            button_pressed = is_pressed()

            if rotation != 0:
                zoom_factor = max(1.0, zoom_factor + ZOOM_STEP * rotation)
                if isinstance(cam, PiCam):
                    cam.set_zoom(zoom_factor)
                elif isinstance(cam, dict) and "picam" in cam:
                    cam["picam"].set_zoom(zoom_factor)

                encoder_message = f"Zoom: {zoom_factor:.1f}x"
                encoder_timer = ENCODER_MESSAGE_TIME

            elif button_pressed:
                zoom_factor = 1.0
                if isinstance(cam, PiCam):
                    cam.set_zoom(1.0)
                elif isinstance(cam, dict) and "picam" in cam:
                    cam["picam"].set_zoom(1.0)
                encoder_message = "Zoom reset"
                encoder_timer = ENCODER_MESSAGE_TIME

            # --- Overlay status text ---
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

            # --- Show ---
            display.show(frame)
            frame_counter += 1
            sleep(0.01)

    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        if cam:
            if isinstance(cam, dict):
                for c in cam.values():
                    if hasattr(c, "stop"): c.stop()
            elif hasattr(cam, "stop"):
                cam.stop()
        display.close()


if __name__ == "__main__":
    main()
