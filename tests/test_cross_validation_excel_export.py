from __future__ import annotations

import json

import pandas as pd
from openpyxl import load_workbook

from ashare_f10.cross_validation.exporter import _write_excel


def test_cross_validation_excel_preserves_all_columns(tmp_path) -> None:
    path = tmp_path / "matrix.xlsx"
    detail = pd.DataFrame(
        [
            {
                "comparison_key": "688521|2025-12-31|TOTAL_ASSETS",
                "security_code": "688521",
                "report_date": "2025-12-31",
                "field_key": "TOTAL_ASSETS",
                "field_name_cn": "资产总计",
                "eastmoney_value_num": 12_345.0,
                "official_value_num": 12_345.0,
                "status": "EXACT_MATCH",
                "notes": {"source": "official", "pages": [1, 2]},
            },
            {
                "comparison_key": "688521|2025-12-31|TOTAL_LIABILITIES",
                "security_code": "688521",
                "report_date": "2025-12-31",
                "field_key": "TOTAL_LIABILITIES",
                "field_name_cn": "负债合计",
                "eastmoney_value_num": 6_789.0,
                "official_value_num": 6_789.0,
                "status": "EXACT_MATCH",
                "notes": {"source": "official", "pages": [3]},
            },
        ]
    )
    registry = pd.DataFrame(
        [
            {
                "theme": "财务报表与指标",
                "family": "RPT_F10_FINANCE_GBALANCE",
                "field_key": "TOTAL_ASSETS",
                "field_name_cn": "资产总计",
                "validation_mode": "OFFICIAL_DIRECT",
            }
        ]
    )

    _write_excel(path, [("Detail", detail), ("Registry", registry)])

    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet = workbook["Detail"]
        assert sheet["A2"].value == "688521|2025-12-31|TOTAL_ASSETS"
        assert sheet["B2"].value == "688521"
        assert sheet["D2"].value == "TOTAL_ASSETS"
        assert sheet["E2"].value == "资产总计"
        assert sheet["F2"].value == 12_345
        assert sheet["G2"].value == 12_345
        assert sheet["H2"].value == "EXACT_MATCH"
        assert json.loads(sheet["I2"].value) == {"source": "official", "pages": [1, 2]}

        registry_sheet = workbook["Registry"]
        assert registry_sheet["B2"].value == "RPT_F10_FINANCE_GBALANCE"
        assert registry_sheet["C2"].value == "TOTAL_ASSETS"
        assert registry_sheet["E2"].value == "OFFICIAL_DIRECT"
    finally:
        workbook.close()
