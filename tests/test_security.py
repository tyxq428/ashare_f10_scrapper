from ashare_f10.fetch.security import parse_security, replace_security_tokens


def test_parse_shanghai():
    identity = parse_security("688521")
    assert identity.secucode == "688521.SH"
    assert identity.page_code == "SH688521"
    assert identity.market_id_code == "1.688521"


def test_parse_shenzhen():
    identity = parse_security("300308")
    assert identity.secucode == "300308.SZ"
    assert identity.page_code == "SZ300308"
    assert identity.market_id_code == "0.300308"


def test_replace_nested_tokens():
    identity = parse_security("300308")
    value = {
        "filter": '(SECUCODE="688521.SH")',
        "secid": "1.688521",
        "url": "SH688521/688521",
    }
    replaced = replace_security_tokens(value, identity)
    assert replaced["filter"] == '(SECUCODE="300308.SZ")'
    assert replaced["secid"] == "0.300308"
    assert replaced["url"] == "SZ300308/300308"
