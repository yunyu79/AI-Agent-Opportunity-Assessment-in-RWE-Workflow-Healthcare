"""Descriptive full-file quality statistics; repeated values are not always errors."""
from collections import Counter
from statistics import median
from cleaning import ROW, as_number
from diagnostics import detect_issues
from review import is_missing


def quality_summary(rows, columns, contract):
    findings=detect_issues(rows,columns,contract)
    n=len(rows);stats=[]
    outlier_rows=set()
    for col in columns:
        observed=[r[col] for r in rows if not is_missing(r[col],contract)]
        counts=Counter(observed)
        repeated=[count for count in counts.values() if count>1]
        outliers={i for f in findings if f['column']==col and f['issue']=='Statistical outlier (IQR)' for i in f['source_rows']}
        outlier_rows.update(outliers)
        outside={i for f in findings if f['column']==col and f['issue']=='Outside allowed range' for i in f['source_rows']}
        nums=[as_number(v) for v in observed] if col in contract['numeric_columns'] else []
        nums=[v for v in nums if v is not None and v.is_finite()]
        stats.append({'column':col,'missing_count':n-len(observed),'missing_percent':100*(n-len(observed))/n if n else None,
                      'outlier_count':len(outliers),'outlier_percent_of_all_rows':100*len(outliers)/n if n else None,
                      'outside_allowed_range':len(outside),'distinct_nonmissing_values':len(counts),
                      'repeated_value_groups':len(repeated),'rows_in_repeated_values':sum(repeated),
                      'excess_repeated_values':sum(count-1 for count in repeated),
                      'finite_numeric_count':len(nums),'minimum':str(min(nums)) if nums else None,
                      'median':str(median(nums)) if nums else None,'maximum':str(max(nums)) if nums else None})
    rowcounts=Counter(tuple(r[c] for c in columns) for r in rows)
    duplicate_sizes=[count for count in rowcounts.values() if count>1]
    overall={'total_rows':n,'rows_with_statistical_outliers':len(outlier_rows),
             'exact_duplicate_groups':len(duplicate_sizes),'rows_in_exact_duplicate_groups':sum(duplicate_sizes),
             'excess_exact_duplicate_rows':sum(count-1 for count in duplicate_sizes),
             'exact_duplicate_row_percent':100*sum(duplicate_sizes)/n if n else None}
    return overall,stats
