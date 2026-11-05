import copy
import os
import tempfile
import unittest
from unittest.mock import patch
from cleaning import load_csv, DEFAULT_CONTRACT
from agent import initial_state, build_agent, resume_agent
from project_store import save_project, load_project, close_project

class ProjectStoreTests(unittest.TestCase):
 def test_restore_pending_and_completed_without_reapplying(self):
  with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'CLEANING_PROJECT_DIR':directory}):
   data=b'patient_id,age\n001,\n002,20\n003,30\n'
   rows,columns=load_csv(data);contract=copy.deepcopy(DEFAULT_CONTRACT)
   contract.update(required_columns=['patient_id'],numeric_columns=['age'],date_columns=[],category_maps={},numeric_ranges={'age':[0,120]},date_order_pairs=[])
   graph=build_agent();config={'configurable':{'thread_id':'original'}}
   graph.invoke(initial_state(rows,columns,contract),config)
   run=dict(graph=graph,config=config,source_bytes=data,filename='test.csv',draft_choices={'1':{'missing:age':'Impute mean'}},objectives='Test')
   project='a'*32
   save_project(project,{'study_objectives':'Test'},run)
   restored=load_project(project);r=restored['run'];snapshot=r['graph'].get_state(r['config'])
   self.assertEqual(snapshot.next,('human_review',));self.assertEqual(snapshot.values['audit'],[])
   self.assertEqual(r['draft_choices'],run['draft_choices'])
   resume_agent(r['graph'],r['config'],[],treatments={'missing:age':'Impute mean'})
   self.assertEqual(r['graph'].get_state(r['config']).values['rows'][0]['age'],'25')
   save_project(project,restored['settings'],r)
   again=load_project(project)['run'];done=again['graph'].get_state(again['config'])
   self.assertEqual(done.next,());self.assertEqual(len(done.values['audit']),1)
   self.assertEqual(done.values['rows'][0]['patient_id'],'001')
   close_project(project);self.assertIsNone(load_project(project))
 def test_invalid_ids_rejected(self):
  with self.assertRaises(ValueError):load_project('../secret')
