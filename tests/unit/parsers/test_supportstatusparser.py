from productcomposer.parsers.supportstatusparser import parse_supportstatus


def test_supportstatusparser_ok():
    supportstatus_override = {}
    parse_supportstatus('tests/assets/supportstatus.txt', supportstatus_override)
    #print(supportstatus_override)
    assert len(supportstatus_override) == 73


def test_supportstatusparser_ko():
    supportstatus_override = {}
    parse_supportstatus(
        'tests/assets/supportstatus-wrong.txt', supportstatus_override
    )
    assert len(supportstatus_override) == 0
