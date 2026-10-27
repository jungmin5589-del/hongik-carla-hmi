"""Validate pixel-preserving caching and the camera-safe simulation setting."""
import copy
import io
import os
import unittest
from types import SimpleNamespace

os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
from PIL import Image, ImageDraw
from display_frames import CachedFrame, mjpeg_frames
from rendering_mode import enable_physics_only, renderer_is_nrend, renderer_matches


def jpeg(color):
    image = Image.new('RGB', (320,180), color)
    ImageDraw.Draw(image).rectangle((23,17,171,139),fill=(217,39,86))
    output=io.BytesIO();image.save(output,format='JPEG',quality=95)
    return output.getvalue()


class PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.display.init();pygame.display.set_mode((1,1))
    @classmethod
    def tearDownClass(cls):
        pygame.display.quit()
    def test_repeated_identical_download_does_not_decode_or_scale_again(self):
        data=jpeg((12,75,121));cache=CachedFrame()
        actual=cache.surface(data,(1280,720))
        expected=pygame.transform.smoothscale(pygame.image.load(io.BytesIO(data)).convert(),(1280,720))
        self.assertEqual(pygame.image.tobytes(actual,'RGB'),pygame.image.tobytes(expected,'RGB'))
        for _ in range(30):
            self.assertIs(cache.surface(bytes(bytearray(data)),(1280,720)),actual)
        self.assertEqual((cache.decodes,cache.scales),(1,1))
    def test_new_image_and_resize_invalidate_only_the_required_cache(self):
        cache=CachedFrame();a=jpeg((12,75,121));b=jpeg((99,177,29))
        first=pygame.image.tobytes(cache.surface(a,(640,360)),'RGB')
        second=cache.surface(b,(640,360))
        self.assertNotEqual(first,pygame.image.tobytes(second,'RGB'))
        resized=cache.surface(b,(800,600))
        self.assertEqual(resized.get_size(),(800,450))
        expected=pygame.transform.smoothscale(pygame.image.load(io.BytesIO(b)).convert(),(800,450))
        self.assertEqual(pygame.image.tobytes(resized,'RGB'),pygame.image.tobytes(expected,'RGB'))
        self.assertEqual((cache.decodes,cache.scales),(2,3))
    def test_stream_delivers_frames_and_rejects_truncated_data(self):
        data=jpeg((12,75,121))
        part=b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(data)).encode()+b'\r\n\r\n'+data+b'\r\n'
        self.assertEqual(list(mjpeg_frames(io.BytesIO(part+part))),[data,data])
        with self.assertRaises(ValueError):
            list(mjpeg_frames(io.BytesIO(part[:-30])))


class FakeWorld:
    def __init__(self,actors=()):
        self.settings=SimpleNamespace(no_rendering_mode=False,synchronous_mode=False,fixed_delta_seconds=None,substepping=True)
        self.actors=actors;self.calls=0
    def get_settings(self):return copy.copy(self.settings)
    def get_actors(self):return self.actors
    def apply_settings(self,value):self.settings=copy.copy(value);self.calls+=1


class RenderingTests(unittest.TestCase):
    def test_forced_gsplat_cannot_silently_reuse_a_different_renderer(self):
        self.assertTrue(renderer_matches({'renderer':'gsplat'},'gsplat'))
        self.assertTrue(renderer_matches({'use_gsplat':'True'},'gsplat'))
        self.assertFalse(renderer_matches({'renderer':'default'},'gsplat'))
        self.assertFalse(renderer_matches({'renderer':'gsplat'},'trained'))
        self.assertFalse(renderer_matches({'renderer':'nrend'},'gsplat'))
        self.assertTrue(renderer_matches({'renderer':'default'},'trained'))
        self.assertTrue(renderer_matches({'renderer':'gsplat','nurec_private_camera_mode':'native'},'gsplat-native'))
        self.assertFalse(renderer_matches({'renderer':'gsplat'},'gsplat-native'))
    def test_current_and_legacy_server_config_identify_the_backend(self):
        self.assertTrue(renderer_is_nrend({'renderer':'nrend'}))
        self.assertTrue(renderer_is_nrend({'enable_nrend':'True'}))
        self.assertFalse(renderer_is_nrend({'renderer':'default','enable_nrend':'True'}))
        self.assertFalse(renderer_is_nrend({'renderer':'gsplat'}))
    def test_only_background_drawing_changes_and_previous_value_is_returned(self):
        world=FakeWorld();before=copy.copy(world.settings)
        self.assertFalse(enable_physics_only(world))
        self.assertTrue(world.settings.no_rendering_mode)
        for key in ('synchronous_mode','fixed_delta_seconds','substepping'):
            self.assertEqual(getattr(world.settings,key),getattr(before,key))
        self.assertTrue(enable_physics_only(world));self.assertEqual(world.calls,1)
    def test_gpu_camera_and_synchronous_world_are_left_untouched(self):
        camera=FakeWorld([SimpleNamespace(type_id='sensor.camera.rgb')])
        with self.assertRaises(RuntimeError):enable_physics_only(camera)
        self.assertFalse(camera.settings.no_rendering_mode);self.assertEqual(camera.calls,0)
        sync=FakeWorld();sync.settings.synchronous_mode=True
        with self.assertRaises(RuntimeError):enable_physics_only(sync)
        self.assertEqual(sync.calls,0)


if __name__=='__main__':unittest.main()
