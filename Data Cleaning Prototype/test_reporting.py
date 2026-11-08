import copy
import unittest
from cleaning import DEFAULT_CONTRACT, ROW
from agent import build_agent,initial_state,resume_agent
from reporting import management_report

class ReportingTests(unittest.TestCase):
 def test_tied_mode_can_be_revised_without_partial_changes(self):
  c=copy.deepcopy(DEFAULT_CONTRACT);c.update(required_columns=[],identifier_columns=[],numeric_columns=[],date_columns=[],numeric_ranges={},date_order_pairs=[],category_maps={})
  rows=[{ROW:2,'ethnicity':'A'},{ROW:3,'ethnicity':'B'},{ROW:4,'ethnicity':''}]
  g=build_agent();config={'configurable':{'thread_id':'tie'}}
  g.invoke(initial_state(rows,['ethnicity'],c),config)
  with self.assertRaisesRegex(ValueError,'no unique mode'):resume_agent(g,config,[],treatments={'missing:ethnicity':'Impute mode'})
  snapshot=g.get_state(config)
  self.assertEqual(snapshot.next,('human_review',));self.assertEqual(snapshot.values['rows'],rows);self.assertEqual(snapshot.values['audit'],[])
  done=resume_agent(g,config,[],treatments={'missing:ethnicity':'Keep unchanged'})
  self.assertEqual(done.next,());self.assertEqual(done.values['rows'],rows)
  report=management_report(done.values,{'filename':'<script>alert(1)</script>','objectives':'Review ethnicity'})
  self.assertIn('Missing values',report);self.assertIn('No executed changes',report)
  self.assertNotIn('<script>',report);self.assertIn('&lt;script&gt;',report)
 def test_report_lists_executed_imputation(self):
  c=copy.deepcopy(DEFAULT_CONTRACT);c.update(required_columns=[],identifier_columns=[],numeric_columns=['age'],date_columns=[],numeric_ranges={},date_order_pairs=[],category_maps={})
  rows=[{ROW:2,'age':'10'},{ROW:3,'age':'20'},{ROW:4,'age':''}]
  g=build_agent();config={'configurable':{'thread_id':'report'}};g.invoke(initial_state(rows,['age'],c),config)
  state=resume_agent(g,config,[],treatments={'missing:age':'Impute mean'}).values
  report=management_report(state,{'filename':'sample.csv','objectives':'Test'})
  self.assertIn('Impute mean: 1 audit entries',report);self.assertIn('Row reconciliation:</strong> PASS',report)
