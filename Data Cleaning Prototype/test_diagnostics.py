import copy
import unittest
from cleaning import ROW, DEFAULT_CONTRACT
from diagnostics import detect_issues
from agent import build_agent, initial_state

class DiagnosticTests(unittest.TestCase):
 def contract(self):
  c=copy.deepcopy(DEFAULT_CONTRACT)
  c.update(required_columns=['id','value','absent'],identifier_columns=['id'],numeric_columns=['value'],numeric_ranges={'value':[0,100]},date_columns=['start_date','end_date'],date_order_pairs=[],category_maps={'kind':{'a':'A'}})
  return c
 def test_distinct_findings_and_strict_dates(self):
  rows=[{ROW:i+2,'id':str(i),'value':str(i+10),'start_date':'2026-01-01','end_date':'2026-01-02','kind':'A'} for i in range(20)]
  rows[0]['value']='999';rows[1]['value']='invalid';rows[2]['value']=''
  rows[3]['end_date']='2026-01-01';rows[4]['kind']='unexpected';rows[5]['end_date']='bad'
  rows.append(dict(rows[6],**{ROW:22}))
  kinds={x['issue']:x for x in detect_issues(rows,list(rows[0])[1:],self.contract())}
  for kind in ['Required column absent','Statistical outlier (IQR)','Invalid numeric value','Outside allowed range','Unexpected category','Invalid or ambiguous date','Repeated identifier candidate','Exact duplicate rows','Date order violation: start_date']:self.assertIn(kind,kinds)
  self.assertEqual(kinds['Invalid numeric value']['source_rows'],[3])
  self.assertEqual(kinds['Date order violation: start_date']['source_rows'],[5])
  self.assertEqual(len(kinds['Exact duplicate rows']['source_rows']),2)
 def test_validation_only_dataset_enters_review_without_mutation(self):
  rows=[{ROW:2,'id':'001','value':'999','start_date':'2026-01-02','end_date':'2026-01-01','kind':'A'}]
  columns=list(rows[0])[1:];graph=build_agent();config={'configurable':{'thread_id':'diagnostic-only'}}
  graph.invoke(initial_state(rows,columns,self.contract()),config)
  snapshot=graph.get_state(config)
  self.assertEqual(snapshot.next,('human_review',));self.assertEqual(snapshot.values['rows'],rows);self.assertEqual(snapshot.values['audit'],[])

class DuplicatePolicyTests(unittest.TestCase):
 def test_postal_repeats_and_configured_unique_keys(self):
  c=copy.deepcopy(DEFAULT_CONTRACT);c.update(required_columns=[],identifier_columns=['zip_code','person_id'],numeric_columns=[],numeric_ranges={},date_columns=[],date_order_pairs=[],category_maps={})
  rows=[{ROW:2,'zip_code':'00123','person_id':'a'},{ROW:3,'zip_code':'00123','person_id':'b'}]
  self.assertFalse(any(x['issue']=='Repeated identifier candidate' for x in detect_issues(rows,['zip_code','person_id'],c)))
  c['duplicate_unique_columns']=['zip_code']
  self.assertTrue(any(x['column']=='zip_code' for x in detect_issues(rows,['zip_code','person_id'],c)))
  c['duplicate_unique_columns']=[];c['allowed_duplicate_columns']=['zip_code']
  self.assertFalse(detect_issues(rows,['zip_code','person_id'],c))
 def test_m2_precedence_at_exactly_five_percent(self):
  from review import review_tables
  rows=[{ROW:i+2,'value':'' if i==0 else str(i)} for i in range(20)]
  c=copy.deepcopy(DEFAULT_CONTRACT);c.update(required_columns=[],identifier_columns=[],numeric_columns=['value'],numeric_ranges={},date_columns=[],date_order_pairs=[],category_maps={})
  s={'rows':rows,'columns':['value'],'contract':c,'plan':[]}
  _,review=review_tables(s,{'value':'Critical'})
  self.assertEqual(next(r for r in review if r['id']=='missing:value')['rule'],'M2')
  _,review=review_tables(s,{'value':'Non-critical'})
  self.assertEqual(next(r for r in review if r['id']=='missing:value')['rule'],'M3')
