"""Allowlisted, deterministic data cleaning tools and row/cell provenance."""
import copy
import csv
import hashlib
import io
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

ROW = '__source_row__'
TOOLS = {'trim', 'normalize_missing', 'normalize_category', 'normalize_date', 'normalize_number', 'drop_exact_duplicates'}
DEFAULT_CONTRACT = {
    'required_columns': ['patient_id', 'age', 'sex', 'admission_date', 'discharge_date', 'total_cost'],
    'identifier_columns': ['patient_id'],
    'missing_tokens': ['', 'NA', 'N/A', 'NULL'],
    'numeric_columns': ['age', 'total_cost'],
    'date_columns': ['admission_date', 'discharge_date'],
    'category_maps': {'sex': {'m': 'M', 'male': 'M', 'f': 'F', 'female': 'F', 'unknown': 'Unknown'}},
    'numeric_ranges': {'age': [0, 120], 'total_cost': [0, None]},
    'date_order_pairs': [['admission_date', 'discharge_date']]
}


def load_csv(data):
    if len(data) > 5 * 1024 * 1024:
        raise ValueError('CSV exceeds 5 MB.')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError('Use a UTF-8 CSV file.') from exc
    parsed = list(csv.reader(io.StringIO(text), strict=True))
    if len(parsed) < 2:
        raise ValueError('CSV needs a header and at least one data row.')
    columns = parsed[0]
    if len(columns) > 100 or len(parsed) > 10001:
        raise ValueError('Limit: 100 columns and 10,000 data rows.')
    if any(not c or len(c) > 150 for c in columns) or len(set(columns)) != len(columns):
        raise ValueError('Column headers must be unique and nonempty (up to 150 characters).')
    if ROW in columns:
        raise ValueError(f'{ROW} is reserved for provenance.')
    rows = []
    for i, values in enumerate(parsed[1:], 2):
        if len(values) != len(columns):
            raise ValueError(f'CSV record {i} has {len(values)} fields; expected {len(columns)}.')
        if any(len(v) > 10000 for v in values):
            raise ValueError('A cell exceeds 10,000 characters.')
        rows.append({ROW: i, **dict(zip(columns, values))})
    return rows, columns


def validate_contract(contract, columns):
    expected = set(DEFAULT_CONTRACT)
    if not isinstance(contract, dict) or set(contract) != expected:
        raise ValueError('Contract keys must match the supplied example contract.')
    for key in ['required_columns', 'identifier_columns', 'numeric_columns', 'date_columns', 'missing_tokens']:
        if not isinstance(contract[key], list) or any(not isinstance(v, str) for v in contract[key]):
            raise ValueError(f'{key} must be a list of strings.')
    if any(c == ROW for key in ['required_columns', 'identifier_columns', 'numeric_columns', 'date_columns'] for c in contract[key]):
        raise ValueError('Source row IDs cannot be transformed.')
    if not isinstance(contract['category_maps'], dict) or not isinstance(contract['numeric_ranges'], dict):
        raise ValueError('category_maps and numeric_ranges must be objects.')
    protected = set(contract['identifier_columns']) | {c for c in columns if c.lower() == 'id' or c.lower().endswith('_id')}
    transforms = set(contract['numeric_columns']) | set(contract['date_columns']) | set(contract['category_maps'])
    if protected & transforms:
        raise ValueError('Identifiers cannot be cast or category/date mapped. Leading zeros must be retained.')
    if set(contract['numeric_columns']) & (set(contract['date_columns']) | set(contract['category_maps'])):
        raise ValueError('A column cannot have conflicting transformation types.')
    if set(contract['date_columns']) & set(contract['category_maps']):
        raise ValueError('A column cannot have conflicting transformation types.')
    for col, mapping in contract['category_maps'].items():
        if col == ROW or not isinstance(mapping, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k,v in mapping.items()):
            raise ValueError('Each category map must contain string-to-string entries.')
        normalized = [k.strip().casefold() for k in mapping]
        if len(set(normalized)) != len(normalized):
            raise ValueError('Category keys must be unique after case/whitespace normalization.')
    for col, bounds in contract['numeric_ranges'].items():
        if col not in contract['numeric_columns'] or not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError('Ranges require a configured numeric column and [minimum, maximum].')
        if any(x is not None and (type(x) not in (int, float) or not Decimal(str(x)).is_finite()) for x in bounds):
            raise ValueError('Range bounds must be finite numbers or null.')
        if bounds[0] is not None and bounds[1] is not None and bounds[0] > bounds[1]:
            raise ValueError('Minimum range exceeds maximum.')
    if not isinstance(contract['date_order_pairs'], list):
        raise ValueError('date_order_pairs must be a list.')
    for pair in contract['date_order_pairs']:
        if not isinstance(pair, list) or len(pair) != 2 or any(x not in contract['date_columns'] for x in pair):
            raise ValueError('Date order pairs must name two configured date columns.')
    return copy.deepcopy(contract)


