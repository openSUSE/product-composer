from typing import Any
from typing import Dict
import yaml
import pydantic

from ..utils.loggerutils import die
from ..verifiers.composeschema import ComposeSchema, compose_schema_iso



def parse_yaml(filename: str, flavor: str | None) -> Dict[str, Any]:
    with open(filename, 'r') as file:
        _yml = yaml.safe_load(file)

    # we may not allow this in future anymore, but for now convert these from float to str
    for a in ('product_compose_schema', 'version'):
        if a in _yml:
            _yml[a] = str(_yml[a])

    try:
        model = ComposeSchema(**_yml)
    except pydantic.ValidationError as se:
        if flavor:
            die(f"Failed to verify configuration for flavor {flavor}\n{se}")
        else:
            die(f"Failed to verify configuration\n{se}")

    # Use the pydantic validated/converted representation
    yml: Dict[str, Any] = model.dict()

    if flavor:
        if flavor not in yml['flavors']:
            die(f'Flavor not found: {flavor}')
        f = yml['flavors'][flavor]
        # overwrite global values from flavor overwrites
        for tag in (
            'architectures',
            'name',
            'summary',
            'version',
            'version_from_package',
            'update',
            'edition',
            'product_type',
            'product_directory_name',
            'source',
            'debug',
            'repodata',
            'content',
            'unpack',
            'set_updateinfo_from',
            'set_updateinfo_id_prefix',
        ):
            if f.get(tag, None):
                yml[tag] = f[tag]

        # Merge build_options instead of replacing global defined set
        if 'build_options' in f:
            for option in f['build_options']:
                yml['build_options'].append(option)

        if f['iso']:
            if not yml['iso']:
                yml['iso'] = compose_schema_iso().dict()
            for tag in ('volume_id', 'publisher', 'tree', 'base', 'joliet'):
                if f['iso'].get(tag):
                    yml['iso'][tag] = f['iso'][tag]

    for tag in (
            'installcheck',
            'unpack',
            'content'
    ):
        if tag in yml and yml[tag] is None:
            yml[tag] = []

    return yml
