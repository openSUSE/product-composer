from ..parsers.yamlparser import parse_yaml
from . import register
from ..utils.loggerutils import die, note
from ..utils.rpmutils import create_package_set
from ..core.Pool import Pool

# global db for eulas
eulas = {}
# global db for supportstatus
supportstatus = {}
# per package override via supportstatus.txt file
supportstatus_override = {}


@register('verify')
class VerifyCommand:
    def run(self, args):
        result = self.verify(args)

    def verify_flavor(self, filename, flavor):
        yml = parse_yaml(filename, flavor)
        if not flavor and not yml['architectures']:
            die('No architecture defined and no flavor.')
        if not yml['architectures']:
            die(f'No architecture defined for flavor {flavor}')

        # check package sets
        for arch in yml['architectures']:
            pool = Pool()
            for pkgset_name in yml['content']:
                create_package_set(yml, arch, flavor, pkgset_name, pool=pool)
            for pkgset_name in yml['unpack']:
                create_package_set(yml, arch, flavor, pkgset_name, pool=pool)
        return yml.get('flavors')

    def verify(self, args):
        flavors = self.verify_flavor(args.filename, args.flavor)
        if args.flavor == None:
            for flavor in flavors:
                self.verify_flavor(args.filename, flavor)
