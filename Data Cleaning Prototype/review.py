"""Spreadsheet-style review models and explicitly approved treatments."""
import copy
import io
from decimal import Decimal
from collections import Counter
from cleaning import ROW, as_number, proposed_value, quality_issues
from diagnostics import detect_issues

KEEP = 'Keep unchanged'
ASSESS = ['MICE — assessment required', 'ML prediction — assessment required', 'Proxy — validation required']
MISSING_OPTIONS = [KEEP, 'Complete-case: delete rows missing this column', 'Exclude column', 'Impute median', 'Impute mean', 'Impute mode'] + ASSESS


def is_missing(value, contract):
    return value is None or isinstance(value,str) and value.strip().casefold() in {v.strip().casefold() for v in contract['missing_tokens']}


def review_tables(state, importance=None):
    importance = importance or {}
    rows, cols, contract = state['rows'], state['columns'], state['contract']
    summary, review = [], []
    diagnostics = detect_issues(rows,cols,contract)
    issues = []
    for col in cols:
        missing_rows = {r[ROW] for r in rows if is_missing(r[col],contract)}
        affected = set(missing_rows)
        for finding in diagnostics:
            if finding['column'] in (col,'All source columns'):affected.update(finding['source_rows'])
        reasons = set()
        for issue in issues:
            if issue['column']==col and issue['source_row'] is not None:
                affected.add(issue['source_row']); reasons.add(issue['issue'])
        for action in state.get('plan',[]):
            if action['column']==col:
                for row in rows:
                    if proposed_value(action['tool'],row[col],col,contract)!=row[col]: affected.add(row[ROW])
        pct=100*len(missing_rows)/len(rows) if rows else None
        summary.append({'column':col,'affected_cells_estimate':len(affected),'percentage of missing':pct})
        if missing_rows:
            role=importance.get(col,'Unconfirmed')
            rule='M2' if pct<=5 and role!='Non-critical' else 'M4' if pct>20 else 'M3' if pct>=5 else 'M1'
            observed=[r[col] for r in rows if not is_missing(r[col],contract)]
            numeric=col in contract['numeric_columns'] and bool(observed) and all(as_number(v) is not None and as_number(v).is_finite() for v in observed)
            identifier=col in contract['identifier_columns'] or col.lower()=='id' or col.lower().endswith('_id')
            options=[KEEP,'Complete-case: delete rows missing this column','Exclude column']
            if not identifier and observed:
                if numeric: options+=['Impute median','Impute mean']
                options+=['Impute mode']
                options+=ASSESS
            suggestion={
                'M1':'Keep missing values; consider excluding this non-critical variable if unused. Assess joint row loss before complete-case deletion.',
                'M2':'Recommend ordinary imputation: median for skewed numeric values or outliers, mean for approximately symmetric numeric values, mode for suitable categories. Explain exceptions for identifiers or structural/all-missing fields.',
                'M3':'Choose the best justified method among ordinary median/mean/mode imputation, MICE, ML and a validated proxy. Explain suitability and prerequisites.',
                'M4':'Assess recoverability first; compare exclusion, MICE, validated ML or proxy. Preserve critical variables pending assessment.',
            }[rule]
            review.append(dict(id='missing:'+col,column=col,issue='Missing values',reason=f'{len(missing_rows)} of {len(rows)} values match configured missing markers; root cause is not established.',affected_cells_estimate=len(missing_rows),missing_percent=pct,rule=rule,importance=role,suggested_plan=suggestion+' Examine reasons; MCAR/MAR/MNAR is uncertain until supported by evidence. Present suitable removal, imputation, MICE, ML and proxy alternatives and obtain approval before row changes.',selected_action=KEEP,options=options))
        if missing_rows:
            numbers=[as_number(v) for v in observed] if numeric else []
            if numbers:
                from statistics import median
                review[-1]['numeric_summary']={'observed_count':len(numbers),'mean':str(sum(numbers)/len(numbers)),'median':str(median(numbers)),'minimum':str(min(numbers)),'maximum':str(max(numbers))}
        for action in state.get('plan',[]):
            if action['column']==col and action['tool']!='normalize_missing':
                review.append(dict(id=action['id'],column=col,issue='Format inconsistency',reason=action['reason'],affected_cells_estimate=action['affected_cells_estimate'],missing_percent=pct,rule='Explicit contract',importance=importance.get(col,'Unconfirmed'),suggested_plan=action['reason'],selected_action=KEEP,options=[KEEP,'Apply suggested normalization']))
    for finding in diagnostics:
        col=finding['column']
        review.append(dict(id='diagnostic:'+col+':'+finding['issue'],column=col,issue=finding['issue'],reason=finding['reason'],source_rows=finding['source_rows'],affected_cells_estimate=len(finding['source_rows']),missing_percent=next((x['percentage of missing'] for x in summary if x['column']==col),None),rule='Diagnostic review',importance=importance.get(col,'Unconfirmed'),suggested_plan='Assess evidence and source records before correction; retain until an appropriate action is approved.',selected_action=KEEP,options=[KEEP,'Investigate source — assessment required']))
    for entry in review:
        entry['options'] += [method+' — assessment required' for method in ('remove','imputation by median','imputation by mean','imputation by mode','MICE','ML','proxy') if method+' — assessment required' not in entry['options']]
    return summary, review


def validate_choices(review, choices):
    allowed={r['id']:r for r in review}
    if not isinstance(choices,dict) or any(k not in allowed or v not in allowed[k]['options'] for k,v in choices.items()):
        raise ValueError('Treatment choices must match the current reviewed table.')
    return {k:v for k,v in choices.items() if v!=KEEP}


