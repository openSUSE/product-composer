import pydantic
import pytest

from productcomposer.parsers.yamlparser import parse_yaml


def test_yamlparser_ok():
    yml = parse_yaml('tests/assets/yamls/Backports.productcompose', 'backports_x86_64')
    assert len(yml['flavors']) == 4


def test_yamlparser_wrong_schema(capsys):
    with pytest.raises(SystemExit) as exc:
        yml = parse_yaml(
            'tests/assets/yamls/UnsupportedSchemaVer.productcompose', 'backports_x86_64'
        )

    assert '0.3' in capsys.readouterr().out


def test_yamlparser_missing_schema(capsys):
    with pytest.raises(SystemExit) as exc:
        yml = parse_yaml(
            'tests/assets/yamls/MissingSchemaVer.productcompose', 'backports_x86_64'
        )
    assert 'field required' in capsys.readouterr().out.lower()


def test_yamlparser_invalid_schema(capsys):
    with pytest.raises(SystemExit) as exc:
        yml = parse_yaml('tests/assets/yamls/InvalidSchema.productcompose', 'backports')
    assert 'Flavor not found' in capsys.readouterr().out


def test_yamlparser_flavor_notfound(capsys):
    with pytest.raises(SystemExit) as excinfo:
        yml = parse_yaml('tests/assets/yamls/Backports.productcompose', 'ports_x86_64')

    assert excinfo.type == SystemExit
    assert excinfo.value.code == 1

    assert 'ERROR: Flavor not found' in capsys.readouterr().out


def test_yamlparser_invalid_buildoption(capsys):
    with pytest.raises(SystemExit) as exc:
        yml = parse_yaml(
            'tests/assets/yamls/InvalidBuildOption.productcompose', 'backports_x86_64'
        )

    assert 'invalid_build_option' in capsys.readouterr().out
