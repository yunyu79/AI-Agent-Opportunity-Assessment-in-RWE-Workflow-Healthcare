"""Study-objective-led cleaning workflow with explicit human decisions."""
import copy
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from cleaning import ROW, load_csv, quality_issues
from demo_data import DATASETS, demo_input, contract_for_source
from workflow import (missing_report, duplicate_groups, outliers, apply_missing,
                      apply_duplicates, apply_outliers, validate, export_csv)

st.set_page_config(page_title='Data Cleaning Agent', page_icon='🧹', layout='wide')
st.title('Data Cleaning Agent')
st.caption('Study objectives → files → missing values → duplicates → outliers → validate → download')
if st.sidebar.button('New project'):
    st.session_state.clear()
    st.rerun()

if 'project' not in st.session_state:
    st.subheader('1 · What are this study’s objectives?')
    with st.form('objectives'):
        objective = st.text_area('Study objectives (required)')
        outcome = st.text_input('Outcome')
        exposure = st.text_input('Exposure / predictors')
        confounders = st.text_input('Key confounders')
        unit = st.text_input('Unit of analysis / repeated measurements')
        create = st.form_submit_button('Create project')
    if create:
        if not objective.strip(): st.error('Describe the study objectives first.')
        else:
            st.session_state.project = dict(objectives=objective, outcome=outcome, exposure=exposure, confounders=confounders, unit=unit)
            st.session_state.tables = {}
            st.rerun()
    st.stop()
st.sidebar.write(st.session_state.project)

st.subheader('2 · Read files')
source = st.radio('Input', ['Three demonstration files', 'Upload CSV files'])
files = st.file_uploader('CSV files', type=['csv'], accept_multiple_files=True) if source == 'Upload CSV files' else []
if st.button('Read files'):
    try:
        inputs = [(demo_input(name)[1], demo_input(name)[0], demo_input(name)[2]) for name in DATASETS.values()] if source == 'Three demonstration files' else [(f.name, f.getvalue(), dict(required_columns=[], identifier_columns=[], numeric_columns=[], date_columns=[], category_maps={}, numeric_ranges={}, date_order_pairs=[], missing_tokens=[''])) for f in files]
        if not inputs: raise ValueError('Choose files first.')
        if len({n for n,_,_ in inputs}) != len(inputs): raise ValueError('Use unique filenames.')
        tables = {}
        for name,data,contract in inputs:
            rows, columns = load_csv(data)
            tables[name] = dict(original=copy.deepcopy(rows), rows=rows, columns=columns, contract=contract, audit=[], stage=3, decisions={}, filename=name)
        st.session_state.tables = tables
    except Exception as exc: st.error(str(exc))
if not st.session_state.tables: st.stop()
name = st.selectbox('Current file (files remain separate)', list(st.session_state.tables))
t = st.session_state.tables[name]
# Namespace every widget by file and stage so decisions cannot leak between tables.
prefix = name + ':' + str(t['stage'])
st.caption(f"{name} · {len(t['original'])} source records · {len(t['columns'])} current columns · CSV record numbers include the header")
st.dataframe(pd.DataFrame(t['rows']), hide_index=True)

