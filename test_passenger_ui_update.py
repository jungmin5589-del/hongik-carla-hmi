import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from apply_passenger_ui import apply,ROOT,FILES

class UpdateTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup)
  self.live=Path(self.t.name)/'live';self.live.mkdir()
  self.native='FIELD CONTROL = unchanged\n<main><p><a href="/experiment">AI OFF / ON experiment</a></p>'
  (self.live/'native_carla.py').write_text(self.native)
  (self.live/'navigation_adapter.py').write_text("# field adapter\npath.endswith(('.js', '.woff2'))")
  for name in ('vehicle_following.py','motion_link.py','lab.local.json'):(self.live/name).write_text('FIELD PATCH')
  server=self.live.parent/'data-server-py';server.mkdir();(server/'sixdof_rs.pyd').write_bytes(b'FIELD RUST BUILD')
 def test_dry_run_and_application_preserve_field_control_and_dll(self):
  report=apply(self.live);self.assertTrue(report['check'])
  self.assertEqual((self.live/'native_carla.py').read_text(),self.native)
  with patch('apply_passenger_ui.socket.socket') as s:
   s.return_value.__enter__.return_value.connect_ex.return_value=1
   report=apply(self.live,True)
  self.assertTrue(report['protected_unchanged'])
  self.assertIn('FIELD CONTROL = unchanged',(self.live/'native_carla.py').read_text())
  self.assertEqual((self.live.parent/'data-server-py/sixdof_rs.pyd').read_bytes(),b'FIELD RUST BUILD')
  for name in ('vehicle_following.py','motion_link.py','lab.local.json'):self.assertEqual((self.live/name).read_text(),'FIELD PATCH')
  for name in FILES:self.assertEqual((self.live/name).read_bytes(),(ROOT/name).read_bytes())
  self.assertEqual(apply(self.live)['changed'],[])
  self.assertEqual((Path(report['backup'])/'native_carla.py').read_text(),self.native)
 def test_unknown_adapter_stops_before_writing_anything(self):
  (self.live/'navigation_adapter.py').write_text('unknown field version')
  with self.assertRaises(ValueError):apply(self.live,True)
  self.assertFalse((self.live/'course_ui').exists())
 def test_running_app_blocks_writes(self):
  with patch('apply_passenger_ui.socket.socket') as s:
   s.return_value.__enter__.return_value.connect_ex.return_value=0
   with self.assertRaises(RuntimeError):apply(self.live,True)
  self.assertFalse((self.live/'course_ui').exists())

if __name__=='__main__':unittest.main()
