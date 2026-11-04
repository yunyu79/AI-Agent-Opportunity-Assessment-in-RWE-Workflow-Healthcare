"""Repository-owned demo inputs and executable contracts; no CSV regeneration."""
import copy
import json
from pathlib import Path

from cleaning import DEFAULT_CONTRACT, load_csv, validate_contract

ROOT = Path(__file__).resolve().parent
DEMO_TABLES = ('patient', 'medication', 'procedure')
DATASETS = {f'{name}.csv (500 rows)': name for name in DEMO_TABLES}
LEGACY_SAMPLE = 'Synthetic RWE sample'


def demo_input(name):
    if name not in DEMO_TABLES:
        raise ValueError('Choose patient, medication or procedure.')
    path = ROOT / 'data' / 'demo' / f'{name}.csv'
    data = path.read_bytes()
    _, columns = load_csv(data)
    contract = json.loads((ROOT / 'contracts' / f'{name}.json').read_text(encoding='utf-8'))
    return data, path.name, validate_contract(contract, columns)


def contract_for_source(source):
    if source in DATASETS:
        return demo_input(DATASETS[source])[2]
    return copy.deepcopy(DEFAULT_CONTRACT)
