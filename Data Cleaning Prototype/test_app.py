import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
class AppTests(unittest.TestCase):
 def test_objective_required_and_complete_demo_flow(self):
  app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=30).run()
  self.assertEqual(len(app.exception),0)
  next(b for b in app.button if b.label=='Create project').click().run()
  self.assertNotIn('project',app.session_state)
  app.text_area[0].set_value('Assess age and costs, accounting for repeated events.')
  next(b for b in app.button if b.label=='Create project').click().run()
  next(b for b in app.button if b.label=='Read files').click().run()
  self.assertEqual(len(app.exception),0)
  self.assertEqual(len(app.session_state['tables']),3)
  app.checkbox[0].check().run()
  next(b for b in app.button if b.label=='Apply missing decisions').click().run()
  self.assertEqual(len(app.exception),0)
  next(b for b in app.button if b.label=='Confirm duplicate decisions').click().run()
  self.assertEqual(len(app.exception),0)
  next(b for b in app.button if b.label=='Confirm outlier decisions').click().run()
  self.assertEqual(len(app.exception),0)
  table=next(iter(app.session_state['tables'].values()))
  self.assertEqual(table['stage'],6)
  self.assertEqual(len(table['rows']),500)
  self.assertEqual(table['audit'],[])
  next(b for b in app.button if b.label=='New project').click().run()
  self.assertNotIn('project',app.session_state)
if __name__=='__main__': unittest.main()