def execute_treatments(rows,columns,contract,review,choices):
    choices=validate_choices(review,choices)
    out,cols,audit,pending=copy.deepcopy(rows),list(columns),[],[]
    for entry in review:
        choice=choices.get(entry['id'],KEEP)
        if choice==KEEP or not entry['id'].startswith('missing:'): continue
        col=entry['column']
        if choice in ASSESS or 'assessment required' in choice:
            pending.append({'column':col,'method':choice,'status':'Assessment required; no values changed'}); continue
        targets=[r for r in out if is_missing(r[col],contract)]
        common=dict(rule=entry['rule'],column=col,decision=choice)
        if choice=='Exclude column':
            audit.append(dict(common,action='exclude_column',before=[{ROW:r[ROW],'value':r[col]} for r in out],after=None,affected_cells=len(out)))
            cols.remove(col)
            for r in out: del r[col]
        elif choice.startswith('Complete-case:'):
            audit.extend(dict(common,action='drop_missing_row',source_row=r[ROW],before=copy.deepcopy(r),after=None) for r in targets)
            ids={r[ROW] for r in targets};out=[r for r in out if r[ROW] not in ids]
        elif targets:
            observed=[r[col] for r in out if not is_missing(r[col],contract)]
            if not observed: raise ValueError(f'{col}: cannot impute without observed values.')
            if choice=='Impute mode':
                counts=Counter(observed); modes=[v for v,n in counts.items() if n==max(counts.values())]
                if len(modes)!=1: raise ValueError(f'{col}: mode is tied. Retain or assess another method.')
                fill=modes[0]
            else:
                nums=sorted(as_number(v) for v in observed)
                if choice=='Impute mean': fill=str(sum(nums)/Decimal(len(nums)))
                else:
                    n=len(nums);fill=str(nums[n//2] if n%2 else (nums[n//2-1]+nums[n//2])/2)
            for r in targets:
                audit.append(dict(common,action='impute',source_row=r[ROW],before=r[col],after=fill));r[col]=fill
    pending.extend({'column':r['column'],'method':choices[r['id']],'status':'Assessment required; no values changed'} for r in review if r['id'] in choices and not r['id'].startswith('missing:') and 'assessment required' in choices[r['id']])
    return out,cols,audit,pending


def review_workbook(summary,review,choices=None):
    """Use the application's existing Excel dependency for runtime downloads."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.utils import get_column_letter
    from openpyxl.workbook.defined_name import DefinedName
    wb=Workbook();ws=wb.active;ws.title='Summary'
    ws.append(['column','affected_cells_estimate','percentage of missing'])
    for r in summary: ws.append([r['column'],r['affected_cells_estimate'],None if r['percentage of missing'] is None else r['percentage of missing']/100])
    for cell in ws['C'][1:]: cell.number_format='0.00%'
    review_sheet=wb.create_sheet('Review');options_sheet=wb.create_sheet('Options')
    headers=['Column name','Data issue','Reasons','Suggested plan','Action']
    review_sheet.append(headers)
    for i,r in enumerate(review,2):
        choice=(choices or {}).get(r['id'],r['selected_action'])
        status='Assessment only; does not execute' if choice in ASSESS or 'assessment required' in choice else 'Select and confirm in app to execute'
        review_sheet.append([r['column'],r['issue'],r['reason'],r['suggested_plan'],choice])
        for j,v in enumerate(r['options'],1): options_sheet.cell(j,i-1,v)
        letter=get_column_letter(i-1)
        range_name=f"Treatments_{i}"
        wb.defined_names.add(DefinedName(range_name, attr_text=f"'Options'!${letter}$1:${letter}${len(r['options'])}"))
        dv=DataValidation(type='list',formula1=range_name)
        dv.errorTitle='Choose a listed treatment';dv.error='Select a treatment from this row’s dropdown.';dv.showErrorMessage=True
        review_sheet.add_data_validation(dv);dv.add(review_sheet.cell(i,5))
    options_sheet.sheet_state='hidden'
    notes=wb.create_sheet('Instructions');notes.append(['Review instructions'])
    notes.append(['Workbook is for review. Confirm selections in the app; edited workbook upload is not implemented.'])
    notes.append(['Affected cells in Summary are the union of detected issue cells per column; overlapping tool counts are not added.'])
    for sheet in [ws,review_sheet,notes]:
        sheet.freeze_panes='A2';sheet.auto_filter.ref=sheet.dimensions
        for cell in sheet[1]: cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='17365D')
        for row in sheet:
            for cell in row:
                # Treat untrusted source headers/text as literal text, not Excel formulas.
                if isinstance(cell.value,str): cell.data_type='s'
                cell.alignment=Alignment(vertical='top',wrap_text=True)
        for col in sheet.columns:
            letter=col[0].column_letter;sheet.column_dimensions[letter].width=48 if letter in ('C','H') and sheet==review_sheet else 28
        for row in range(2,sheet.max_row+1): sheet.row_dimensions[row].height=72 if sheet==review_sheet else 30
    buf=io.BytesIO();wb.save(buf);return buf.getvalue()


def recommendation_action(entry, suggested):
    """Map a recommendation to an executable choice or an explicit assessment."""
    mapping={'imputation by median':'Impute median','imputation by mean':'Impute mean',
             'imputation by mode':'Impute mode','MICE':ASSESS[0],'ML':ASSESS[1],'proxy':ASSESS[2]}
    target=mapping.get(suggested)
    if target in entry['options']:return target
    if suggested in ('remove','imputation by median','imputation by mean','imputation by mode','MICE','ML','proxy'):
        return suggested+' — assessment required'
    return KEEP
