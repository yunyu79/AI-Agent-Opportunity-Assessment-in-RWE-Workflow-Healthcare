"""Local JSON project snapshots; restoration never replays approved tools."""
import base64
import json
import os
import re
import time
import uuid
from pathlib import Path


def project_path(project_id):
    if not re.fullmatch(r'[a-f0-9]{32}', project_id):
        raise ValueError('Invalid project ID.')
    root=Path(os.environ.get('CLEANING_PROJECT_DIR',Path(__file__).parent/'.local_projects'))
    root.mkdir(parents=True,exist_ok=True)
    return root/(project_id+'.json')


def save_project(project_id, settings, run=None):
    payload={'version':1,'settings':settings,'run':None}
    if run and run['graph'].get_state(run['config']).values:
        snapshot=run['graph'].get_state(run['config'])
        metadata={k:v for k,v in run.items() if k not in ('graph','config','source_bytes','started_clock')}
        metadata['elapsed_saved']=max(0,time.monotonic()-run.get('started_clock',time.monotonic()))
        payload['run']={'metadata':metadata,'source_base64':base64.b64encode(run['source_bytes']).decode(),
                        'values':snapshot.values,'waiting_review':snapshot.next==('human_review',)}
    path=project_path(project_id)
    temp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('x',encoding='utf-8') as stream:
            os.chmod(temp,0o600)
            json.dump(payload,stream,ensure_ascii=False,allow_nan=False)
        os.replace(temp,path)
    finally:
        temp.unlink(missing_ok=True)


def load_project(project_id):
    path=project_path(project_id)
    if not path.exists():return None
    payload=json.loads(path.read_text(encoding='utf-8'))
    if payload.get('version')!=1:raise ValueError('Unsupported saved project version.')
    if payload.get('run'):
        from agent import build_agent
        stored=payload['run'];graph=build_agent()
        config={'configurable':{'thread_id':uuid.uuid4().hex},'recursion_limit':30}
        if stored['waiting_review']:
            graph.update_state(config,stored['values'],as_node='plan')
            # Create a fresh human interrupt only; no profiling, API call or apply node.
            graph.invoke(None,config)
        else:
            graph.update_state(config,stored['values'],as_node='finish')
        payload['run']={**stored['metadata'],'graph':graph,'config':config,
                        'source_bytes':base64.b64decode(stored['source_base64']),
                        'started_clock':time.monotonic()-stored['metadata'].get('elapsed_saved',0)}
    return payload


def close_project(project_id):
    project_path(project_id).unlink(missing_ok=True)
