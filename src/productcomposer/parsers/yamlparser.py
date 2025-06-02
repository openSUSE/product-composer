from typing import Dict
import yaml
import pydantic

from ..utils.loggerutils import (die, warn, note)
from ..validators.composeschema import ComposeSchema



def parse_yaml(filename: str, flavor: str | None) -> Dict[str, any]:
    with open(filename, 'r') as file:
        _yml = yaml.safe_load(file)

    # we may not allow this in future anymore, but for now convert these from float to str
    for a in ('product_compose_schema', 'version'):
        if a in _yml:
            _yml[a] = str(_yml[a])

    try:
        model = ComposeSchema(**_yml)
        note(f"Configuration is valid for flavor: {flavor}")
    except pydantic.ValidationError as se:
        warn(f"Configuration is invalid for flavor: {flavor}")
        raise se

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
            'update',
            'edition',
            'product_type',
            'product_directory_name',
            'source',
            'debug',
            'repodata',
            'content',
            'unpack',
        ):
            if f.get(tag, None):
                yml[tag] = f[tag]

        # Merge build_options instead of replacing global defined set
        if 'build_options' in f:
            for option in f['build_options']:
                yml['build_options'].append(option)

        if f['iso']:
            for tag in ('volume_id', 'publisher', 'tree', 'base'):
                if f['iso'].get(tag, None):
                    yml['iso'][tag] = f['iso'][tag]

    for tag in (
            'installcheck',
            'unpack',
            'content'
    ):
        if tag in yml and yml[tag] is None:
            yml[tag] = []

    return yml
