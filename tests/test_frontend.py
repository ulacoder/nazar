import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class FrontendContractTests(unittest.TestCase):
    def test_session_navigation_and_localization(self):
        html=(ROOT/'app/templates/index.html').read_text(encoding='utf-8')
        js=(ROOT/'app/static/js/i18n.js').read_text(encoding='utf-8')
        self.assertNotIn('data-page="analytics"',html)
        self.assertIn('id="page-session-detail"',html)
        for name in ('overview','events','analytics','timelapse'):
            self.assertIn(f'data-detail-tab="{name}"',html)
        for locale in ('en','kk','ru'):
            block=js.split(f'Object.assign(translations.{locale}, {{',1)[1].split('});',1)[0]
            for key in ('metadata.teacher','metadata.proctor','metadata.startLesson','metadata.startExam',
                'detail.peopleOverTime','detail.byTrack','detail.noDurations'):
                self.assertIn(f'"{key}"',block)
        self.assertIn('css/session-detail.css',html)
        self.assertIn('brand-eye',html)

if __name__=='__main__': unittest.main()
