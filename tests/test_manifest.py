from ashare_f10.fetch.manifest import load_field_mapping, load_manifest


def test_fixed_manifest_is_complete():
    manifest = load_manifest()
    assert manifest["schema_version"] == "1.0.0"
    assert len(manifest["groups"]) == 113
    families = {group["family"] for group in manifest["groups"]}
    assert "PageAjax" in families
    assert "RPT_F10_FINANCE_GBALANCE" in families
    assert "RPT_F10_FINANCE_GINCOMEQC" in families
    assert "/api/security/ann" in families


def test_chinese_mapping_contains_core_fields():
    mapping = load_field_mapping()["global"]
    assert mapping["TOTAL_ASSETS"]["label"] == "资产总计"
    assert mapping["CIP"]["label"] == "在建工程"
    assert mapping["TOTAL_OPERATE_INCOME"]["label"] == "营业总收入"
