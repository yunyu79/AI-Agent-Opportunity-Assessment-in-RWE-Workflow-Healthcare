import unittest
from cleaning import ROW, load_csv
from workflow import *
class Tests(unittest.TestCase):
 def test_boundaries(self):
  for n,rule in [(1,'M1'),(5,'M3'),(20,'M3'),(21,'M4')]:
   rows=[{ROW:i,'v':'' if i<n else '1'} for i in range(100)]
   self.assertEqual(missing_report(rows,['v'],{'v':'Non-critical'},[''])[0]['rule'],rule)
  self.assertIsNone(missing_report([],['v'],{},[''])[0]['missing_percent'])
 def test_survivor(self):
  rows=[{ROW:2,'id':'001'},{ROW:3,'id':'001'}]
  result,_=apply_duplicates(rows,duplicate_groups(rows,['id']),[2])
  self.assertEqual(result,[rows[1]])
  with self.assertRaises(ValueError): apply_duplicates(rows,duplicate_groups(rows,['id']),[99])
 def test_tails(self):
  rows=[{ROW:i,'v':str(v)} for i,v in enumerate([-999]+list(range(20))+[999])]
  candidates=outliers(rows,['v']); lower=next(c for c in candidates if c['tail']=='lower'); key=(lower['source_row'],'v')
  with self.assertRaises(ValueError): apply_outliers(rows,candidates,{key:'Cap upper P95'})
  changed,_=apply_outliers(rows,candidates,{key:'Cap P5/P95'})
  self.assertEqual(changed[0]['v'],lower['p5']); self.assertEqual(rows[0]['v'],'-999')
 def test_reconcile(self):
  rows=[{ROW:2,'id':'001','v':''},{ROW:3,'id':'002','v':'2'}]
  result,cols,audit=apply_missing(rows,['id','v'],{'v':'Drop missing rows'},[''])
  checks,_=validate(rows,result,cols,audit,[''],['v'],[],[])
  self.assertTrue(all(c['status']=='PASS' for c in checks[:-1]))
 def test_demos(self):
  from demo_data import demo_input
  for name in ('patient','medication','procedure'):
   data,_,contract=demo_input(name); rows,cols=load_csv(data)
   self.assertEqual(len(rows),500); missing_report(rows,cols,{},['']); outliers(rows,contract['numeric_columns'])
if __name__=='__main__': unittest.main()
