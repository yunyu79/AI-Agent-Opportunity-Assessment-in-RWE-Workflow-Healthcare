import io
import unittest
from openpyxl import load_workbook
from cleaning import ROW, DEFAULT_CONTRACT, load_csv, profile, propose
from agent import build_agent, initial_state, resume_agent
from review import *

class ReviewTests(unittest.TestCase):
 def state(self):
  rows=[{ROW:i+2,'patient_id':f'{i:03}','age':'' if i<2 else str(i+20)} for i in range(10)]
  contract=copy.deepcopy(DEFAULT_CONTRACT);contract.update(required_columns=['patient_id'],numeric_columns=['age'],date_columns=[],category_maps={},numeric_ranges={'age':[0,120]},date_order_pairs=[])
  return dict(rows=rows,columns=['patient_id','age'],contract=contract,plan=propose(rows,['patient_id','age'],contract))
 def test_threshold_and_eligibility(self):
  s=self.state();summary,review=review_tables(s)
  missing=next(r for r in review if r['id']=='missing:age')
  self.assertEqual(missing['rule'],'M3');self.assertEqual(summary[1]['percentage of missing'],20)
  self.assertIn('Impute mean',missing['options'])
  s['rows'][0]['patient_id']=''
  _,review=review_tables(s)
  self.assertNotIn('Impute mean',next(r for r in review if r['id']=='missing:patient_id')['options'])
  with self.assertRaises(ValueError):validate_choices(review,{'missing:patient_id':'Impute mean'})
 def test_graph_mean_and_assessment(self):
  for choice in ['Impute mean','MICE — assessment required','Complete-case: delete rows missing this column']:
   s=self.state();graph=build_agent();config={'configurable':{'thread_id':choice}}
   graph.invoke(initial_state(s['rows'],s['columns'],s['contract']),config)
   result=resume_agent(graph,config,[],treatments={'missing:age':choice}).values
   self.assertEqual(result['original'],s['rows'])
   if choice=='Impute mean': self.assertEqual(result['rows'][0]['age'],'25.5')
   elif choice.startswith('Complete-case'): self.assertEqual(len(result['rows']),8)
   else: self.assertEqual(result['rows'],s['rows']);self.assertTrue(result['pending_methods'])
 def test_workbook(self):
  summary,review=review_tables(self.state());wb=load_workbook(io.BytesIO(review_workbook(summary,review)))
  self.assertEqual(wb.sheetnames,['Summary','Review','Options','Instructions'])
  self.assertEqual(wb['Summary']['C3'].value,.2)
  self.assertGreater(len(wb['Review'].data_validations.dataValidation),0)
  for dv in wb['Review'].data_validations.dataValidation:self.assertIn(dv.formula1,wb.defined_names)
 def test_distinct_issue_counts(self):
  s=self.state();s['rows'][2]['age']=' 23 '
  s['plan']=propose(s['rows'],s['columns'],s['contract'])
  summary,_=review_tables(s)
  self.assertEqual(summary[1]['affected_cells_estimate'],3)
if __name__=='__main__':unittest.main()

class RecommendationDefaults(unittest.TestCase):
 def test_mapping_and_ambiguous_removal(self):
  _,review=review_tables(ReviewTests().state())
  entry=next(r for r in review if r['id']=='missing:age')
  self.assertEqual(recommendation_action(entry,'imputation by mean'),'Impute mean')
  self.assertEqual(recommendation_action(entry,'remove'),'remove — assessment required')
  s=ReviewTests().state()
  rows,cols,audit,pending=execute_treatments(s['rows'],s['columns'],s['contract'],review,{'missing:age':recommendation_action(entry,'remove')})
  self.assertEqual(rows,s['rows']);self.assertEqual(audit,[]);self.assertTrue(pending)
