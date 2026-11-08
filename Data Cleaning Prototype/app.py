"""Streamlit interface for the LangGraph cleaning agent."""
import io
import json
import os
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from exporting import excel_bundle
from review import review_tables, review_workbook, KEEP
from llm_review import explain_review
from diagnostics import detect_issues
from project_store import save_project, load_project, close_project

from agent import build_agent, initial_state, resume_agent, load_skill
from demo_data import DATASETS, LEGACY_SAMPLE, contract_for_source, demo_input
from cleaning import DEFAULT_CONTRACT, ROW, csv_bytes, data_hash, load_csv

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='RWE Data Cleaning Agent',page_icon='🧹',layout='wide')
# A project token in the URL survives browser refresh and reconnect.
project_id=st.query_params.get('project')
if not project_id or len(project_id)!=32 or any(c not in '0123456789abcdef' for c in project_id):
    project_id=uuid.uuid4().hex
    st.query_params['project']=project_id
if st.session_state.get('_loaded_project')!=project_id:
    saved=load_project(project_id)
    st.session_state['_saved_settings']=saved['settings'] if saved else {}
    for key,value in st.session_state['_saved_settings'].items():
        if key!='saved_upload':st.session_state[key]=value
    if saved and saved['run']: st.session_state['run']=saved['run']
    st.session_state['_loaded_project']=project_id


def persist():
    settings=dict(st.session_state.get('_saved_settings',{}))
    keys=['study_objectives','dataset','planner','model','consent']
    keys += [k for k in st.session_state if k.startswith(('contract-','critical-','noncritical-','review_note-','review-consent-'))]
    for key in keys:
        if key in st.session_state: settings[key]=st.session_state[key]
    upload=st.session_state.get('upload_csv')
    if upload:
        import base64
        settings['saved_upload']={'name':upload.name,'base64':base64.b64encode(upload.getvalue()).decode()}
    st.session_state['_saved_settings']=settings
    save_project(project_id,settings,st.session_state.get('run'))


st.title('RWE Data Cleaning Agent')
st.caption('LangGraph · profile → plan → human review → cleaning tools → validation')
st.info('Use synthetic or de-identified data. Offline mode uses deterministic rules; OpenAI mode uses an LLM to select among allowed tools. Every change requires your approval.')


def display_rows(rows):
    return pd.DataFrame(rows).fillna('∅')




# Upgrade saved defaults as well as new projects.
if st.session_state.get('model') in ('gpt-4.1-mini','gpt-6-astra'):
    st.session_state['model']='gpt-6.1-sol'
with st.sidebar:
    st.header('1 · Study and data')
    objectives = st.text_area('Study objectives (required for a new project)', key='study_objectives',on_change=persist)
    source = st.radio('Dataset',list(DATASETS) + [LEGACY_SAMPLE,'Upload CSV'],key='dataset',on_change=persist)
    uploaded = st.file_uploader('UTF-8 CSV',type=['csv'],disabled=source!='Upload CSV',key='upload_csv',on_change=persist)
    mode = st.selectbox('Planner',['Offline rules','OpenAI planner'],key='planner',on_change=persist)
    model = st.text_input('Model',value='gpt-6.1-sol',key='model',on_change=persist)
    consent = st.checkbox('Allow sending column names, aggregate counts and the contract to OpenAI.',disabled=mode!='OpenAI planner',key='consent',on_change=persist)
    st.caption('Patient rows and sample cell values are excluded from the planner request. No API key is entered or displayed here.')
    with st.expander('Edit data contract'):
        contract_text = st.text_area('Contract JSON',value=json.dumps(contract_for_source(source),indent=2),height=400,key='contract-'+source,on_change=persist)
    start = st.button('Profile and propose plan',type='primary',width='stretch')
    reset = st.button('Close project',width='stretch')
    st.caption('Settings and progress are saved locally until Close project. Bookmark this page to reopen this project after restarting. Saved data is in .local_projects (or CLEANING_PROJECT_DIR).')

if reset:
    close_project(project_id)
    st.session_state.clear()
    st.query_params.clear()
    st.rerun()