if t['stage'] == 3:
    st.subheader('3 · Missing values')
    st.write('Classify importance using the study objectives. Unconfirmed is the default; column names alone do not establish importance.')
    importance = {c:st.selectbox(f'{c}: importance', ['Unconfirmed','Critical','Non-critical'], key=prefix+':importance:'+c) for c in t['columns']}
    tokens_text = st.text_input('Missing markers (JSON string array; exact matching)', value='[""]', key=prefix+':tokens')
    try:
        tokens = json.loads(tokens_text)
        if not isinstance(tokens,list) or any(not isinstance(v,str) for v in tokens): raise ValueError('Use a JSON array of strings.')
    except (ValueError,TypeError) as exc:
        st.error(str(exc)); st.stop()
    st.caption('Only empty fields are missing by default. Add NA, NULL or other markers only after confirming their meaning. Structural non-applicability must be reviewed separately.')
    report = missing_report(t['rows'],t['columns'],importance,tokens)
    st.dataframe(pd.DataFrame(report), hide_index=True)
    st.warning('Missingness percentages do not establish MCAR/MAR/MNAR. Inspect group/time/source patterns. MICE, ML and proxy require a study-specific implementation and are advisory here; no simulated imputation is performed.')
    choices = {}
    for item in report:
        if item['missing_count']:
            choices[item['column']] = st.selectbox(item['column']+' handling', ['Keep','Drop column','Drop missing rows','Median','Mode','Defer: MICE / ML / proxy assessment'], key=prefix+':choice:'+item['column'])
    loss = sum(any(choice=='Drop missing rows' and (r[c] is None or r[c] in tokens) for c,choice in choices.items()) for r in t['rows'])
    st.write(f'Combined complete-case loss from selected row deletions: {loss} / {len(t["rows"])} records.')
    note = st.text_area('Decision rationale / missingness assessment / limitations',key=prefix+':note')
    confirm = st.checkbox('I reviewed these rules and approve the selected changes.',key=prefix+':confirm')
    if st.button('Apply missing decisions',disabled=not confirm):
        try:
            decisions = {c:('Keep' if v.startswith('Defer:') else v) for c,v in choices.items()}
            rows,cols,audit = apply_missing(t['rows'],t['columns'],decisions,tokens)
            t.update(rows=rows, columns=cols, audit=t['audit']+audit, tokens=tokens, importance=importance, missing_before=report, stage=4)
            t['decisions']['missing'] = dict(choices=choices,note=note)
            t['deferred'] = any(v.startswith('Defer:') for v in choices.values())
            st.rerun()
        except ValueError as exc: st.error(str(exc))

elif t['stage'] == 4:
    st.subheader('4 · Duplicates: review all columns')
    keys = st.multiselect('Duplicate key (empty = exact full-row match; use event/visit keys for repeated measurements)',t['columns'],key=prefix+':keys')
    groups = duplicate_groups(t['rows'],t['columns'],keys)
    st.caption('Missing business keys are not matched. Candidate identity does not establish that a repeated event is erroneous.')
    deletions=[]
    for group in groups:
        st.write(group['group'])
        st.dataframe(pd.DataFrame(group['rows']),hide_index=True)
        action=st.radio(group['group']+' decision',['Keep all','Keep one selected row','Delete selected rows'],key=prefix+group['group'])
        ids=[r[ROW] for r in group['rows']]
        if action=='Keep one selected row':
            keep=st.selectbox('Survivor source row',ids,key=prefix+group['group']+':survivor')
            deletions.extend(i for i in ids if i!=keep)
        elif action=='Delete selected rows': deletions.extend(st.multiselect('Rows to delete',ids,key=prefix+group['group']+':delete'))
    st.write(f'{len(groups)} candidate groups; {len(deletions)} selected row deletions.')
    note=st.text_input('Duplicate decision rationale',key=prefix+':note')
    if st.button('Confirm duplicate decisions'):
        t['duplicate_candidates']=groups
        t['rows'],audit=apply_duplicates(t['rows'],groups,deletions)
        t['audit']+=audit
        t['decisions']['duplicates']=dict(keys=keys,deleted=deletions,note=note)
        t['stage']=5
        st.rerun()

