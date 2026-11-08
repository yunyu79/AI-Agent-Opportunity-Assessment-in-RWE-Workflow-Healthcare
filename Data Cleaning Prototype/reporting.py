"""Printable, escaped management report derived from actual audit records."""
from collections import Counter
from datetime import datetime, timezone
from html import escape
from cleaning import ROW, propose
from review import review_tables


def management_report(state, run):
    original=state['original'];columns=[c for c in original[0] if c!=ROW] if original else state['columns']
    before=dict(rows=original,columns=columns,contract=state['contract'],plan=propose(original,columns,state['contract']))
    _,findings=review_tables(before,state.get('importance'))
    _,remaining=review_tables(dict(state,plan=propose(state['rows'],state['columns'],state['contract'])),state.get('importance'))
    def e(value):return escape(str(value))
    groups={}
    for item in findings:groups.setdefault(item['column'],[]).append(item)
    for item in state.get('audit',[]):groups.setdefault(item.get('column','All source columns'),[])
    rows=[]
    for col,items in groups.items():
        changes=[a for a in state.get('audit',[]) if a.get('column','All source columns')==col]
        counts=Counter(a.get('decision',a.get('action','Change')) for a in changes)
        applied='; '.join(f'{method}: {count} audit entries' for method,count in counts.items()) or 'No executed changes for this column'
        allocations=Counter(str(a['after']) for a in changes if a.get('tie_method')=='balanced tied modes')
        if allocations:applied+='; balanced tied-mode allocations (seed 42): '+', '.join(f'{category}: {count}' for category,count in sorted(allocations.items()))
        pending=[p['method'] for p in state.get('pending_methods',[]) if p['column']==col]
        unresolved=[f"{r['issue']} ({r['affected_cells_estimate']} affected records/cells)" for r in remaining if r['column']==col]
        issues='; '.join(f"{i['issue']} ({i['affected_cells_estimate']} affected records/cells)" for i in items) or 'Audit-only change'
        outcome='; '.join(unresolved) or 'No remaining findings from configured checks'
        if pending:outcome+='; Pending assessment: '+', '.join(pending)
        rows.append('<tr>'+''.join('<td>'+e(x)+'</td>' for x in [col,issues,applied,outcome])+'</tr>')
    removed={a['source_row'] for a in state.get('audit',[]) if a.get('source_row') is not None and isinstance(a.get('before'),dict) and a.get('after') is None}
    reconciled=len(original)-len(removed)==len(state['rows'])
    status='Further review required' if remaining or state.get('pending_methods') or state.get('issues') else 'Configured checks completed without remaining findings'
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Data cleaning report</title>
<style>body{{font:15px/1.5 Arial,sans-serif;max-width:1100px;margin:40px auto;color:#182638}}h1,h2{{color:#17365d}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #ccd4df;padding:10px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}th{{background:#eef3f9}}@media print{{body{{margin:0}}thead{{display:table-header-group}}tr{{break-inside:avoid}}}}</style>
<h1>Data cleaning report</h1><p>Generated {e(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}</p>
<h2>Study and scope</h2><p><strong>Objectives:</strong> {e(run.get('objectives','Not recorded'))}</p><p><strong>Input:</strong> {e(run.get('filename','Unknown'))}. Checks cover the loaded file and configured rules.</p>
<h2>Executive summary</h2><p>{e(status)}. Input: {len(original)} rows and {len(columns)} columns. Output: {len(state['rows'])} rows and {len(state['columns'])} columns. {len(state.get('audit',[]))} changes were recorded in the audit log.</p>
<p><strong>Row reconciliation:</strong> {'PASS' if reconciled else 'FAIL'} — {len(original)} input minus {len(removed)} logged row deletions = {len(state['rows'])} output rows.</p>
<h2>Issues, methods and results by column</h2><table><thead><tr><th>Column</th><th>Issues detected before cleaning</th><th>Methods actually applied</th><th>Remaining issues / outcome</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>Approval and limitations</h2><p>Only executed audit entries are described as applied. Recommendations, dropdown selections and assessment-only methods are not counted as executed treatment. Counts may overlap across issues; audit-entry counts are not always cell counts, especially for whole-row or whole-column changes.</p><p>Statistical outliers and repeated identifiers are candidates, not proven errors. Missingness mechanisms and clinical validity require study-specific evidence. MICE, ML and proxy assessments remain pending unless implemented and executed. Retained issues are not claimed to be resolved.</p><p>This report excludes raw patient records. The downloadable audit bundle contains the detailed change log. Use your browser’s Print command to save this report as PDF.</p></html>'''
