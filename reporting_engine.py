from dataclasses import asdict
import io
import pandas as pd

def results_dataframe(conventional, mrt, conventional_score, mrt_score):
    return pd.DataFrame([
        {'Option': 'Conventional Expansion', **asdict(conventional), 'Decision Score': conventional_score},
        {'Option': 'MRT Pharma Hybrid', **asdict(mrt), 'Decision Score': mrt_score},
    ])

def excel_bytes(results, assumptions, score_breakdown, sensitivity, statistics):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        results.to_excel(writer, index=False, sheet_name='Results')
        assumptions.to_excel(writer, index=False, sheet_name='Assumptions')
        score_breakdown.to_excel(writer, index=False, sheet_name='Decision Score')
        sensitivity.to_excel(writer, index=False, sheet_name='Sensitivity')
        statistics.to_excel(writer, index=False, sheet_name='Search Statistics')
    return buffer.getvalue()
