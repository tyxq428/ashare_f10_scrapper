from ashare_f10.normalize.facts import iter_facts


def test_normalize_financial_record():
    combined = {
        "metadata": {"security": {"code": "688521"}},
        "groups": [
            {
                "theme": "财务报表与指标",
                "family": "RPT_F10_FINANCE_GBALANCE",
                "records": [{"REPORT_DATE": "2026-03-31 00:00:00", "TOTAL_ASSETS": 100, "CIP": 5}],
                "requests": [],
            }
        ],
    }
    rows = list(iter_facts(combined))
    assets = next(row for row in rows if row["field_key"] == "TOTAL_ASSETS")
    assert assets["field_name_cn"] == "资产总计"
    assert assets["value_num"] == 100
    assert assets["data_semantics"] == "point_in_time"
