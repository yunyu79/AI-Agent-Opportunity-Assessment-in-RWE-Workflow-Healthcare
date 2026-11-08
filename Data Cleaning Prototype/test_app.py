import unittest
import tempfile
import os
from unittest.mock import patch
from pathlib import Path
from streamlit.testing.v1 import AppTest
class AppTests(unittest.TestCase):
 def setUp(self):
  self.directory=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{"CLEANING_PROJECT_DIR":self.directory.name});self.env.start()
 def tearDown(self):
  self.env.stop();self.directory.cleanup()
 def test_summary_and_clickable_plan(self):
  app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=30).run()
  self.assertEqual(len(app.exception),0)
  next(b for b in app.button if b.label=='Profile and propose plan').click().run()
  self.assertNotIn('run',app.session_state)
  next(a for a in app.text_area if a.label.startswith('Study objectives')).set_value('Study age and healthcare costs')
  next(b for b in app.button if b.label=='Profile and propose plan').click().run()
  self.assertEqual(len(app.exception),0)
  self.assertTrue(any('affected_cells_estimate' in df.value.columns for df in app.dataframe))
  self.assertTrue(any(b.label=='Retry LLM assessment' for b in app.button))
  self.assertTrue(next(b for b in app.button if b.label=='Apply selected actions').disabled)
  with patch('llm_review.explain_review',side_effect=lambda review,*args: {r['id']:{'reasons':'Evidence insufficient; assess mechanism.','suggested_plan':'MICE'} for r in review}):
   next(c for c in app.checkbox if c.label=='Allow this review context to be sent to OpenAI.').check().run()
   self.assertTrue(any(list(df.value.columns)==['Column name','Data issue','Reasons','Suggested plan','Action'] for df in app.dataframe))
  grid=next(df.value for df in app.dataframe if list(df.value.columns)==['Column name','Data issue','Reasons','Suggested plan','Action'])
  self.assertTrue((grid['Action']==grid['Suggested plan']).all())
  run=app.session_state['run'];self.assertEqual(run['graph'].get_state(run['config']).values['audit'],[])
  next(b for b in app.button if b.label=='Apply selected actions').click().run()
  self.assertEqual(len(app.exception),0)
  self.assertEqual(run['graph'].get_state(run['config']).values['rows'],run['graph'].get_state(run['config']).values['original'])
if __name__=='__main__':unittest.main()

class PersistenceUITests(AppTests):
 def test_reopen_and_close_project(self):
  path=str(Path(__file__).with_name('app.py'))
  app=AppTest.from_file(path,default_timeout=30).run()
  next(a for a in app.text_area if a.label.startswith('Study objectives')).set_value('Retain my study settings').run()
  next(b for b in app.button if b.label=='Profile and propose plan').click().run()
  token=app.query_params['project']
  again=AppTest.from_file(path,default_timeout=30)
  again.query_params['project']=token
  again.run()
  self.assertEqual(len(again.exception),0)
  self.assertEqual(again.session_state['study_objectives'],'Retain my study settings')
  run=again.session_state['run']
  self.assertEqual(run['graph'].get_state(run['config']).next,('human_review',))
  self.assertEqual(run['graph'].get_state(run['config']).values['audit'],[])
  next(b for b in again.button if b.label=='Close project').click().run()
  self.assertEqual(len(again.exception),0)
  self.assertNotIn('run',again.session_state)
  from project_store import project_path
  self.assertFalse(project_path(token[0] if isinstance(token,list) else token).exists())

class AssessmentFailureTests(AppTests):
 def test_failed_assessment_is_visible_and_not_retried_automatically(self):
  app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=30).run()
  next(a for a in app.text_area if a.label.startswith('Study objectives')).set_value('Assess missingness')
  next(b for b in app.button if b.label=='Profile and propose plan').click().run()
  with patch('llm_review.explain_review',side_effect=ValueError('OpenAI assessment failed (HTTP 401). Check OPENAI_API_KEY.')) as call:
   next(c for c in app.checkbox if c.label=='Allow this review context to be sent to OpenAI.').check().run()
   self.assertEqual(call.call_count,1)
   self.assertTrue(any('HTTP 401' in e.value for e in app.error))
   app.run()
   self.assertEqual(call.call_count,1)
   self.assertTrue(next(b for b in app.button if b.label=='Apply selected actions').disabled)
   grid=next(df.value for df in app.dataframe if list(df.value.columns)==['Column name','Data issue','Reasons','Suggested plan','Action'])
  self.assertTrue((grid['Action']=='Keep unchanged').all())
  run=app.session_state['run'];self.assertEqual(run['graph'].get_state(run['config']).values['audit'],[])
