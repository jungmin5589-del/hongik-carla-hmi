import unittest
from repo_safety import allowed,check_content

class PublicationChecks(unittest.TestCase):
    def test_runtime_and_external_data_are_never_approved(self):
        for path in ['vendor/nre/serve.py','source/model.usdz','cache/voice.wav','validation/frame.jpg','backups/old.py',
                     'mobile-state.json','secrets/vapid.key','.env','serve-reference.py','../other.py','course_ui/vendor/unapproved.bin']:
            self.assertFalse(allowed(path),path)
    def test_owned_sources_and_explicit_licensed_dependencies_are_allowed(self):
        for path in ['fog_trial.py','settings/scenarios.json','docs/SETUP.md','course_ui/index.html','course_ui/vendor/three.module.js']:
            self.assertTrue(allowed(path),path)
    def test_embedded_proprietary_source_and_private_keys_are_rejected(self):
        for data in [b'# SPDX-License-Identifier: LicenseRef-NvidiaProprietary\n',b'-----BEGIN PRIVATE KEY-----\nexample']:
            with self.assertRaises(ValueError):check_content('example.py',data)

if __name__=='__main__':unittest.main()
