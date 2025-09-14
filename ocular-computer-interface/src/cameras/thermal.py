import board
import busio
import numpy as np
import adafruit_mlx90640
import cv2

class ThermalCam:
    def __init__(self, width=800, height=480):
        i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
        self.mlx = adafruit_mlx90640.MLX90640(i2c)
        self.mlx.refresh_rate = adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
        self.frame = np.zeros((24*32,))
        self.width = width
        self.height = height

    def capture(self):
        while True:
            try:
                self.mlx.getFrame(self.frame)
                break
            except ValueError:
                continue
        img = np.reshape(self.frame, (24, 32))
        norm = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        norm = 255 - norm
        colormap = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)
        corrected = cv2.flip(colormap, 1)  # Fix left-right inversion
        return cv2.resize(corrected, (self.width, self.height), interpolation=cv2.INTER_NEAREST)
