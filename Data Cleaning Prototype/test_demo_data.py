"""Integration checks for the reviewed CSV demonstrations and their contracts."""
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import build_agent, initial_state, load_skill, resume_agent
from cleaning import load_csv, profile
from demo_data import DATASETS, DEMO_TABLES, ROOT, demo_input
from streamlit.testing.v1 import AppTest


class DemoDataTests(unittest.TestCase):
    def test_fixture_counts_missingness_and_identity(self):
        manifest = json.loads((ROOT / 'data/demo/manifest.json').read_text())
        expected = {'patient': ('race', 150), 'medication': ('paid_amount', 125),
                    'procedure': ('description', 125)}
        patient_ids = set()
        tables = {}
        for table in DEMO_TABLES:
            data, filename, contract = demo_input(table)
            rows, columns = load_csv(data)
            tables[table] = rows
            self.assertEqual(len(rows), 500)
            self.assertEqual(hashlib.sha256(data).hexdigest(), manifest['files'][filename]['sha256'])
            report = profile(rows, columns, contract)
            col, count = expected[table]
            self.assertEqual(report['missing_by_column'][col], count)
            self.assertIn(col, report['high_missing_columns'])
            self.assertEqual(report['duplicate_rows'], manifest['files'][filename]['exact_duplicate_excess'])
            if table == 'patient':
                self.assertEqual(report['duplicate_rows'], 2)
            if table == 'patient':
                patient_ids = {r['patient_id'] for r in rows}
                self.assertEqual(sum(bool(r['age']) and not 0 <= int(r['age']) <= 120 for r in rows), 2)
                self.assertEqual(report['unknown_by_column']['race'], 5)
        for table in ['medication', 'procedure']:
            self.assertTrue(all(not r['patient_id'] or r['patient_id'] in patient_ids for r in tables[table]))

    def test_all_demos_run_real_graph_without_filling_or_unapproved_deletion(self):
        for table in DEMO_TABLES:
            with self.subTest(table=table):
                data, _, contract = demo_input(table)
                rows, columns = load_csv(data)
                graph = build_agent()
                config = {'configurable': {'thread_id': table}, 'recursion_limit': 30}
                graph.invoke(initial_state(rows, columns, contract), config)
                pending = graph.get_state(config)
                self.assertEqual(pending.next, ('human_review',))
                self.assertEqual(pending.values['audit'], [])
                while pending.next:
                    approved = [a['id'] for a in pending.values['plan'] if a['id'] != 'drop_exact_duplicates']
                    pending = resume_agent(graph, config, approved)
                self.assertEqual(len(pending.values['rows']), 500)
                self.assertEqual(pending.values['original'], rows)
                self.assertFalse(any(i['issue'] == 'Required column missing' for i in pending.values['issues']))
                for original, current in zip(rows, pending.values['rows']):
                    for col in columns:
                        if original[col] == '':
                            self.assertIsNone(current[col])
                        if original[col] == 'Unknown':
                            self.assertEqual(current[col], 'Unknown')

    def test_default_and_selected_demo_ui_use_matching_contracts(self):
        for label in DATASETS:
            with self.subTest(label=label):
                app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=30).run()
                self.assertEqual(app.radio[0].value, 'patient.csv (500 rows)')
                app.radio[0].set_value(label).run()
                next(b for b in app.button if b.label == 'Profile and propose plan').click().run()
                self.assertEqual(len(app.exception), 0)
                run = app.session_state['run']
                snapshot = run['graph'].get_state(run['config'])
                self.assertEqual(len(snapshot.values['rows']), 500)
                self.assertEqual(run['filename'], label.split()[0])
                self.assertTrue(run['is_sample'])
                self.assertEqual(snapshot.next, ('human_review',))

    def test_missingness_threshold_is_strict_and_unknown_is_separate(self):
        data, _, contract = demo_input('patient')
        rows, columns = load_csv(data)
        for row in rows:
            row['race'] = 'White'
        for row in rows[:100]:
            row['race'] = ''
        rows[100]['race'] = 'Unknown'
        report = profile(rows, columns, contract)
        self.assertEqual(report['missing_percent_by_column']['race'], 20)
        self.assertNotIn('race', report['high_missing_columns'])
        self.assertEqual(report['unknown_by_column']['race'], 1)

    def test_skill_is_reloaded_and_hashed(self):
        text, digest = load_skill()
        self.assertIn('name: clean-rwe-demo-data', text)
        self.assertEqual(digest, hashlib.sha256(text.encode()).hexdigest())
        with patch('agent.Path.read_text', return_value='Updated project instructions'):
            updated, updated_digest = load_skill()
        self.assertNotEqual(updated_digest, digest)
        self.assertEqual(updated, 'Updated project instructions')


if __name__ == '__main__':
    unittest.main()
