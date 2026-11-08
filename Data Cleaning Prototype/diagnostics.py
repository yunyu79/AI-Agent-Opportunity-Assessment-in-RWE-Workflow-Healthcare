"""Read-only issue detection; each variable/issue type remains separate."""
from collections import defaultdict
from decimal import Decimal
from cleaning import ROW, as_number, as_date


def detect_issues(rows, columns, contract):
    findings=[]
    tokens={v.strip().casefold() for v in contract['missing_tokens']}
    def missing(v):return v is None or isinstance(v,str) and v.strip().casefold() in tokens
    def add(col,kind,ids,evidence):
        if ids or kind=='Required column absent':
            findings.append(dict(column=col,issue=kind,source_rows=sorted(set(ids)),reason=evidence))
    for col in contract['required_columns']:
        if col not in columns:add(col,'Required column absent',[], 'The configured schema requires this column, but it is absent from the input.')
    for col in columns:
        observed=[r for r in rows if not missing(r[col])]
        if col in contract['numeric_columns']:
            valid=[];invalid=[];outside=[]
            lo,hi=contract['numeric_ranges'].get(col,[None,None])
            for r in observed:
                n=as_number(r[col])
                if n is None or not n.is_finite():invalid.append(r[ROW]);continue
                valid.append((r[ROW],n))
                if lo is not None and n<Decimal(str(lo)) or hi is not None and n>Decimal(str(hi)):outside.append(r[ROW])
            add(col,'Invalid numeric value',invalid,'Nonmissing values cannot be parsed as finite numbers; possible format or entry problems.')
            add(col,'Outside allowed range',outside,f'Values violate configured bounds [{lo}, {hi}]. Verify units, entry and domain validity.')
            if col not in contract['identifier_columns'] and col.lower()!='id' and not col.lower().endswith('_id') and len(valid)>=4:
                nums=sorted(n for _,n in valid)
                def quantile(q):
                    pos=Decimal(q)*(len(nums)-1);i=int(pos);return nums[i]+(nums[min(i+1,len(nums)-1)]-nums[i])*(pos-i)
                q1,q3=quantile('.25'),quantile('.75');iqr=q3-q1
                if iqr>0:
                    low,high=q1-Decimal('1.5')*iqr,q3+Decimal('1.5')*iqr
                    add(col,'Statistical outlier (IQR)',[i for i,n in valid if n<low or n>high],f'Outside 1.5×IQR fences [{low}, {high}], using {len(valid)} finite observations and linear quartiles. Statistical candidates may be legitimate extremes.')
        if col in contract['date_columns'] or col in ('start_date','end_date'):
            add(col,'Invalid or ambiguous date',[r[ROW] for r in observed if not as_date(r[col])],'Nonmissing values do not parse as supported year-first calendar dates. Check format and validity.')
        if col in contract['category_maps']:
            mapping=contract['category_maps'][col];known={v.strip().casefold() for v in mapping.values()}|{v.strip().casefold() for v in mapping}
            add(col,'Unexpected category',[r[ROW] for r in observed if str(r[col]).strip().casefold() not in known],'Nonmissing category is outside the configured dictionary; verify coding or dictionary completeness.')
        expected_unique=contract.get('duplicate_unique_columns',contract['identifier_columns'])
        allowed_repeats=set(contract.get('allowed_duplicate_columns',[]))
        postal=col.lower().replace('_','').replace(' ','') in ('zip','zipcode','postalcode','postcode')
        if col in expected_unique and col not in allowed_repeats and (not postal or col in contract.get('duplicate_unique_columns',[])):
            groups=defaultdict(list)
            for r in observed:groups[r[col]].append(r[ROW])
            ids=[i for group in groups.values() if len(group)>1 for i in group]
            add(col,'Repeated identifier candidate',ids,'Identifier repeats. This may be a valid repeated event or visit; confirm the study row grain and composite key before treating it as a duplicate.')
    pairs=set(tuple(p) for p in contract['date_order_pairs'])
    if {'start_date','end_date'}<=set(columns):pairs.add(('start_date','end_date'))
    for start,end in sorted(pairs):
        if start not in columns or end not in columns:continue
        strict=(start,end)==('start_date','end_date')
        ids=[]
        for r in rows:
            a,b=as_date(r[start]),as_date(r[end])
            if a and b and (b<=a if strict else b<a):ids.append(r[ROW])
        add(end,'Date order violation: '+start,ids,f'Requires {end} {">" if strict else ">="} {start}. Equality is '+('invalid for this strict interval.' if strict else 'allowed for same-day events.'))
    groups=defaultdict(list)
    for r in rows:groups[tuple(r[c] for c in columns)].append(r[ROW])
    add('All source columns','Exact duplicate rows',[i for group in groups.values() if len(group)>1 for i in group],'Rows have identical values in every source column (provenance excluded). Counts include all group members, not just excess rows; confirm survivors before removal.')
    return findings
