import copy
import io
import unittest
from pathlib import Path

from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest
from exporting import excel_bundle
from cleaning import DEFAULT_CONTRACT, load_csv, proposed_value


class AppTests(unittest.TestCase):
    def test_streamlit_review_and_cancel(self):
        app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=20).run()
        self.assertEqual(len(app.exception),0)
        next(b for b in app.button if b.label=='Profile and propose plan').click().run()
        self.assertEqual(len(app.exception),0)
        run=app.session_state['run']
        state=run['graph'].get_state(run['config'])
        self.assertEqual(state.next,('human_review',))
        self.assertEqual(state.values['audit'],[])
        next(b for b in app.button if b.label=='Cancel further cleaning').click().run()
        self.assertEqual(len(app.exception),0)
        state=run['graph'].get_state(run['config'])
        self.assertEqual(state.values['status'],'cancelled')
        self.assertEqual(len(state.values['rows']),10)

    def test_streamlit_approval_executes_selected_tools(self):
        app=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=20).run()
        next(b for b in app.button if b.label=='Profile and propose plan').click().run()
        self.assertNotIn('drop_exact_duplicates',app.multiselect[0].value)
        next(b for b in app.button if b.label=='Apply selected actions').click().run()
        self.assertEqual(len(app.exception),0)
        run=app.session_state['run']
        state=run['graph'].get_state(run['config'])
        self.assertEqual(state.next,())
        self.assertGreater(len(state.values['audit']),0)
        self.assertEqual(len(state.values['rows']),10)
        self.assertTrue(any(a['tool']=='drop_exact_duplicates' for a in state.values['remaining_actions']))

    def test_workbook_preserves_identifier_and_formula_as_text(self):
        rows,columns=load_csv(b'patient_id,note\n001,=1+1\n')
        state={'original':rows,'rows':copy.deepcopy(rows),'issues':[],'audit':[],'trace':[]}
        wb=load_workbook(io.BytesIO(excel_bundle(state,{'mode':'test'})),data_only=False)
        self.assertEqual(wb['Cleaned']['B2'].value,'001')
        self.assertEqual(wb['Cleaned']['C2'].value,'=1+1')
        self.assertEqual(wb['Cleaned']['C2'].data_type,'s')

    def test_numeric_canonicalization_never_rounds_precision(self):
        number='123456789012345678901234567890.0100'
        self.assertEqual(proposed_value('normalize_number',number,'total_cost',DEFAULT_CONTRACT),'123456789012345678901234567890.01')


if __name__=='__main__': unittest.main()