def as_number(value):
    if value is None or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', value.strip()):
        return None
    try:
        n = Decimal(value.strip())
        return n if n.is_finite() else None
    except InvalidOperation:
        return None


def as_date(value):
    if value is None:
        return None
    text = value.strip()
    if not re.fullmatch(r'\d{4}[-/]\d{2}[-/]\d{2}', text):
        return None
    try:
        return date.fromisoformat(text.replace('/', '-')).isoformat()
    except ValueError:
        return None


def proposed_value(tool, value, column, contract):
    if tool == 'trim':
        return value.strip() if isinstance(value, str) else value
    if tool == 'normalize_missing':
        tokens = {v.strip().casefold() for v in contract['missing_tokens']}
        return None if isinstance(value, str) and value.strip().casefold() in tokens else value
    if value is None:
        return None
    if tool == 'normalize_category':
        mapping = {k.strip().casefold():v for k,v in contract['category_maps'].get(column, {}).items()}
        return mapping.get(value.strip().casefold(), value)
    if tool == 'normalize_date':
        return as_date(value) or value
    if tool == 'normalize_number':
        n = as_number(value)
        if n is None:
            return value  # Invalid strings are retained, never silently coerced to missing.
        text = format(n, 'f')
        if '.' in text:
            text = text.rstrip('0').rstrip('.')
        return '0' if n == 0 else text
    return value


def fingerprint(row, columns):
    return tuple(row[c] for c in columns)


def propose(rows, columns, contract):
    candidates = []
    by_tool = [('trim', columns), ('normalize_missing', columns),
               ('normalize_category', list(contract['category_maps'])),
               ('normalize_date', contract['date_columns']), ('normalize_number', contract['numeric_columns'])]
    reasons = {'trim': 'Remove leading/trailing whitespace only.',
               'normalize_missing': 'Replace only configured missing tokens with null.',
               'normalize_category': 'Apply the explicit, reviewer-visible category dictionary.',
               'normalize_date': 'Normalize valid YYYY-MM-DD or YYYY/MM/DD dates only.',
               'normalize_number': 'Canonicalize numeric text without changing its mathematical value.'}
    for tool, cols in by_tool:
        for col in cols:
            if col not in columns:
                continue
            count = sum(proposed_value(tool,r[col],col,contract) != r[col] for r in rows)
            if count:
                candidates.append({'id': f'{tool}:{col}', 'tool': tool, 'column': col,
                                   'affected_cells_estimate': count, 'reason': reasons[tool]})
    duplicate_count = len(rows) - len({fingerprint(r, columns) for r in rows})
    if duplicate_count:
        candidates.append({'id': 'drop_exact_duplicates', 'tool': 'drop_exact_duplicates', 'column': None,
                           'affected_cells_estimate': duplicate_count,
                           'reason': 'Remove rows identical across every source column; retain the first. Repeated patient IDs alone are not duplicates.'})
    return candidates


