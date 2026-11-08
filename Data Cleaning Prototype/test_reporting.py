import copy
import unittest
from cleaning import DEFAULT_CONTRACT, ROW
from agent import build_agent,initial_state,resume_agent
from reporting import management_report

class ReportingTests(unittest.TestCase):
 def test_tied_mode_is_applied_only_after_approval(self):
  c=copy.deepcopy(DEFAULT_CONTRACT);c.update(required_columns=[],identifier_columns=[],numeric_columns=[],date_columns=[],numeric_ranges={},date_order_pairs=[],category_maps={})
  rows=[{ROW:2,'ethnicity':'A'},{ROW:3,'ethnicity':'B'},{ROW:4,'ethnicity':''}]
  g=build_agent();config={'configurable':{'thread_id':'tie'}}
  g.invoke(initial_state(rows,['ethnicity'],c),config)
  snapshot=g.get_state(config)
  self.assertEqual(snapshot.next,('human_review',));self.assertEqual(snapshot.values['rows'],rows);self.assertEqual(snapshot.values['audit'],[])
  done=resume_agent(g,config,[],treatments={'missing:ethnicity':'Impute mode'})
  self.assertEqual(done.next,());self.assertIn(done.values['rows'][2]['ethnicity'],['A','B'])
  self.assertEqual(done.values['original'],rows)
  report=management_report(done.values,{'filename':'<script>alert(1)</script>','objectives':'Review ethnicity'})
  self.assertIn('Missing values',report);self.assertIn('balanced tied-mode allocations',report)
  self.assertNotIn('<script>',report);self.assertIn('&lt;script&gt;',report)
 def test_report_lists_executed_imputation(self):
  c=copy.deepcopy(DEFAULT_CONTRACT);c.update(required_columns=[],identifier_columns=[],numeric_columns=['age'],date_columns=[],numeric_ranges={},date_order_pairs=[],category_maps={})
  rows=[{ROW:2,'age':'10'},{ROW:3,'age':'20'},{ROW:4,'age':''}]
  g=build_agent();config={'configurable':{'thread_id':'report'}};g.invoke(initial_state(rows,['age'],c),config)
  state=resume_agent(g,config,[],treatments={'missing:age':'Impute mean'}).values
  report=management_report(state,{'filename':'sample.csv','objectives':'Test'})
  self.assertIn('Impute mean: 1 audit entries',report);self.assertIn('Row reconciliation:</strong> PASS',report)

class BalancedModeTests(unittest.TestCase):
 def test_balanced_reproducible_and_observed_values_preserved(self):
  from review import review_tables,execute_treatments
  c=copy.deepcopy(DEFAULT_CONTRACT);c.update(required_columns=[],identifier_columns=[],numeric_columns=[],date_columns=[],numeric_ranges={},date_order_pairs=[],category_maps={})
  rows=[{ROW:i+2,'category':v} for i,v in enumerate(['A','B']+['']*7)]
  _,review=review_tables({'rows':rows,'columns':['category'],'contract':c,'plan':[]})
  first=execute_treatments(rows,['category'],c,review,{'missing:category':'Impute mode'})
  second=execute_treatments(rows,['category'],c,review,{'missing:category':'Impute mode'})
  self.assertEqual(first,second);self.assertEqual(first[0][:2],rows[:2])
  assigned=[r['category'] for r in first[0][2:]]
  self.assertEqual(sorted([assigned.count('A'),assigned.count('B')]),[3,4])
  self.assertEqual(len(first[2]),7);self.assertTrue(all(a['seed']==42 for a in first[2]))
  self.assertTrue(all(r['category']=='' for r in rows[2:]))
