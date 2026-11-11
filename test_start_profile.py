import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from start_profile import plan,run

class ProfileTests(unittest.TestCase):
    def test_laptop_never_enables_motion(self):
        p=plan('laptop');self.assertTrue(p['preview']);self.assertFalse(p['motion'])
    def test_motion_profile_uses_original_packet_and_ports(self):
        p=plan('motion');self.assertFalse(p['preview']);self.assertTrue(p['motion'])
        self.assertEqual(p['environment']['SIXDOF_UDP_PORT'],'10000')
        self.assertEqual(p['environment']['SIXDOF_PACKET'],'legacy')
    def test_check_never_launches_or_changes_environment(self):
        before=dict(os.environ)
        with patch('lab_one_click.run') as launch:run('motion',check=True);launch.assert_not_called()
        self.assertEqual(dict(os.environ),before)
    def test_explicit_local_receiver_is_preserved(self):
        with patch.dict(os.environ,{'SIXDOF_UDP_HOST':'192.0.2.20'}),patch('lab_one_click.run') as launch:
            run('laptop');self.assertEqual(os.environ['SIXDOF_UDP_HOST'],'192.0.2.20')
            self.assertFalse(launch.call_args.kwargs['motion'])
    def test_shared_camera_values_precede_local_overrides(self):
        import lab_settings
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'settings').mkdir()
            (root/'settings/lab-shared.json').write_text(json.dumps({'fov':70,'fps':25}))
            (root/'lab.local.json').write_text(json.dumps({'fov':72}))
            with patch.object(lab_settings,'ROOT',root):cfg=lab_settings.settings()
            self.assertEqual(cfg['fov'],72);self.assertEqual(cfg['fps'],25)
