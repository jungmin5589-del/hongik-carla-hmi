"""Validate stream structure every frame and decoded RGB on periodic audits."""
import io
from PIL import Image


def validate_jpeg(data,expected_size,full_decode=False):
    if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
        raise ValueError('Renderer returned an incomplete JPEG frame.')
    with Image.open(io.BytesIO(data)) as image:
        if image.format!='JPEG' or image.size!=tuple(expected_size):
            raise ValueError('Renderer returned an unexpected frame format or size.')
        if full_decode:image.load()
        return image.size
