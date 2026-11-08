import copy
import unittest
from cleaning import DEFAULT_CONTRACT, ROW
from summary import quality_summary
class SummaryTests(unittest.TestCase):
 def test_duplicates_outliers_and_missing_denominators(self):
  c=copy.deepcopy(DEFAULT_CONTRACT);c.update(required_columns=[],identifier_columns=[],numeric_columns=['value'],numeric_ranges={},date_columns=[],date_order_pairs=[],category_maps={})
  rows=[{ROW:i+2,'value':str(i),'zip_code':'00123'} for i in range(20)]
  rows += [{ROW:22,'value':'999','zip_code':'00123'},{ROW:23,'value':'','zip_code':'00123'},dict(rows[0],**{ROW:24})]
  overall,stats=quality_summary(rows,['value','zip_code'],c)
  self.assertEqual(overall['exact_duplicate_groups'],1);self.assertEqual(overall['rows_in_exact_duplicate_groups'],2);self.assertEqual(overall['excess_exact_duplicate_rows'],1)
  self.assertEqual(overall['rows_with_statistical_outliers'],1)
  self.assertEqual(stats[0]['missing_count'],1);self.assertEqual(stats[0]['outlier_count'],1)
  self.assertEqual(stats[1]['rows_in_repeated_values'],23);self.assertEqual(stats[1]['outlier_count'],0)
 def test_empty(self):
  overall,stats=quality_summary([],['value'],DEFAULT_CONTRACT)
  self.assertIsNone(overall['exact_duplicate_row_percent']);self.assertIsNone(stats[0]['missing_percent'])
