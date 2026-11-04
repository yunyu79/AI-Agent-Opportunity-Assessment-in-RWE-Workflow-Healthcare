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

from agent import build_agent, initial_state, resume_agent, load_skill
from demo_data import DATASETS, LEGACY_SAMPLE, contract_for_source, demo_input
from cleaning import DEFAULT_CONTRACT, ROW, csv_bytes, data_hash, load_csv

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='RWE Data Cleaning Agent',page_icon='🧹',layout='wide')
st.title('RWE Data Cleaning Agent')
st.caption('LangGraph · profile → plan → human review → cleaning tools → validation')
st.info('Use synthetic or de-identified data. Offline mode uses deterministic rules; OpenAI mode uses an LLM to select among allowed tools. Every change requires your approval.')


def display_rows(rows):
    return pd.DataFrame(rows).fillna('∅')




with st.sidebar:
    st.header('1 · Choose data')
    source = st.radio('Dataset',list(DATASETS) + [LEGACY_SAMPLE,'Upload CSV'])
    uploaded = st.file_uploader('UTF-8 CSV',type=['csv'],disabled=source!='Upload CSV')
    mode = st.selectbox('Planner',['Offline rules','OpenAI planner'])
    model = st.text_input('Model',value=os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),disabled=mode!='OpenAI planner')
    consent = st.checkbox('Allow sending column names, aggregate counts and the contract to OpenAI.',disabled=mode!='OpenAI planner')
    st.caption('Patient rows and sample cell values are excluded from the planner request. No API key is entered or displayed here.')
    with st.expander('Edit data contract'):
        contract_text = st.text_area('Contract JSON',value=json.dumps(contract_for_source(source),indent=2),height=400,key='contract-'+source)
    start = st.button('Profile and propose plan',type='primary',width='stretch')
    reset = st.button('Clear current run',width='stretch')
    st.caption('In-memory checkpoints only. Export before restarting or clearing the run.')

if reset:
    st.session_state.pop('run',None)
    st.rerun()

if start:
    try:
        if source in DATASETS:
            data,filename,_=demo_input(DATASETS[source])
        elif source==LEGACY_SAMPLE:
            data=(ROOT/'sample_rwe.csv').read_bytes()
            filename='sample_rwe.csv'
        elif uploaded:
            data,filename=uploaded.getvalue(),uploaded.name
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
                              'source_bytes':data,'filename':filename,'started_at':datetime.now(timezone.utc).isoformat(),
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
    st.caption('Edit SKILL.md in the project folder. OpenAI planning reads it on each call; offline rules follow the JSON contract. Filling and standard mapping tools are not implemented.')

run=st.session_state.get('run')
if not run:
    st.subheader('Preview selected input')
    if source in DATASETS:
        preview_data,preview_name,_=demo_input(DATASETS[source])
    elif source==LEGACY_SAMPLE:
        preview_data,preview_name=(ROOT/'sample_rwe.csv').read_bytes(),'sample_rwe.csv'
    elif uploaded:
        preview_data,preview_name=uploaded.getvalue(),uploaded.name
    else:
        st.write('Upload a CSV, or choose one of the three 500-row demonstrations.')
        st.stop()
    try:
        rows,_=load_csv(preview_data)
        st.caption(f'{preview_name}: {len(rows)} source rows. Showing the first 20; the agent processes the entire selected file.')
        st.dataframe(display_rows(rows[:20]),hide_index=True,width='stretch')
    except ValueError as exc:
        st.error(str(exc))
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

with st.expander('Missingness by column',expanded=True):
    report=state['profile']
    st.dataframe(pd.DataFrame([
        {'column':c,'missing_count':report['missing_by_column'][c],
         'missing_percent':report['missing_percent_by_column'][c],
         'literal_unknown_count':report['unknown_by_column'][c],
         'review_over_20_percent':c in report['high_missing_columns']}
        for c in state['columns']
    ]),hide_index=True,width='stretch')
    st.caption('Missing counts follow the configured null tokens; Unknown is counted separately unless explicitly configured as missing. Over 20% triggers review, not automatic filling or exclusion. Structural blanks such as death_date for living patients remain valid.')

if snapshot.next==('human_review',) and not run['error']:
    st.subheader('2 · Review the proposed plan')
    st.write(state['rationale'])
    plan=state['plan']
    st.dataframe(pd.DataFrame(plan),hide_index=True,width='stretch')
    st.caption('Counts estimate each action independently; overlapping actions may change fewer cells. Exact duplicate removal is optional: identical rows can still represent legitimate repeated events.')
    options=[a['id'] for a in plan]
    default=[a for a in options if a!='drop_exact_duplicates']
    with st.form('review-'+str(state['round'])):
        selected=st.multiselect('Approved actions',options,default=default)
        note=st.text_input('Reviewer note (optional)')
        left,right=st.columns(2)
        apply=left.form_submit_button('Apply selected actions',type='primary')
        cancel=right.form_submit_button('Cancel further cleaning')
    if apply or cancel:
        try:
            run.setdefault('reviews',[]).append({'round':state['round'],'approved':selected if apply else [],'cancelled':bool(cancel),'note':note,'at':datetime.now(timezone.utc).isoformat()})
            with st.spinner('Applying approved tools and validating…'):
                resume_agent(run['graph'],run['config'],selected if apply else [],cancel=bool(cancel))
            if not run['graph'].get_state(run['config']).next:
                run['finished_seconds']=round(time.monotonic()-run['started_clock'],2)
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
            'remaining_actions':state.get('remaining_actions',[]),
            'api_calls':state.get('calls',[]),'reviews':run.get('reviews',[])}
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
