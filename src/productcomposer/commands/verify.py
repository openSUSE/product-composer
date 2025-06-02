from ..parsers.yamlparser import parse_yaml
from . import register
from ..utils.loggerutils import (die, note)

# global db for eulas
eulas = {}
# global db for supportstatus
supportstatus = {}
# per package override via supportstatus.txt file
supportstatus_override = {}

@register("verify")
class VerifyCommand:
    def run(self, args):
        yml = parse_yaml(args.filename, args.flavor)
        if args.flavor == None:
            for flavor in yml['flavors']:
                yml = parse_yaml(args.filename, flavor)
                if not yml['architectures']:
                    die(f'No architecture defined for flavor {flavor}')
                if yml['content']:
                    for pkgsetname in yml['content']:
                        if pkgsetname not in (x['name'] for x in yml['packagesets']):
                            die(f'package set {pkgsetname} not defined for flavor {flavor}')
            return
        if not yml['architectures']:
            die('No architecture defined and no flavor.')
