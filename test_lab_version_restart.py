import unittest
from launch_lab import restart_required
class RestartTests(unittest.TestCase):
    def test_old_idle_app_is_restarted_without_manual_stop(self):
        self.assertTrue(restart_required({'mode':'paused','lab_rig':True},True))
    def test_active_old_drive_is_not_interrupted(self):
        with self.assertRaises(RuntimeError):restart_required({'mode':'auto','scenario':{'completed':False}},True)
    def test_current_matching_app_is_reused(self):
        self.assertFalse(restart_required({'runtime_revision':'20261111-r3','lab_rig':True,'motion':{'enabled':True}},True))
