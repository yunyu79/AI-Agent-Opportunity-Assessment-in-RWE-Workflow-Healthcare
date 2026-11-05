"""Objective-led, explicit-decision cleaning; source values stay strings."""
import copy
import csv
import io
from collections import defaultdict
from decimal import Decimal
from cleaning import ROW, as_number


def missing(value, tokens):
    return value is None or value in tokens


def missing_report(rows, columns, importance, tokens):
    result = []
    for col in columns:
        count = sum(missing(r[col], tokens) for r in rows)
        pct = 100 * count / len(rows) if rows else None
        role = importance.get(col, 'Unconfirmed')
        rule = None if pct is None or count == 0 else ('M4' if pct > 20 else 'M3' if pct >= 5 else 'M1' if role == 'Non-critical' else 'M2')
        recommendation = {
            'M1': 'Retain missing values; consider excluding this non-critical variable from analysis. Complete-case only after assessing joint row loss.',
            'M2': 'Assess missingness patterns and sample loss; low missingness alone does not justify deletion or imputation.',
            'M3': 'Compare retention, complete-case and suitable imputation; assess group patterns and sensitivity.',
            'M4': 'Assess importance, mechanism and recoverability first. Consider exclusion, MICE, validated ML, proxy or additional collection.',
        }.get(rule, 'No missing values.' if rows else 'Empty table: percentage undefined.')
        result.append(dict(column=col, missing_count=count, denominator=len(rows), missing_percent=pct, importance=role, rule=rule, recommendation=recommendation))
    return result


def duplicate_groups(rows, columns, keys=None):
    keys = keys or columns
    groups = defaultdict(list)
    for row in rows:
        # Missing business keys do not establish entity identity.
        if keys != columns and any(row[k] in (None, '') for k in keys):
            continue
        groups[tuple(row[k] for k in keys)].append(row)
    return [dict(group=f'D{i+1}', rows=members) for i, members in enumerate(g for g in groups.values() if len(g) > 1)]


def quantile(values, q):
    ordered = sorted(values)
    pos = Decimal(str(q)) * (len(ordered)-1)
    lo = int(pos)
    hi = min(lo+1, len(ordered)-1)
    return ordered[lo] + (ordered[hi]-ordered[lo]) * (pos-lo)


def outliers(rows, columns):
    found = []
    for col in columns:
        values = [(r, as_number(r[col])) for r in rows]
        values = [(r, v) for r, v in values if v is not None and v.is_finite()]
        if len(values) < 4:
            continue
        nums = [v for _, v in values]
        q1, q3 = quantile(nums, .25), quantile(nums, .75)
        if q3 == q1:
            continue
        low, high = q1-Decimal('1.5')*(q3-q1), q3+Decimal('1.5')*(q3-q1)
        p5, p95 = quantile(nums, .05), quantile(nums, .95)
        for row, value in values:
            if value < low or value > high:
                found.append(dict(source_row=row[ROW], column=col, value=row[col], low=str(low), high=str(high), p5=str(p5), p95=str(p95), tail='lower' if value < low else 'upper', possible_cause='Unknown. Check units, entry/decimal errors, equipment limits, subgroup differences or a genuine extreme; none established by IQR alone.'))
    return found


def apply_missing(rows, columns, decisions, tokens):
    output, cols, audit = copy.deepcopy(rows), list(columns), []
    for col, choice in decisions.items():
        if col not in cols or choice not in ('Keep', 'Drop column', 'Drop missing rows', 'Median', 'Mode'):
            raise ValueError('Unknown missing-value decision.')
        affected = [r for r in output if missing(r[col], tokens)]
        if choice == 'Drop column':
            audit.append(dict(rule='missing', column=col, decision=choice, count=len(output), originals=[{ROW:r[ROW], 'value':r[col]} for r in output]))
            cols.remove(col)
            for r in output: del r[col]
        elif choice == 'Drop missing rows':
            ids = {r[ROW] for r in affected}
            audit.extend(dict(rule='missing', decision=choice, source_row=r[ROW], before=r, after=None) for r in affected)
            output = [r for r in output if r[ROW] not in ids]
        elif choice in ('Median', 'Mode') and affected:
            observed = [r[col] for r in output if not missing(r[col], tokens)]
            if not observed: raise ValueError(f'{col}: no observed values to impute.')
            if choice == 'Median':
                nums = [as_number(v) for v in observed]
                if any(v is None or not v.is_finite() for v in nums): raise ValueError(f'{col}: median requires finite numeric values.')
                fill = str(quantile(nums, .5))
            else:
                counts = {v:observed.count(v) for v in set(observed)}
                modes = [v for v,n in counts.items() if n == max(counts.values())]
                if len(modes) != 1: raise ValueError(f'{col}: tied mode; choose a different method.')
                fill = modes[0]
            for r in affected:
                audit.append(dict(rule='missing', decision=choice, source_row=r[ROW], column=col, before=r[col], after=fill))
                r[col] = fill
    return output, cols, audit


