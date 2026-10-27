import io
import unittest
from PIL import Image
from frame_validation import validate_jpeg


class JPEGValidationTests(unittest.TestCase):
    def image(self):
        stream=io.BytesIO();Image.new('RGB',(128,72),(40,90,190)).save(stream,format='JPEG')
        return stream.getvalue()
    def test_header_and_full_audit_keep_the_exact_encoded_frame(self):
        data=self.image();original=bytes(data)
        for full in (False,True):self.assertEqual(validate_jpeg(data,(128,72),full),(128,72))
        self.assertEqual(data,original)
    def test_wrong_dimensions_missing_end_marker_and_non_jpeg_are_rejected(self):
        data=self.image()
        for value,size in [(data,(640,360)),(data[:-2],(128,72)),(b'not an image',(128,72))]:
            with self.assertRaises(ValueError):validate_jpeg(value,size)


if __name__=='__main__':unittest.main()
