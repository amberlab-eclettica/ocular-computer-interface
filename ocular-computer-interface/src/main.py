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

# Map switch positions to camera modes
SWITCH_CAMERA_MAP = {
    1: "picam",
    2: "picam_noir",
    3: "thermal"
}

def create_camera(mode):
    if mode == "thermal":
        return ThermalCam(width=FRAME_WIDTH//2, height=FRAME_HEIGHT)
    else:
        camera_num = 0 if mode == "picam_noir" else 1
        for attempt in range(3):
            try:
                return PiCam(camera_num=camera_num, width=FRAME_WIDTH, height=FRAME_HEIGHT)
            except RuntimeError as e:
                print(f"Failed to open camera, retrying... ({attempt+1}/3)")
                time.sleep(0.1)
        raise RuntimeError(f"Unable to open camera {mode}")

def main():
    display = StereoDisplay(width=FRAME_WIDTH, height=FRAME_HEIGHT, border_px=BORDER_PX)

    current_mode = None
    cam = None
    encoder_message = ""
    encoder_timer = 0  # seconds remaining to show the encoder action

    try:
        while True:
            # --- Check switch position ---
            switch_pos = get_position()
            if switch_pos in SWITCH_CAMERA_MAP:
                selected_mode = SWITCH_CAMERA_MAP[switch_pos]
                if selected_mode != current_mode:
                    print(f"Switching camera to: {selected_mode}")
                    if cam and hasattr(cam, "stop"):
                        cam.stop()
                        cam = None
                    cam = create_camera(selected_mode)
                    current_mode = selected_mode

            if not cam:
                sleep(0.1)
                continue

            frame = cam.capture()

            # --- Encoder handling ---
            rotation = get_rotation()
            button_pressed = is_pressed()

            if rotation != 0:
                step = 0.1
                cam.set_zoom(cam.zoom_factor + step * rotation)

                encoder_message = f"Zoom: {cam.zoom_factor:.1f}x"
                encoder_timer = 1.0

            elif button_pressed:
                # Reset zoom on button press (for PiCam)
                if isinstance(cam, PiCam):
                    cam.set_zoom(1.0)
                    encoder_message = "Zoom reset"
                else:
                    encoder_message = "Encoder button pressed"
                encoder_timer = 1.0

            # --- Prepare overlay text ---
            text_lines = []
            if switch_pos:
                text_lines.append(f"Switch: {switch_pos}")
            if encoder_timer > 0:
                text_lines.append(encoder_message)

            # Overlay text in the center
            y0 = FRAME_HEIGHT // 2 - (len(text_lines) * 20)
            for i, line in enumerate(text_lines):
                (text_w, text_h), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
                x = (FRAME_WIDTH - text_w) // 2
                y = y0 + i * (text_h + 10)
                cv2.putText(frame, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

            # Decrease encoder timer
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
