from productcomposer.parsers.eulasparser import parse_eulas


def test_eulasparser_ok():
    eulas = {}
    parse_eulas('tests/assets/eulas', eulas)
    assert len(eulas) == 3


def test_eulasparser_wrong_path():
    eulas = {}
    parse_eulas('tests/assets/xulas', eulas)
    assert len(eulas) == 0
