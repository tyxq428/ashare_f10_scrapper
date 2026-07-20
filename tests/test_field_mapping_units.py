from ashare_f10.fetch.manifest import load_field_mapping


def test_core_amount_and_ratio_units_are_not_confused_by_operate_substring():
    mapping = load_field_mapping()["global"]
    expected = {
        "TOTAL_OPERATE_INCOME": "元",
        "TOTAL_OPERATEINCOME": "元",
        "OPERATE_PROFIT": "元",
        "OPERATE_CYCLE": "天",
        "OPERATEDEPT_NAME": "文本",
        "NEWCAPITALADER": "%",
        "NONPERLOAN": "%",
        "NET_CAPITAL_LIABILITIES": "%",
        "NET_ASSETS_LIABILITIES": "%",
        "PB_MRQ_REALTIME": "倍",
        "CURRENT_ASSET_TR": "次",
        "FIXED_ASSET_TR": "次",
        "ACCOUNTS_PAYABLE_TR": "次",
    }
    assert {key: mapping[key]["unit"] for key in expected} == expected


def test_yoy_share_fields_are_percentages():
    mapping = load_field_mapping()["global"]
    for key in (
        "PREFERRED_SHARES_PAYBALE_YOY",
        "PREFERRED_SHARES_YOY",
        "TREASURY_SHARES_YOY",
    ):
        assert mapping[key]["unit"] == "%"
