import yaml
import pydantic

from ..utils.loggerutils import (die, warn, note)
from ..validators.composeschema import ComposeSchema



def parse_yaml(filename, flavor):
    with open(filename, 'r') as file:
        yml = yaml.safe_load(file)

    # we may not allow this in future anymore, but for now convert these from float to str
    if 'product_compose_schema' in yml:
        yml['product_compose_schema'] = str(yml['product_compose_schema'])
    if 'version' in yml:
        yml['version'] = str(yml['version'])

    if 'product_compose_schema' not in yml:
        die('missing product composer schema')
    if yml['product_compose_schema'] not in ('0.1', '0.2'):
        die(f'Unsupported product composer schema: {yml["product_compose_schema"]}')

    try:
        ComposeSchema(**yml)
        note(f"Configuration is valid for flavor: {flavor}")
    except pydantic.ValidationError as se:
        import pdb; pdb.set_trace()
        warn(f"YAML syntax is invalid for flavor: {flavor}")
        raise se

    if 'flavors' not in yml:
        yml['flavors'] = []

    if 'build_options' not in yml or yml['build_options'] is None:
        yml['build_options'] = []

    if flavor:
        if flavor not in yml['flavors']:
            die('Flavor not found: ' + flavor)
        f = yml['flavors'][flavor]
        # overwrite global values from flavor overwrites
        for tag in (
            'architectures',
            'name',
            'summary',
            'version',
            'update',
            'edition',
            'product-type',
            'product_directory_name',
            'source',
            'debug',
            'repodata',
        ):
            if tag in f:
                yml[tag] = f[tag]

        # Add additional build_options instead of replacing global defined set.
        if 'build_options' in f:
            for option in f['build_options']:
                yml['build_options'].append(option)

        if 'iso' in f:
            if 'iso' not in yml:
                yml['iso'] = {}
            for tag in ('volume_id', 'publisher', 'tree', 'base'):
                if tag in f['iso']:
                    yml['iso'][tag] = f['iso'][tag]

    if 'installcheck' in yml and yml['installcheck'] is None:
        yml['installcheck'] = []

    # FIXME: validate strings, eg. right set of chars

    return yml