def apply_duplicates(rows, groups, deletions):
    allowed = {r[ROW] for g in groups for r in g['rows']}
    if not set(deletions) <= allowed: raise ValueError('Deletion outside reviewed duplicate candidates.')
    return [copy.deepcopy(r) for r in rows if r[ROW] not in deletions], [dict(rule='duplicates', decision='Delete selected row', source_row=r[ROW], before=r, after=None) for r in rows if r[ROW] in deletions]


def apply_outliers(rows, candidates, decisions):
    output, audit = copy.deepcopy(rows), []
    deleted = set()
    for item in candidates:
        key = (item['source_row'], item['column'])
        choice = decisions.get(key, 'Keep')
        if choice not in ('Keep', 'Delete row', 'Set missing', 'Cap upper P95', 'Cap P5/P95'):
            raise ValueError('Unknown outlier decision.')
        row = next(r for r in output if r[ROW] == key[0])
        old = row[key[1]]
        if choice == 'Delete row': deleted.add(key[0])
        elif choice == 'Set missing': row[key[1]] = None
        elif choice in ('Cap upper P95', 'Cap P5/P95'):
            if choice == 'Cap upper P95' and item['tail'] == 'lower': raise ValueError('Lower-tail values cannot be capped upward to P95.')
            row[key[1]] = item['p5'] if item['tail'] == 'lower' else item['p95']
        if choice != 'Keep': audit.append(dict(rule='outliers', decision=choice, source_row=key[0], column=key[1], before=old, after=row[key[1]], reference=item))
    audit.extend(dict(rule='outliers', decision='Delete row record', source_row=r[ROW], before=r, after=None) for r in output if r[ROW] in deleted)
    return [r for r in output if r[ROW] not in deleted], audit


def export_csv(rows, columns):
    buf = io.StringIO(newline='')
    writer = csv.writer(buf)
    writer.writerow([ROW]+columns)
    for r in rows: writer.writerow([r[ROW]]+[r[c] for c in columns])
    return buf.getvalue().encode('utf-8-sig')


def validate(original, rows, columns, audit, tokens, numeric_columns, required, keys):
    checks = []
    def check(name, expected, actual):
        checks.append(dict(check=name, expected=expected, actual=actual, status='PASS' if expected == actual else 'FAIL'))
    source_ids = {r[ROW] for r in original}
    ids = [r[ROW] for r in rows]
    removed = {a['source_row'] for a in audit if a.get('after', 'absent') is None and isinstance(a.get('before'), dict)}
    check('Row reconciliation', len(original)-len(removed), len(rows))
    check('Source provenance', True, len(set(ids)) == len(ids) and set(ids) <= source_ids)
    check('Output schema', True, all(set(r) == set(columns)|{ROW} for r in rows))
    invalid = sum(not missing(r[c],tokens) and (as_number(r[c]) is None or not as_number(r[c]).is_finite()) for c in numeric_columns if c in columns for r in rows)
    check('Numeric parsing', 0, invalid)
    check('Required columns', [], [c for c in required if c not in columns])
    encoded = export_csv(rows, columns)
    decoded = list(csv.reader(io.StringIO(encoded.decode('utf-8-sig'))))
    expected = [[str(r[ROW])]+['' if r[c] is None else r[c] for c in columns] for r in rows]
    check('CSV round trip', True, decoded[1:] == expected and decoded[0] == [ROW]+columns)
    checks.append(dict(check='Domain schema / date / range / category checks',expected='Study-specific validation',actual='Review contract findings',status='NOT CHECKED'))
    return checks, encoded
