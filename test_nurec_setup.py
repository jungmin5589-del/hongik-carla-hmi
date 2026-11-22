"""Installation logic fixtures only; no real OS features or WSL are installed."""
import os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
import nurec_environment as env
import setup_nurec_lab as setup
import deploy_nurec_option as deployment

class EnvironmentTests(unittest.TestCase):
    def test_existing_matching_vhd_selects_its_actual_distribution_name(self):
        with tempfile.TemporaryDirectory() as folder:
            vhd=Path(folder)/'ext4.vhdx';vhd.write_bytes(b'fixture')
            with patch.dict(os.environ,{},clear=True),patch.object(env,'vhd_path',return_value=vhd),patch.object(env,'distributions',return_value=[dict(name='UnrelatedUbuntu',vhd=str(vhd.with_name('other.vhdx'))),dict(name='Hongik-NuRec22',vhd=str(vhd))]):
                self.assertEqual(env.distro_name(True),'Hongik-NuRec22')

    def test_unrelated_ubuntu_is_not_used_just_because_its_name_matches(self):
        with patch.dict(os.environ,{},clear=True),patch.object(env,'vhd_path',return_value=Path('E:/our/ext4.vhdx')),patch.object(env,'distributions',return_value=[dict(name='Ubuntu-22.04',vhd='C:/unrelated/ext4.vhdx')]):
            with self.assertRaisesRegex(FileNotFoundError,'66_NUREC_SETUP'):env.distro_name(True)

    def test_per_pc_config_does_not_write_into_the_shared_source(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'pc/nurec-setup.json'
            with patch.object(env,'CONFIG',path):
                env.save(dict(distro='one'));env.save(dict(distro='two'))
                self.assertEqual(env.config()['distro'],'two')
                self.assertEqual(len(list(path.parent.glob('*.backup'))),1)

class SetupTests(unittest.TestCase):
    def test_stop_does_not_terminate_an_unrelated_wsl_distribution(self):
        import stop_nurec_lab as stopping
        with patch.object(stopping,'data_root',return_value=Path('E:/models')),patch.object(stopping,'drive_state',return_value=None),patch.object(stopping,'distro_name',return_value='other'),patch.object(stopping,'distributions',return_value=[dict(name='other',vhd='C:/other/ext4.vhdx')]),patch.object(stopping,'vhd_path',return_value=Path('E:/ours/ext4.vhdx')),patch.object(stopping.subprocess,'run') as command:
            with self.assertRaisesRegex(RuntimeError,'종료하지'):stopping.main()
            command.assert_not_called()

    def test_stop_leaves_native_carla_running(self):
        import stop_nurec_lab as stopping
        with patch.object(stopping,'data_root',return_value=Path('E:/models')),patch.object(stopping,'drive_state',return_value=dict(kind='hongik-native-carla')),patch.object(stopping,'stop_nurec') as stop:
            with self.assertRaisesRegex(RuntimeError,'그대로'):stopping.main()
            stop.assert_not_called()

    def test_existing_valid_python_is_reused_without_pip_or_copy(self):
        with patch.object(setup,'python_path',return_value=Path('existing/python.exe')),patch.object(setup,'probe_python',return_value={}),patch.object(setup.shutil,'copytree') as copying,patch.object(setup,'run') as commands:
            self.assertEqual(setup.prepare_python(Path('root')),Path('existing/python.exe'));copying.assert_not_called();commands.assert_not_called()

    def test_existing_matching_distribution_is_not_registered_twice(self):
        with patch.object(setup,'distro_name',return_value='original'),patch.object(setup,'run') as commands:
            self.assertEqual(setup.prepare_distribution(Path('root')),'original');commands.assert_not_called()

    def test_name_conflict_does_not_unregister_or_overwrite_any_distribution(self):
        with tempfile.TemporaryDirectory() as folder:
            vhd=Path(folder)/'ext4.vhdx';vhd.write_bytes(b'fixture')
            with patch.object(setup,'distro_name',side_effect=FileNotFoundError),patch.object(setup,'vhd_path',return_value=vhd),patch.object(setup,'distributions',return_value=[dict(name='Hongik-NuRec22')]),patch.object(setup,'run') as command:
                with self.assertRaisesRegex(RuntimeError,'변경하지'):setup.prepare_distribution(Path(folder))
                command.assert_not_called()

    def test_new_lab_registration_uses_import_in_place_only(self):
        with tempfile.TemporaryDirectory() as folder:
            vhd=Path(folder)/'ext4.vhdx';vhd.write_bytes(b'fixture')
            with patch.object(setup,'distro_name',side_effect=FileNotFoundError),patch.object(setup,'vhd_path',return_value=vhd),patch.object(setup,'distributions',return_value=[]),patch.object(setup,'run',return_value=NS(returncode=0)) as command:
                self.assertEqual(setup.prepare_distribution(Path(folder)),'Hongik-NuRec22')
                self.assertEqual(command.call_args.args[0],['wsl.exe','--import-in-place','Hongik-NuRec22',vhd])

    def test_no_ssd_check_never_launches_or_installs_anything(self):
        with patch.object(setup,'data_root',side_effect=FileNotFoundError('SSD missing')),patch.object(setup,'run') as command,patch.object(setup,'save') as saving:
            report=setup.inspect();self.assertFalse(report['environment_ready']);self.assertFalse(report['motion_enabled']);command.assert_not_called();saving.assert_not_called()

    def test_deployment_converts_only_shell_scripts_to_lf_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';target=root/'target';source.mkdir();target.mkdir()
            (source/'serve.sh').write_bytes(b'set -euo pipefail\r\necho ready\r\n');(target/'serve.sh').write_bytes(b'original\r\n')
            with patch.object(deployment,'ROOT',source):
                self.assertEqual(deployment.deploy(target,['serve.sh']),1)
                self.assertEqual((target/'serve.sh').read_bytes(),b'set -euo pipefail\necho ready\n')
                self.assertEqual(deployment.deploy(target,['serve.sh']),0)
            self.assertEqual(next((target/'backups').glob('*/serve.sh')).read_bytes(),b'original\r\n')

if __name__=='__main__':unittest.main()