if start:
    try:
        if not objectives.strip():
            raise ValueError('Enter the study objectives before proposing a plan.')
        if source in DATASETS:
            data,filename,_=demo_input(DATASETS[source])
        elif source==LEGACY_SAMPLE:
            data=(ROOT/'sample_rwe.csv').read_bytes()
            filename='sample_rwe.csv'
        elif uploaded:
            data,filename=uploaded.getvalue(),uploaded.name
        elif source=='Upload CSV' and st.session_state['_saved_settings'].get('saved_upload'):
            import base64
            stored=st.session_state['_saved_settings']['saved_upload']
            data,filename=base64.b64decode(stored['base64']),stored['name']
        else:
            raise ValueError('Select a CSV file first.')
        if mode=='OpenAI planner' and not consent:
            raise ValueError('Confirm sending the profile/contract to OpenAI, or choose offline rules.')
        contract=json.loads(contract_text)
        rows,columns=load_csv(data)
        state=initial_state(rows,columns,contract,mode,model)
        graph=build_agent()
        config={'configurable':{'thread_id':str(uuid.uuid4())},'recursion_limit':30}
        st.session_state.run={'graph':graph,'config':config,'source_hash':data_hash(data),
                              'objectives':objectives,'source_bytes':data,'filename':filename,'started_at':datetime.now(timezone.utc).isoformat(),
                              'started_clock':time.monotonic(),'is_sample':source!='Upload CSV','error':None}
        with st.spinner('Profiling and preparing a reviewable plan…'):
            graph.invoke(state,config)
            if not graph.get_state(config).next:
                st.session_state.run['finished_seconds']=round(time.monotonic()-st.session_state.run['started_clock'],2)
    except Exception as exc:
        if 'run' in st.session_state: st.session_state.run['error']=str(exc)
        else: st.error(str(exc))

with st.expander('Agent instructions — SKILL.md'):
    skill_text,skill_hash=load_skill()
    st.markdown(skill_text)
    st.caption('Edit SKILL.md in the project folder. OpenAI planning reads it on each call; offline rules follow the JSON contract. Mean, median, mode, complete-case and column exclusion run after approval. MICE, ML and proxy require further assessment.')

run=st.session_state.get('run')
if not run:
    st.subheader('Preview selected input')
    if source in DATASETS:
        preview_data,preview_name,_=demo_input(DATASETS[source])
    elif source==LEGACY_SAMPLE:
        preview_data,preview_name=(ROOT/'sample_rwe.csv').read_bytes(),'sample_rwe.csv'
    elif uploaded:
        preview_data,preview_name=uploaded.getvalue(),uploaded.name
    elif source=='Upload CSV' and st.session_state['_saved_settings'].get('saved_upload'):
        import base64
        stored=st.session_state['_saved_settings']['saved_upload']
        preview_data,preview_name=base64.b64decode(stored['base64']),stored['name']
    else:
        persist()
        st.write('Upload a CSV, or choose one of the three 500-row demonstrations.')
        st.stop()
    try:
        rows,_=load_csv(preview_data)
        st.caption(f'{preview_name}: {len(rows)} source rows. Showing the first 20; the agent processes the entire selected file.')
        st.dataframe(display_rows(rows[:20]),hide_index=True,width='stretch')
    except ValueError as exc:
        st.error(str(exc))
    persist()
    st.stop()

if run['error']: st.error(run['error'])
snapshot=run['graph'].get_state(run['config'])
state=snapshot.values
if not state:
    st.warning('No checkpoint available. Start a new run.')
    st.stop()
if run['is_sample']: st.caption('SYNTHETIC DATA — no real patients or clinical evidence.')
st.caption(f"Current run: {run['filename']} · {state.get('mode')} · {state.get('status')} · review round {state.get('round',0)}/2")
cols=st.columns(3)
cols[0].metric('Original rows',len(state['original']))
cols[1].metric('Current rows',len(state['rows']))
cols[2].metric('Audited changes',len(state.get('audit',[])))

st.subheader('Data issue summary')
st.caption('Affected cells count distinct source cells with detected issues; overlapping tool estimates are not added. Missing percentages use the full file row count.')
summary, _ = review_tables(state)
st.dataframe(pd.DataFrame(summary), hide_index=True, width='stretch', column_config={'percentage of missing':st.column_config.NumberColumn(format='%.2f%%')})

