from __future__ import annotations

import pandas as pd

from ashare_f10.cross_validation.registry import FieldValidationRegistry


def test_registry_classifies_every_context() -> None:
    frame = pd.DataFrame(
        [
            {
                "theme": "财务",
                "family": "RPT_F10_FINANCE_GBALANCE",
                "dataset": "资产负债表",
                "field_key": "TOTAL_ASSETS",
                "field_name_cn": "资产总计",
                "unit": "元",
                "data_semantics": "point_in_time",
                "field_category": "PAGE_DISPLAY_FIELD",
            },
            {
                "theme": "行情",
                "family": "/api/qt/stock/get",
                "dataset": "最新行情",
                "field_key": "f43",
                "field_name_cn": "最新价",
                "unit": "元",
                "data_semantics": "event",
                "field_category": "PAGE_DISPLAY_FIELD",
            },
            {
                "theme": "未知",
                "family": "RPT_NEW_FREE_SOURCE_LATER",
                "dataset": "未知",
                "field_key": "X_TEST",
                "field_name_cn": "待验证字段",
                "unit": "",
                "data_semantics": "event",
                "field_category": "PAGE_DISPLAY_FIELD",
            },
        ]
    )
    registry = FieldValidationRegistry.load()
    output = registry.build_frame(frame)
    assert len(output) == 3
    assert output["validation_mode"].notna().all()
    assert registry.coverage(output)["classification_coverage"] == 1.0
    assert output.loc[output.field_key == "TOTAL_ASSETS", "validation_mode"].item() == "OFFICIAL_DIRECT"
    assert output.loc[output.field_key == "f43", "validation_mode"].item() == "NOT_IN_PERIODIC_REPORT_SCOPE"
    assert output.loc[output.field_key == "X_TEST", "validation_mode"].item() == "FUTURE_FREE_SOURCE_REQUIRED"
