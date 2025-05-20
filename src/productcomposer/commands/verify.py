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
        result = self.verify(args)

    def verify(self, args):
        yml = parse_yaml(args.filename, args.flavor)
        if args.flavor == None and 'flavors' in yml:
            for flavor in yml['flavors']:
                yml = parse_yaml(args.filename, flavor)
                if 'architectures' not in yml or not yml['architectures']:
                    die(f'No architecture defined for flavor {flavor}')
        elif 'architectures' not in yml or not yml['architectures']:
            die('No architecture defined and no flavor.')