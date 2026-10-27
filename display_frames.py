"""Frame transport and exact-pixel presentation cache; no interpolation."""
import io
import pygame


def mjpeg_frames(response):
    while True:
        line = response.readline()
        if not line:
            return
        if not line.startswith(b'--frame'):
            continue
        headers = {}
        while True:
            line = response.readline()
            if not line:
                raise ValueError('Incomplete frame header')
            if line in (b'\r\n', b'\n'):
                break
            key, value = line.decode('ascii').split(':', 1)
            headers[key.lower()] = value.strip()
        size = int(headers['content-length'])
        if not 0 < size <= 32 * 1024 * 1024:
            raise ValueError('Invalid frame length')
        data = response.read(size)
        if len(data) != size:
            raise ValueError('Incomplete frame')
        yield data


class CachedFrame:
    def __init__(self):
        self.jpeg = self.frame = self.scaled = self.scaled_size = None
        self.decodes = self.scales = 0

    def surface(self, jpeg, viewport):
        if jpeg is not None and jpeg is not self.jpeg and jpeg != self.jpeg:
            self.frame = pygame.image.load(io.BytesIO(jpeg)).convert()
            self.jpeg = jpeg
            self.scaled = None
            self.decodes += 1
        if self.frame is None:
            return None
        ratio = min(viewport[0] / self.frame.get_width(), viewport[1] / self.frame.get_height())
        size = (round(self.frame.get_width() * ratio), round(self.frame.get_height() * ratio))
        if self.scaled is None or self.scaled_size != size:
            # Keep the same scaling algorithm and pixels as the original display.
            self.scaled = pygame.transform.smoothscale(self.frame, size)
            self.scaled_size = size
            self.scales += 1
        return self.scaled
