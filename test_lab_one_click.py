import os,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from lab_one_click import run

class OneClickTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.bundle=Path(self.temp.name);self.root=self.bundle/'live';self.root.mkdir();self.runner=Mock()
    def tearDown(self):self.temp.cleanup()
    def test_missing_bundle_never_launches_any_program(self):
        with self.assertRaisesRegex(RuntimeError,'complete portable'):run(self.root,runner=self.runner)
        self.runner.assert_not_called()
    def test_first_run_sets_up_before_launching_welcome(self):
        (self.bundle/'CARLA_0.9.16.zip').write_bytes(b'fixture')
        run(self.root,runner=self.runner)
        calls=self.runner.call_args_list
        self.assertEqual(Path(calls[0].args[0][1]).name,'setup_lab.py')
        self.assertEqual(Path(calls[1].args[0][1]).name,'launch_lab.py');self.assertIn('--welcome',calls[1].args[0])
    def test_initialized_folder_is_checked_without_reextracting(self):
        engine=self.bundle/'CARLA_0.9.16';engine.mkdir();(engine/'.hongik-engine-ready').write_text('ready')
        run(self.root,preview=True,runner=self.runner)
        calls=self.runner.call_args_list
        self.assertEqual(Path(calls[0].args[0][1]).name,'lab_preflight.py');self.assertIn('--preview',calls[1].args[0])
    def test_failed_preflight_never_continues_to_launch(self):
        engine=self.bundle/'CARLA_0.9.16';engine.mkdir();(engine/'.hongik-engine-ready').write_text('ready')
        self.runner.side_effect=RuntimeError('failed')
        with self.assertRaises(RuntimeError):run(self.root,runner=self.runner)
        self.assertEqual(self.runner.call_count,1)
    def test_read_only_check_does_not_extract_or_launch(self):
        run(self.root,check=True,runner=self.runner)
        self.assertEqual(self.runner.call_count,1);self.assertEqual(Path(self.runner.call_args.args[0][1]).name,'lab_preflight.py')
    def test_native_stop_and_start_choose_the_same_portable_engine(self):
        from launch_native_carla import engine_path
        engine=self.bundle/'CARLA_0.9.16';engine.mkdir();(engine/'CarlaUE4.exe').write_bytes(b'fixture')
        with patch.dict(os.environ,{},clear=True):self.assertEqual(engine_path(self.root),engine)
        with patch.dict(os.environ,{'CARLA_ROOT':str(self.bundle/'explicit-engine')}):
            self.assertEqual(engine_path(self.root),self.bundle/'explicit-engine')

if __name__=='__main__':unittest.main()
