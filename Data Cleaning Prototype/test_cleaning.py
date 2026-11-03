import copy
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from agent import build_agent, choose_plan, initial_state, resume_agent
from cleaning import (DEFAULT_CONTRACT, ROW, csv_bytes, execute, load_csv, profile,
                      propose, quality_issues, validate_contract)


class CleaningTests(unittest.TestCase):
    def setUp(self):
        self.rows,self.columns=load_csv(Path(__file__).with_name('sample_rwe.csv').read_bytes())
        self.contract=copy.deepcopy(DEFAULT_CONTRACT)

    def run_graph(self,rows=None,columns=None,select=None,mode='Offline rules',planner=None):
        rows=rows if rows is not None else self.rows
        columns=columns if columns is not None else self.columns
        graph=build_agent(planner)
        config={'configurable':{'thread_id':'test'},'recursion_limit':30}
        graph.invoke(initial_state(rows,columns,self.contract,mode),config)
        snapshot=graph.get_state(config)
        while snapshot.next:
            ids=select(snapshot.values) if select else [p['id'] for p in snapshot.values['plan']]
            snapshot=resume_agent(graph,config,ids)
        return graph,config,snapshot.values

    def test_csv_preserves_identifiers_and_rejects_bad_input(self):
        self.assertEqual(self.rows[0]['patient_id'],'001')
        for data in [b'a,a\n1,2',b'__source_row__,a\n1,2',b'a,b\n1,2,3',b'\xff\xfe']:
            with self.assertRaises(ValueError): load_csv(data)

    def test_no_changes_before_real_langgraph_interrupt(self):
        graph=build_agent();config={'configurable':{'thread_id':'pause'}}
        graph.invoke(initial_state(self.rows,self.columns,self.contract),config)
        snapshot=graph.get_state(config)
        self.assertEqual(snapshot.next,('human_review',))
        self.assertEqual(snapshot.values['rows'],self.rows)
        self.assertEqual(snapshot.values['audit'],[])

    def test_cancel_keeps_original_without_apply(self):
        graph=build_agent();config={'configurable':{'thread_id':'cancel'}}
        graph.invoke(initial_state(self.rows,self.columns,self.contract),config)
        state=resume_agent(graph,config,cancel=True).values
        self.assertEqual(state['status'],'cancelled')
        self.assertEqual(state['rows'],self.rows)
        self.assertFalse(any(t['node']=='apply_tools' for t in state['trace']))

    def test_only_approved_action_changes_data(self):
        _,_,state=self.run_graph(select=lambda s:['trim:age'] if 'trim:age' in [p['id'] for p in s['plan']] else [])
        self.assertEqual(state['rows'][0]['age'],'45')
        self.assertEqual(state['rows'][0]['sex'],'male')
        self.assertEqual(state['rows'][0]['admission_date'],'2026/01/02')
        self.assertTrue(all(a['action']=='trim' and a['column']=='age' for a in state['audit']))

    def test_complete_cleaning_preserves_clinical_findings_and_source(self):
        graph,config,state=self.run_graph()
        self.assertEqual(len(state['rows']),8)
        self.assertEqual(len(state['original']),10)
        first=state['rows'][0]
        self.assertEqual(first['patient_id'],'001')
        self.assertEqual(first['admission_date'],'2026-01-02')
        self.assertEqual(first['total_cost'],'1200.5')
        bad=next(r for r in state['rows'] if r['patient_id']=='003')
        self.assertEqual((bad['age'],bad['total_cost'],bad['admission_date']),('150','-10','2026-02-30'))
        self.assertEqual(len([r for r in state['rows'] if r['patient_id']=='006']),2)
        self.assertEqual(state['status'],'completed_with_findings')
        self.assertTrue(any(i['issue'].startswith('Date precedes') for i in state['issues']))
        self.assertTrue(any(i['issue'].startswith('Unmapped category') for i in state['issues']))
        self.assertTrue(any(i['value']=='1x0' for i in state['issues']))
        self.assertTrue(any(i['issue'].startswith('Required value missing') for i in state['issues']))
        self.assertEqual(self.rows,state['original'])
        with self.assertRaises(ValueError): resume_agent(graph,config,[])

    def test_second_round_has_its_own_approval(self):
        rows,columns=load_csv(b'patient_id,age,sex,admission_date,discharge_date,total_cost\n001,20,M,2026-01-01,2026-01-02,10\n 001,20,M,2026-01-01,2026-01-02,10\n')
        graph=build_agent();config={'configurable':{'thread_id':'loop'}}
        graph.invoke(initial_state(rows,columns,self.contract),config)
        first=graph.get_state(config)
        self.assertEqual([p['id'] for p in first.values['plan']],['trim:patient_id'])
        second=resume_agent(graph,config,['trim:patient_id'])
        self.assertEqual(second.next,('human_review',))
        self.assertEqual(second.values['round'],2)
        self.assertEqual(len(second.values['rows']),2)
        self.assertEqual(second.values['plan'][0]['id'],'drop_exact_duplicates')
        done=resume_agent(graph,config,['drop_exact_duplicates'])
        self.assertEqual(done.next,())
        self.assertEqual(len(done.values['rows']),1)

    def test_declining_duplicate_removal_preserves_rows(self):
        _,_,state=self.run_graph(select=lambda s:[p['id'] for p in s['plan'] if p['id']!='drop_exact_duplicates'])
        self.assertEqual(len(state['rows']),10)
        self.assertFalse(any(a['action']=='drop_exact_duplicates' for a in state['audit']))
        self.assertIn('drop_exact_duplicates',state['blocked'])

    def test_audit_can_reconstruct_original_rows(self):
        _,_,state=self.run_graph()
        by_id={r[ROW]:copy.deepcopy(r) for r in state['rows']}
        for entry in reversed(state['audit']):
            if entry['action']=='drop_exact_duplicates':
                by_id[entry['source_row']]=entry['before']
            else:
                by_id[entry['source_row']][entry['column']]=entry['before']
        self.assertEqual([by_id[k] for k in sorted(by_id)],state['original'])

    def test_invalid_values_are_not_silently_cast_to_null(self):
        _,_,state=self.run_graph()
        row=next(r for r in state['rows'] if r['patient_id']=='004')
        self.assertEqual(row['total_cost'],'1x0')
        self.assertEqual(row['admission_date'],'01/02/2026')

    def test_identifier_cast_and_conflicting_contract_rejected(self):
        bad=copy.deepcopy(self.contract);bad['numeric_columns'].append('patient_id')
        with self.assertRaises(ValueError): validate_contract(bad,self.columns)
        bad=copy.deepcopy(self.contract);bad['date_columns'].append('age')
        with self.assertRaises(ValueError): validate_contract(bad,self.columns)

    def test_unknown_action_rejected_at_execution_and_resume(self):
        with self.assertRaises(ValueError): execute(self.rows,self.columns,self.contract,propose(self.rows,self.columns,self.contract),['run_python'])
        graph=build_agent();config={'configurable':{'thread_id':'unknown'}}
        graph.invoke(initial_state(self.rows,self.columns,self.contract),config)
        with self.assertRaises(ValueError): resume_agent(graph,config,['run_python'])
        self.assertEqual(graph.get_state(config).values['rows'],self.rows)

    def test_missing_required_columns_are_reported_not_created(self):
        rows,columns=load_csv(b'patient_id\n001\n')
        issues=quality_issues(rows,columns,self.contract)
        self.assertEqual(len([i for i in issues if i['issue']=='Required column missing']),5)
        self.assertNotIn('age',rows[0])

    def test_llm_selects_tools_without_receiving_patient_rows(self):
        observed=[]
        def fake(summary,candidates,contract,model):
            observed.append(summary)
            self.assertNotIn('001200.50',json.dumps(summary))
            return [next(c for c in candidates if c['id']=='trim:age')],'Trim age only.',{'model':'mock'}
        _,_,state=self.run_graph(mode='OpenAI planner',planner=fake,select=lambda s:[])
        self.assertEqual(len(observed),1)
        self.assertEqual(state['rows'],self.rows)
        self.assertEqual(state['calls'][0]['model'],'mock')

    def test_structured_api_plan_and_unknown_action(self):
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self,*_): pass
        summary=profile(self.rows,self.columns,self.contract)
        for selected,should_fail in [(['trim:age'],False),(['execute_code'],True)]:
            body={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'selected_ids':selected,'rationale':'test'})}]}],'usage':{'input_tokens':100}}
            with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),patch('urllib.request.urlopen',return_value=Response(json.dumps(body).encode())) as call:
                if should_fail:
                    with self.assertRaises(ValueError): choose_plan(summary,summary['candidates'],self.contract,'mock')
                else:
                    plan,_,meta=choose_plan(summary,summary['candidates'],self.contract,'mock')
                    self.assertEqual(plan[0]['id'],'trim:age')
                    payload=json.loads(call.call_args.args[0].data)
                    self.assertNotIn('001200.50',json.dumps(payload))
                    self.assertTrue(payload['text']['format']['strict'])
                    self.assertEqual(meta['usage']['input_tokens'],100)

    def test_export_keeps_source_row_and_leading_zeros(self):
        _,_,state=self.run_graph()
        exported=csv_bytes(state['rows'],self.columns).decode('utf-8-sig')
        self.assertIn('__source_row__,patient_id',exported)
        self.assertIn(',001,45,M,',exported)


if __name__=='__main__': unittest.main()