elif t['stage'] == 5:
    st.subheader('5 · Outliers')
    st.caption('Select continuous numeric variables; exclude identifiers and category codes. IQR uses 1.5 × IQR; constant-IQR or fewer than four numeric observations are skipped. Full-file reference, linear quantiles, fixed at this review stage.')
    eligible=[c for c in t['columns'] if c not in t['contract']['identifier_columns'] and not c.lower().endswith('_id')]
    numeric=st.multiselect('Continuous numeric columns',eligible,default=[c for c in t['contract']['numeric_columns'] if c in eligible],key=prefix+':numeric')
    candidates=outliers(t['rows'],numeric)
    st.dataframe(pd.DataFrame(candidates),hide_index=True)
    decisions={}
    for item in candidates:
        key=(item['source_row'],item['column'])
        options=['Keep','Delete row','Set missing','Cap P5/P95']
        if item['tail']=='upper': options.append('Cap upper P95')
        decisions[key]=st.selectbox(f"Record {key[0]} · {key[1]} = {item['value']}",options,key=prefix+str(key))
    st.warning('Possible causes are hypotheses, not established diagnoses. Capping can affect effect estimates; lower-tail values are never raised to P95. Small samples and skew can make thresholds unstable.')
    note=st.text_area('Outlier decision rationale / cause evidence',key=prefix+':note')
    if st.button('Confirm outlier decisions'):
        t['outlier_candidates']=candidates
        t['rows'],audit=apply_outliers(t['rows'],candidates,decisions)
        t['audit']+=audit
        t['numeric']=numeric
        t['decisions']['outliers']=dict(choices=[dict(source_row=k[0],column=k[1],choice=v) for k,v in decisions.items()],note=note)
        t['stage']=6
        st.rerun()

else:
    st.subheader('6 · Validate output')
    keys=t['decisions']['duplicates']['keys']
    checks,encoded=validate(t['original'],t['rows'],t['columns'],t['audit'],t['tokens'],t['numeric'],t['contract']['required_columns'],keys)
    contract=copy.deepcopy(t['contract']); contract['missing_tokens']=t['tokens']
    findings=quality_issues(t['rows'],t['columns'],contract)
    checks[-1]=dict(check='Contract domain checks',expected=0,actual=len(findings),status='PASS' if not findings else 'FAIL')
    passed=all(c['status']=='PASS' for c in checks) and not t.get('deferred')
    st.dataframe(pd.DataFrame(checks).astype(str),hide_index=True)
    if passed: st.success('All configured checks passed. Accepted findings and limitations remain documented below.')
    else: st.warning('Provisional output: failed checks or deferred decisions require attention.')
    summary=missing_report(t['rows'],t['columns'],t['importance'],t['tokens'])
    remaining_dups=duplicate_groups(t['rows'],t['columns'],keys)
    remaining_outliers=outliers(t['rows'],t['numeric'])
    report=dict(project=st.session_state.project,filename=name,scope='Full file',status='PASS' if passed else 'PROVISIONAL',input_rows=len(t['original']),output_rows=len(t['rows']),input_columns=list(t['original'][0].keys()) if t['original'] else [],output_columns=t['columns'],checks=checks,rules_before=t['missing_before'],missing_after=summary,decisions=t['decisions'],audit=t['audit'],contract_findings=findings,remaining_duplicate_groups=remaining_dups,remaining_outliers=remaining_outliers,limits=['No automatic inference of missingness mechanism.','MICE, ML and proxy are advisory and require additional study-specific work.','Files checked separately; no cross-table relationship validation.','Outlier detection uses full-file IQR; subgroup and clinical validation require study-specific checks.','CSV exports nulls as empty strings; source values and cell changes are retained in the report.'])
    st.write('Applied decisions and summarized results')
    st.json(dict(decisions=t['decisions'],audited_changes=len(t['audit']),remaining_missing=sum(i['missing_count'] for i in summary),remaining_duplicate_groups=len(remaining_dups),remaining_outliers=len(remaining_outliers)))
    with st.expander('Full validation report, findings and limitations'): st.json(report)
    st.subheader('7 · Download')
    selection=st.radio('Download options',['CSV and report','CSV only','Report only'])
    if selection!='Report only': st.download_button('Download cleaned CSV',encoded,'cleaned_'+name,'text/csv')
    if selection!='CSV only': st.download_button('Download result report',json.dumps(report,indent=2,ensure_ascii=False),name+'.report.json','application/json')
    dup_rows=[dict(r,duplicate_group=g['group']) for g in t.get('duplicate_candidates',[]) for r in g['rows']]
    st.download_button('Download all duplicate candidates',pd.DataFrame(dup_rows).to_csv(index=False).encode('utf-8-sig'),name+'.duplicates.csv','text/csv')
    st.download_button('Download all outlier candidates',pd.DataFrame(t.get('outlier_candidates',[])).to_csv(index=False).encode('utf-8-sig'),name+'.outliers.csv','text/csv')
