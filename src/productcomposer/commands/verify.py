from ..parsers.yamlparser import parse_yaml
from . import register
from ..utils.loggerutils import die
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
        self.verify(args)

    def verify_flavor(self, filename, flavor):
        yml = parse_yaml(filename, flavor)
        if not flavor and not yml['architectures']:
            # no default build defined, skipping
            return yml.get('flavors')
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
        if args.flavor is None:
            for flavor in flavors:
                self.verify_flavor(args.filename, flavor)
