"""A stalled local service may recover; unrelated processes must remain untouched."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import open_mobile
from launch_live import can_reuse_drive
from profile_sources import source_id

class RecoveryTests(unittest.TestCase):
    def test_failed_renderer_is_not_reused_as_a_healthy_drive(self):
        state=dict(profile='congestion',scene_id=source_id('congestion'),phase='live',error=None)
        self.assertTrue(can_reuse_drive(state,'congestion'))
        self.assertFalse(can_reuse_drive(dict(state,phase='error'),'congestion'))
        self.assertFalse(can_reuse_drive(dict(state,error='Permission denied'),'congestion'))
        self.assertFalse(can_reuse_drive(state,'night'))
    def test_unrelated_process_is_not_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'mobile-process.json').write_text(json.dumps(dict(pid=123)))
            with patch.object(open_mobile,'ROOT',p),patch.object(open_mobile.subprocess,'check_output',return_value=b'other-app.exe'),patch.object(open_mobile.subprocess,'run') as run:
                with self.assertRaises(RuntimeError):open_mobile.stop_unhealthy_gateway()
                run.assert_not_called()
    def test_a_different_renderer_cannot_reuse_the_old_service(self):
        state=dict(profile='congestion',scene_id=source_id('congestion'),phase='live',error=None,renderer_backend='trained')
        self.assertFalse(can_reuse_drive(state,'congestion','nrend'))
        self.assertTrue(can_reuse_drive(dict(state,renderer_backend='nrend'),'congestion','nrend'))
    def test_only_verified_recorded_mobile_process_can_be_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'mobile-process.json').write_text(json.dumps(dict(pid=123)))
            cmd=('python.exe '+str(p/'mobile_gateway.py')).encode()
            with patch.object(open_mobile,'ROOT',p),patch.object(open_mobile.subprocess,'check_output',return_value=cmd),patch.object(open_mobile.subprocess,'run') as run:
                open_mobile.stop_unhealthy_gateway();self.assertEqual(run.call_args.args[0],['taskkill','/PID','123','/T','/F'])

if __name__=='__main__':unittest.main()
