from picamera2 import Picamera2
from time import sleep
import cv2

class PiCam:
    def __init__(self, camera_num=0, width=800, height=480):
        self.picam = Picamera2(camera_num=camera_num)

        # Full sensor dimensions (IMX708)
        self.sensor_width, self.sensor_height = 4608, 2592

        self.config = self.picam.create_preview_configuration(
            main={"size": (width, height), "format": "RGB888"},
            raw={"size": (self.sensor_width, self.sensor_height)}
        )

        # Start with full sensor crop
        self.config["controls"]["ScalerCrop"] = (
            0, 0, self.sensor_width, self.sensor_height
        )

        self.picam.configure(self.config)
        self.picam.start()
        sleep(0.2)

        # Keep track of zoom level
        self.zoom_factor = 1.0  # 1.0 = no zoom

    def set_zoom(self, factor: float):
        """Set digital zoom factor (1.0 = full FOV)."""
        if factor < 1.0:
            factor = 1.0
        if factor > 8.0:  # safety limit
            factor = 8.0
        self.zoom_factor = factor

        crop_w = int(self.sensor_width / factor)
        crop_h = int(self.sensor_height / factor)
        crop_x = (self.sensor_width - crop_w) // 2
        crop_y = (self.sensor_height - crop_h) // 2

        self.picam.set_controls({
            "ScalerCrop": (crop_x, crop_y, crop_w, crop_h)
        })

    def capture(self):
        frame = self.picam.capture_array()
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def stop(self):
        try:
            self.picam.stop()
            self.picam.close()
        except Exception as e:
            print(f"Error closing PiCam: {e}")
