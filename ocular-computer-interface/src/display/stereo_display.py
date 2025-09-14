import numpy as np
import os
import cv2

class StereoDisplay:
    def __init__(self, width=800, height=480, border_px=10):
        self.width = width
        self.height = height
        self.border_px = border_px
        self.fb0 = os.open("/dev/fb0", os.O_RDWR)

        # Precompute barrel distortion
        half_w = width // 2
        half_h = height
        self.map_x, self.map_y = self._create_barrel_map(half_w, half_h)

    def _create_barrel_map(self, width, height, k1=-0.25, k2=0.0):
        x = np.linspace(-1, 1, width)
        y = np.linspace(-1, 1, height)
        xv, yv = np.meshgrid(x, y)
        r = np.sqrt(xv**2 + yv**2)
        r_distorted = r * (1 + k1*r**2 + k2*r**4)
        r[r == 0] = 1e-6
        map_x = ((xv * r_distorted / r + 1) * (width-1)/2).astype(np.float32)
        map_y = ((yv * r_distorted / r + 1) * (height-1)/2).astype(np.float32)
        return map_x, map_y

    def _rgb888_to_rgb565(self, image):
        r = (image[:,:,0] >> 3).astype(np.uint16)
        g = (image[:,:,1] >> 2).astype(np.uint16)
        b = (image[:,:,2] >> 3).astype(np.uint16)
        return ((r << 11) | (g << 5) | b).astype('<u2')

    def show(self, frame):
        half_w = self.width // 2
        half_h = self.height

        # Resize and apply distortion
        half_frame = cv2.resize(frame, (half_w, half_h))
        corrected = cv2.remap(half_frame, self.map_x, self.map_y, interpolation=cv2.INTER_LINEAR)

        # Thin black border
        b = self.border_px
        corrected[:b,:,:] = 0
        corrected[-b:,:,:] = 0
        corrected[:,:b,:] = 0
        corrected[:,-b:,:] = 0

        # Stereo duplication
        stereo_frame = np.concatenate((corrected, corrected), axis=1)

        fb_frame = self._rgb888_to_rgb565(stereo_frame)
        os.lseek(self.fb0, 0, os.SEEK_SET)
        os.write(self.fb0, fb_frame.tobytes())

    def close(self):
        os.close(self.fb0)
