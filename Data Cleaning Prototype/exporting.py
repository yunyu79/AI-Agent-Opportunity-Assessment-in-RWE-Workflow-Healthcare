"""Text-safe workbook export for data and audit records."""
import io
import json
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

def excel_bundle(state, metadata):
    wb = Workbook()
    wb.remove(wb.active)
    for title,items in [('Original',state['original']),('Cleaned',state['rows']),('Issues',state.get('issues',[])),('Audit',state.get('audit',[])),('Trace',state.get('trace',[])),('Metadata',[metadata])]:
        ws = wb.create_sheet(title)
        keys = list(dict.fromkeys(k for row in items for k in row))
        if not keys:
            ws.append(['No records'])
        else:
            ws.append(keys)
            for row in items:
                values = [json.dumps(row.get(k),ensure_ascii=False) if isinstance(row.get(k),(dict,list)) else row.get(k) for k in keys]
                ws.append(values)
        for cell in ws[1]:
            cell.font = Font(bold=True,color='FFFFFF')
            cell.fill = PatternFill('solid',fgColor='20574D')
        for column in ws.columns:
            ws.column_dimensions[column[0].column_letter].width = 24
            for cell in column[1:]:
                if isinstance(cell.value,str): cell.data_type='s'
                cell.alignment = Alignment(wrap_text=True,vertical='top')
        ws.freeze_panes='A2'
        ws.auto_filter.ref=ws.dimensions
    output=io.BytesIO()
    wb.save(output)
    return output.getvalue()

