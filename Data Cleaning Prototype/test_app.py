import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
class AppTests(unittest.TestCase):
 def test_summary_and_clickable_plan(self):
  app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=30).run()
  self.assertEqual(len(app.exception),0)
  next(b for b in app.button if b.label=='Profile and propose plan').click().run()
  self.assertNotIn('run',app.session_state)
  next(a for a in app.text_area if a.label.startswith('Study objectives')).set_value('Study age and healthcare costs')
  next(b for b in app.button if b.label=='Profile and propose plan').click().run()
  self.assertEqual(len(app.exception),0)
  self.assertTrue(any('affected_cells_estimate' in df.value.columns for df in app.dataframe))
  self.assertTrue(any('Selected action' in df.value.columns for df in app.dataframe))
  run=app.session_state['run'];self.assertEqual(run['graph'].get_state(run['config']).values['audit'],[])
  next(b for b in app.button if b.label=='Apply selected actions').click().run()
  self.assertEqual(len(app.exception),0)
  self.assertEqual(run['graph'].get_state(run['config']).values['rows'],run['graph'].get_state(run['config']).values['original'])
if __name__=='__main__':unittest.main()