if snapshot.next==('human_review',) and not run['error']:
    st.subheader('2 · Review the proposed plan')
    st.caption('Review each column below. Click a Selected action cell to choose a treatment; then confirm. The suggested plan does not execute automatically.')
    with st.expander('Study importance and detailed settings'):
        st.write(run['objectives'])
        critical = st.multiselect('Critical variables for these objectives',state['columns'],key='critical-'+project_id,on_change=persist)
        noncritical = st.multiselect('Confirmed non-critical variables',[c for c in state['columns'] if c not in critical],key='noncritical-'+project_id,on_change=persist)
        st.caption('Other variables remain unconfirmed. Review structural missingness and joint sample loss before deletion; simple imputation understates uncertainty.')
    importance={c:('Critical' if c in critical else 'Non-critical' if c in noncritical else 'Unconfirmed') for c in state['columns']}
    summary, review = review_tables(state,importance)
    import hashlib
    context_key=hashlib.sha256(json.dumps([review,run['objectives'],importance,model,load_skill()[1]],sort_keys=True).encode()).hexdigest()
    st.caption('Sol assesses likely reasons and recommends a method using study objectives, importance and aggregate issue descriptions. No record values are sent. Data changes still require your approval.')
    review_consent=st.checkbox('Allow this review context to be sent to OpenAI.',key='review-consent-'+project_id)
    cached=run.get('llm_review',{})
    retry=st.button('Retry LLM assessment',disabled=not review_consent)
    if review_consent and review and (retry or (cached.get('context')!=context_key and run.get('llm_attempt_context')!=context_key)):
        run['llm_attempt_context']=context_key
        run.pop('llm_review_error',None)
        try:
            with st.spinner('Sol is assessing reasons and treatment options…'):
                run['llm_review']={'context':context_key,'items':explain_review(review,run['objectives'],importance,model)}
        except Exception as exc:
            run['llm_review_error']=str(exc)
        persist()
    explanations=run.get('llm_review',{}).get('items',{}) if run.get('llm_review',{}).get('context')==context_key else {}
    if not review_consent:
        st.info('Enable the checkbox above to start the LLM assessment automatically.')
    elif run.get('llm_review_error') and not explanations:
        st.error(run['llm_review_error'])
    # A single spreadsheet widget keeps the five columns together at narrow widths.
    visible=[]
    for r in review:
        explanation=explanations.get(r['id'],{})
        saved=run.get('draft_choices',{}).get(str(state['round']),{}).get(r['id'],KEEP)
        visible.append({'Column name':r['column'],'Data issue':r['issue'],'Reasons':explanation.get('reasons','Assessment unavailable — see message above'),'Suggested plan':explanation.get('suggested_plan','Not generated'),'Action':saved if saved in r['options'] else KEEP})
    with st.expander('Issue details and affected source records'):
        st.caption('Checks cover configured numeric, category, identifier and date rules; they cannot discover every domain-specific inconsistency. Repeated identifiers and statistical outliers are candidates, not proven errors.')
        for finding in review:
            if finding.get('source_rows'):
                st.write(finding['column']+' · '+finding['issue']+' · '+str(len(finding['source_rows']))+' records')
                st.dataframe(pd.DataFrame([r for r in state['rows'] if r[ROW] in set(finding['source_rows'])]),hide_index=True)
    all_options=list(dict.fromkeys(o for r in review for o in r['options']))
    edited=st.data_editor(pd.DataFrame(visible),hide_index=True,width='stretch',height=480,num_rows='fixed',disabled=['Column name','Data issue','Reasons','Suggested plan'],column_config={'Column name':st.column_config.TextColumn(width='medium'),'Data issue':st.column_config.TextColumn(width='medium'),'Reasons':st.column_config.TextColumn(width='large'),'Suggested plan':st.column_config.TextColumn(width='medium'),'Action':st.column_config.SelectboxColumn(options=all_options,required=True,width='large')},key='review-grid-'+project_id+'-'+str(state['round'])+'-'+context_key+'-'+str(bool(explanations))) if visible else pd.DataFrame()
    choices={r['id']:edited.iloc[i]['Action'] for i,r in enumerate(review)}
    run.setdefault('draft_choices',{})[str(state['round'])]=choices
    persist()
    invalid=[r['column'] for r in review if choices[r['id']] not in r['options']]
    if invalid: st.error('Selected treatment is not applicable to: '+', '.join(invalid)+'. Choose a valid option from the per-column list below.')
    with st.expander('Available options for each issue'):
        for r in review: st.write(r['column']+' · '+r['issue']+': '+ '; '.join(r['options']))
    st.caption('MICE, ML and proxy are assessment choices: they preserve values and leave output provisional. This prototype does not execute these models. Numeric imputation is available only for validated numeric columns, never identifiers.')
    export_review=[dict(r,reason=explanations.get(r['id'],{}).get('reasons','Assessment unavailable — see app message'),suggested_plan=explanations.get(r['id'],{}).get('suggested_plan','Not generated')) for r in review]
    st.download_button('Download review Excel form',review_workbook(summary,export_review,choices),'proposed_cleaning_plan.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    st.caption('Excel includes Summary and Review sheets with dropdowns. Confirm choices in this app; importing an edited workbook is not supported.')
    loss=sum(any(r['column'] in row and (row[r['column']] is None or str(row[r['column']]).strip().casefold() in {v.strip().casefold() for v in state['contract']['missing_tokens']}) for r in review if choices[r['id']]=='Complete-case: delete rows missing this column') for row in state['rows'])
    st.write(f'Combined complete-case row loss for current choices: {loss} / {len(state["rows"])}.')
    selected=[r['id'] for r in review if choices[r['id']]=='Apply suggested normalization']
    note=st.text_input('Decision rationale / reviewer note',key='review_note-'+project_id+'-'+str(state['round']),on_change=persist)
    with st.form('review-'+str(state['round'])):
        left,right=st.columns(2)
        apply=left.form_submit_button('Apply selected actions',type='primary',disabled=bool(invalid) or not explanations)
        cancel=right.form_submit_button('Cancel further cleaning')
    if apply or cancel:
        try:
            run.setdefault('reviews',[]).append({'round':state['round'],'approved':selected if apply else [],'cancelled':bool(cancel),'llm_review':explanations,'treatments':choices,'importance':importance,'note':note,'at':datetime.now(timezone.utc).isoformat()})
            with st.spinner('Applying approved tools and validating…'):
                resume_agent(run['graph'],run['config'],selected if apply else [],cancel=bool(cancel),treatments=choices if apply else {},importance=importance)
            if not run['graph'].get_state(run['config']).next:
                run['finished_seconds']=round(time.monotonic()-run['started_clock'],2)
            persist()
            st.rerun()
        except Exception as exc:
            run['error']=str(exc)
            st.error(str(exc))
elif not snapshot.next:
    st.subheader('2 · Review completed')
    if state.get('status')=='cancelled':
        st.warning('Further cleaning cancelled. Earlier approved changes, if any, remain visible and audited; the original dataset is preserved.')
    elif state.get('issues') or state.get('remaining_actions'):
        st.warning('Cleaning completed with unresolved findings. Review flagged clinical/data issues before downstream analysis.')
    else:
        st.success('No findings from the configured checks. This does not establish overall clinical validity.')

left,right=st.columns(2)
with left:
    st.subheader('Original data')
    st.dataframe(display_rows(state['original']),hide_index=True,width='stretch')
with right:
    st.subheader('Current / cleaned data')
    st.dataframe(display_rows(state['rows']),hide_index=True,width='stretch')

with st.expander('Quality findings',expanded=bool(state.get('issues'))):
    if state.get('issues'): st.dataframe(pd.DataFrame(state['issues']),hide_index=True,width='stretch')
    else: st.write('Final checks run after approval. Missing data and implausible values are never imputed or corrected automatically.')
with st.expander('Pending methods / assessments'):
    st.json(state.get('pending_methods',[]))
with st.expander('Remaining or declined cleaning opportunities'):
    st.json(state.get('remaining_actions',[]))
with st.expander('Cell-level audit log'):
    st.json(state.get('audit',[]))
with st.expander('LangGraph execution trace and API usage'):
    st.json({'trace':state.get('trace',[]),'api_calls':state.get('calls',[])})
with st.expander('Graph architecture'):
    st.code(run['graph'].get_graph().draw_mermaid(),language='mermaid')

if not snapshot.next and not run['error']:
    st.subheader('3 · Export results')
    metadata={'filename':run['filename'],'source_sha256':run['source_hash'],'started_at':run['started_at'],
              'elapsed_wall_seconds':run.get('finished_seconds',round(time.monotonic()-run['started_clock'],2)),
              'mode':state['mode'],'model':state['model'] if state['mode']=='OpenAI planner' else None,
              'synthetic':run['is_sample'],'status':state['status'],
              'note':'Wall time includes waiting/review. It is not measured active human labor or ROI.'}
    report={'metadata':metadata,'contract':state['contract'],'original':state['original'],'cleaned':state['rows'],
            'audit':state.get('audit',[]),'issues':state.get('issues',[]),'trace':state.get('trace',[]),
            'remaining_actions':state.get('remaining_actions',[]),'pending_methods':state.get('pending_methods',[]),'study_objectives':run['objectives'],
            'diagnostic_findings':detect_issues(state['rows'],state['columns'],state['contract']),'api_calls':state.get('calls',[]),'reviews':run.get('reviews',[])}
    bundle=io.BytesIO()
    with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('original_input.csv',run['source_bytes'])
        z.writestr('cleaned.csv',csv_bytes(state['rows'],state['columns']))
        z.writestr('audit_report.json',json.dumps(report,indent=2,ensure_ascii=False))
    a,b,c=st.columns(3)
    a.download_button('Cleaned CSV',csv_bytes(state['rows'],state['columns']),'cleaned.csv','text/csv',width='stretch')
    b.download_button('Review workbook',excel_bundle(state,metadata),'cleaning_review.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',width='stretch')
    c.download_button('Full audit bundle',bundle.getvalue(),'cleaning_audit.zip','application/zip',width='stretch')
    st.caption('The audit bundle contains the original input and all record-level changes. CSV preserves source strings; the workbook stores strings as text for spreadsheet review. Nulls export as empty CSV cells and remain distinguishable in JSON.')

# Save results/settings on each completed rerun, including completed and cancelled runs.
persist()
