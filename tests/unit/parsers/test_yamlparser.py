import pytest
from schema import Schema, And, Or, Optional, SchemaError, SchemaMissingKeyError
from productcomposer.parsers.yamlparser import parse_yaml


def test_yamlparser_ok():
    yml = parse_yaml(
        './tests/assets/tomls/Backports.productcompose', 'backports_x86_64'
    )
    assert len(yml['flavors']) == 4


def test_yamlparser_wrong_schema(capsys):
    with pytest.raises(SystemExit) as excinfo:
        yml = parse_yaml(
            './tests/assets/tomls/UnsupportedSchemaVer.productcompose',
            'backports_x86_64',
        )

    assert excinfo.type == SystemExit
    assert excinfo.value.code == 1

    captured = capsys.readouterr()
    assert 'ERROR: Unsupported product composer schema: 0.3' in captured.out


def test_yamlparser_missing_schema(capsys):
    with pytest.raises(SystemExit) as excinfo:
        yml = parse_yaml(
            './tests/assets/tomls/MissingSchemaVer.productcompose', 'backports_x86_64'
        )

    assert excinfo.type == SystemExit
    assert excinfo.value.code == 1

    captured = capsys.readouterr()
    assert 'ERROR: missing product composer schema' in captured.out


def test_yamlparser_invalid_schema():
    with pytest.raises(SchemaMissingKeyError, match="Missing key: 'product-type'"):
        yml = parse_yaml(
            './tests/assets/tomls/InvalidSchema.productcompose', 'backports_x86_64'
        )


def test_yamlparser_flavor_notfound(capsys):
    with pytest.raises(SystemExit) as excinfo:
        yml = parse_yaml(
            './tests/assets/tomls/Backports.productcompose', 'ports_x86_64'
        )

    assert excinfo.type == SystemExit
    assert excinfo.value.code == 1

    captured = capsys.readouterr()
    assert 'ERROR: Flavor not found' in captured.out


def test_yamlparser_invalid_buildoption(capsys):
    with pytest.raises(SchemaError, match="Key 'build_options' error"):
        yml = parse_yaml(
            './tests/assets/tomls/InvalidBuildOption.productcompose', 'backports_x86_64'
        )
