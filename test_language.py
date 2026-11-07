"""English copy completeness, safe audio lookup and unchanged control IDs."""
import json
import re
import unittest
from english_locale import catalog,COPY,OPTIONS
from english_voice import TEXTS,ALIASES,audio_path
from midterm_study import COPY as KO_COPY,OPTIONS as KO_OPTIONS
from navigation_adapter import static_asset,navigation_html

class LanguageTests(unittest.TestCase):
    def test_every_scenario_and_option_has_reviewed_english(self):
        pack=catalog()['strings']
        self.assertEqual(set(COPY),set(KO_COPY));self.assertEqual(set(OPTIONS),set(KO_OPTIONS))
        for profile,copy in KO_COPY.items():
            for phrase in copy:self.assertFalse(re.search('[가-힣]',pack[phrase]))
        for profile,options in KO_OPTIONS.items():
            self.assertEqual(len(options),len(OPTIONS[profile]))
            for option in options:
                self.assertNotEqual(pack[option['label']],option['label']);self.assertNotEqual(pack[option['detail']],option['detail'])
                self.assertTrue(option['action'].startswith('study_'))

    def test_english_recordings_cover_ai_and_exterior_dialogue(self):
        for key in ('night','fog','blockade','city_carpool','city_yield','city_rattle','city_cargo','yield_notice','city_taxi_call','city_taxi_answer'):
            self.assertIn(key,TEXTS);self.assertFalse(re.search('[가-힣]',TEXTS[key][0]))
        self.assertEqual(ALIASES['yield'],'city_yield')

    def test_catalog_is_plain_display_data_without_private_runtime_material(self):
        payload,kind=static_asset('/api/language/en');pack=json.loads(payload)
        self.assertIn('application/json',kind);self.assertEqual(pack['language'],'en')
        for entry in pack['voices'].values():
            if entry['url']:self.assertTrue(entry['url'].startswith('/api/english-audio/'))
            self.assertNotIn('filename',entry)

    def test_invalid_audio_names_are_rejected(self):
        for key in ('../manifest','../../secret','night.wav','city_taxi_call/../normal','unknown'):
            with self.assertRaises(ValueError):audio_path(key)

    def test_cockpit_keeps_original_layout_and_adds_one_language_bootstrap(self):
        markup=navigation_html().decode()
        for marker in ('id="scene"','id="navigation-map"','class="music-dock"','id="temperature"'):
            self.assertIn(marker,markup)
        self.assertEqual(markup.count('src="/language.js"'),1)

if __name__=='__main__':unittest.main()
