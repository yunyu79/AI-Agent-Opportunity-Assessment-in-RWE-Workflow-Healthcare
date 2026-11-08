"""Reproduce the first-round synthetic validation with no network or API key."""
import csv
import io
import hashlib
import json
import sys
from pathlib import Path
from statistics import median
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'Data Cleaning Prototype'))
from agent import build_agent, initial_state, resume_agent
from cleaning import DEFAULT_CONTRACT, ROW, csv_bytes, load_csv
from diagnostics import detect_issues
from review import review_tables, is_missing
from summary import quality_summary


def fixture():
    rows = []
    for i in range(100):
        rows.append({ROW: i + 2, 'id': f'{i:03}', 'zip_code': '00123',
                     'score': '' if i < 5 else str(i + 1),
                     'cost': '' if 10 <= i < 20 else str(i + 1),
                     'group': '' if 20 <= i < 41 else 'A',
                     'note': '' if 41 <= i < 45 else 'recorded',
                     'measure': '9999' if i == 50 else str(i),
                     'start_date': '2026-01-01',
                     'end_date': '2026-01-01' if i == 60 else '2026-01-02'})
    rows[-1] = {**rows[-2], ROW: 101, 'score': rows[-2]['score'], 'cost': rows[-2]['cost']}
    columns = [col for col in rows[0] if col != ROW]
    contract = dict(DEFAULT_CONTRACT, required_columns=columns, identifier_columns=['id', 'zip_code'],
                    numeric_columns=['score','cost','measure'], date_columns=['start_date','end_date'],
                    category_maps={}, numeric_ranges={'measure':[0,100]}, date_order_pairs=[],
                    duplicate_unique_columns=['id'], allowed_duplicate_columns=['zip_code'])
    return rows, columns, contract


def validate():
    rows, columns, contract = fixture()
    expected_missing = {'score': range(2,7), 'cost': range(12,22), 'group': range(22,43), 'note': range(43,47)}
    truth = {(col,'Missing',i) for col,ids in expected_missing.items() for i in ids}
    truth |= {('measure','Statistical outlier (IQR)',52),('measure','Outside allowed range',52),
              ('end_date','Date order violation: start_date',62)}
    truth |= {(col,kind,i) for col,kind in [('id','Repeated identifier candidate'),('All source columns','Exact duplicate rows')] for i in (100,101)}
    importance = {'score':'Critical','note':'Non-critical'}
    timings = []
    for repeat in range(7):
        graph = build_agent()
        config = {'configurable': {'thread_id':str(repeat)}}
        start = perf_counter()
        graph.invoke(initial_state(rows,columns,contract),config)
        pending = graph.get_state(config)
        assert pending.next == ('human_review',) and pending.values['rows'] == rows and not pending.values['audit']
        _, review = review_tables(pending.values,importance)
        profile_time = perf_counter()-start
        start = perf_counter()
        result = resume_agent(graph,config,[],treatments={'missing:score':'Impute median','missing:cost':'MICE — assessment required'},importance=importance).values
        apply_time = perf_counter()-start
        start = perf_counter()
        output = csv_bytes(result['rows'],result['columns'])
        quality_summary(result['rows'],result['columns'],contract)
        export_time = perf_counter()-start
        timings.append([profile_time,apply_time,export_time])
    # Missing counts come from the review table. Compare to independently seeded cell locations
    # using the same predicate that feeds the review table; check the displayed count too.
    missing_entries = {r['column']:r for r in review if r['issue']=='Missing values'}
    detected = {(r['column'],r['issue'],i) for r in detect_issues(rows,columns,contract) for i in r['source_rows']}
    for col,entry in missing_entries.items():
        ids = [r[ROW] for r in rows if is_missing(r[col],contract)]
        assert len(ids)==entry['affected_cells_estimate']
        detected.update((col,'Missing',i) for i in ids)
    expected_rules = {'score':'M2','cost':'M3','group':'M4','note':'M1'}
    actual_rules = {col:r['rule'] for col,r in missing_entries.items()}
    expected = [dict(row,score='53') if row[ROW] in expected_missing['score'] else row for row in rows]
    checks = {
        'five approved median fills equal the independent expected value 53': all(result['rows'][i]['score']=='53' for i in range(5)),
        'full output equals expected, including untouched cells and leading zeros':result['rows']==expected,
        'audit covers exactly the approved cells':{(a['source_row'],a['column'],a['after']) for a in result['audit']}=={(i,'score','53') for i in range(2,7)} and len(result['audit'])==5,
        'MICE is pending and cost remains unchanged':any(p['column']=='cost' for p in result['pending_methods']) and all(a['cost']==b['cost'] for a,b in zip(rows,result['rows'])),
        'CSV round trip preserves all output cell strings':list(csv.DictReader(io.StringIO(output.decode('utf-8-sig'))))==[dict(r, **{ROW:str(r[ROW])}) for r in expected],
    }
    return {'controlled':{'rows':len(rows),'tp':len(truth&detected),'fp':len(detected-truth),'fn':len(truth-detected),
                          'false_positives':sorted(detected-truth),'false_negatives':sorted(truth-detected),'rules':actual_rules,
                          'rule_correct':sum(actual_rules.get(k)==v for k,v in expected_rules.items()),'rule_total':len(expected_rules),
                          'imputation_correct':sum(result['rows'][i]['score']=='53' for i in range(5)),'imputation_total':5,'checks':checks},
            'timing_seconds_median_7_runs':dict(zip(['profile_and_review','approved_execution','statistics_and_csv'],map(median,zip(*timings))))}


def demo_checks():
    root = Path(sys.path[0]); manifest = json.loads((root/'data/demo/manifest.json').read_text())
    results = {}
    for name, spec in manifest['files'].items():
        data = (root/'data/demo'/name).read_bytes()
        rows,columns = load_csv(data)
        contract = json.loads((root/'contracts'/Path(name).with_suffix('.json')).read_text())
        overall, stats = quality_summary(rows,columns,contract)
        blank = next(s['missing_count'] for s in stats if s['column']==spec['high_missing_demo_column'])
        results[name] = {'sha256_matches':hashlib.sha256(data).hexdigest()==spec['sha256'], 'rows':len(rows),
                         'manifest_missing_expected':spec['blank_count'],'detected_missing':blank,
                         'manifest_excess_duplicates_expected':spec['exact_duplicate_excess'], 'detected_excess_duplicates':overall['excess_exact_duplicate_rows']}
    return results


if __name__ == '__main__':
    print(json.dumps({**validate(),'demo_manifest':demo_checks()},indent=2))