def profile(rows, columns, contract):
    candidates = propose(rows, columns, contract)
    tokens = {v.strip().casefold() for v in contract['missing_tokens']}
    return {'rows': len(rows), 'columns': columns,
            'missing_by_column': {c: sum(r[c] is None or (isinstance(r[c],str) and r[c].strip().casefold() in tokens) for r in rows) for c in columns},
            'duplicate_rows': len(rows)-len({fingerprint(r,columns) for r in rows}),
            'candidates': candidates}


def execute(rows, columns, contract, candidates, selected_ids, round_number=1):
    allowed = {a['id']:a for a in candidates}
    if not isinstance(selected_ids,list) or any(not isinstance(x,str) for x in selected_ids) or len(set(selected_ids)) != len(selected_ids) or any(x not in allowed for x in selected_ids):
        raise ValueError('Only distinct action IDs from the reviewed plan may be executed.')
    output = copy.deepcopy(rows)
    audit = []
    for action_id in selected_ids:
        action = allowed[action_id]
        tool, col = action['tool'], action['column']
        if tool not in TOOLS:
            raise ValueError('Unknown tool.')
        if tool == 'drop_exact_duplicates':
            seen, kept = set(), []
            for row in output:
                key = fingerprint(row, columns)
                if key in seen:
                    audit.append({'round': round_number, 'source_row': row[ROW], 'action': tool, 'column': '*',
                                  'before': copy.deepcopy(row), 'after': None})
                else:
                    seen.add(key)
                    kept.append(row)
            output = kept
        else:
            if col not in columns:
                raise ValueError('Unknown column.')
            for row in output:
                old = row[col]
                new = proposed_value(tool,old,col,contract)
                if old != new:
                    audit.append({'round': round_number, 'source_row': row[ROW], 'action': tool,
                                  'column': col, 'before': old, 'after': new})
                    row[col] = new
    return output, audit


def quality_issues(rows, columns, contract):
    issues = []
    for col in contract['required_columns']:
        if col not in columns:
            issues.append({'source_row': None, 'column': col, 'issue': 'Required column missing', 'value': None})
    missing_tokens = {v.strip().casefold() for v in contract['missing_tokens']}
    for row in rows:
        def flag(col, message):
            issues.append({'source_row':row[ROW], 'column':col, 'issue':message, 'value':row.get(col)})
        for col in contract['required_columns']:
            if col in columns and (row[col] is None or (isinstance(row[col],str) and row[col].strip().casefold() in missing_tokens)):
                flag(col,'Required value missing; no imputation applied')
        for col in contract['numeric_columns']:
            if col not in columns or row[col] is None:
                continue
            number = as_number(row[col])
            if number is None:
                flag(col,'Invalid numeric text retained')
            else:
                low, high = contract['numeric_ranges'].get(col,[None,None])
                if (low is not None and number < Decimal(str(low))) or (high is not None and number > Decimal(str(high))):
                    flag(col,'Outside configured plausibility range; retained for review')
        for col in contract['date_columns']:
            if col in columns and row[col] is not None and not as_date(row[col]):
                flag(col,'Invalid or ambiguous date retained; only year-first dates are normalized')
        for col, mapping in contract['category_maps'].items():
            if col in columns and row[col] is not None and row[col] not in mapping.values():
                flag(col,'Unmapped category retained')
        for start,end in contract['date_order_pairs']:
            left,right = as_date(row.get(start)),as_date(row.get(end))
            if left and right and right < left:
                flag(end,'Date precedes '+start+'; neither date was changed')
    return issues


def csv_bytes(rows, columns):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow([ROW]+columns)
    for row in rows:
        writer.writerow([row[ROW]]+[row[c] if row[c] is not None else '' for c in columns])
    return out.getvalue().encode('utf-8-sig')


def data_hash(data):
    return hashlib.sha256(data).hexdigest()
