import os
import shutil
from . import register
from ..parsers.yamlparser import parse_yaml
from ..parsers.supportstatusparser import parse_supportstatus
from ..parsers.eulasparser import parse_eulas
from ..utils.loggerutils import (die, note)
from ..createartifacts.createtree import create_tree
from ..core.Pool import Pool

# hashed via file name
tree_report = {}        
# global db for eulas
eulas = {}
# global db for supportstatus
supportstatus = {}
# per package override via supportstatus.txt file
supportstatus_override = {}

@register("build")
class BuildCommand:
    def run(self, args):
        result = self.build(args)
    
    def get_product_dir(self, yml, flavor, release):
        name = f'{yml["name"]}-{yml["version"]}'
        if 'product_directory_name' in yml:
            # manual override
            name = yml['product_directory_name']
        if flavor and 'hide_flavor_in_product_directory_name' not in yml['build_options']:
            name += f'-{flavor}'
        if yml['architectures']:
            visible_archs = yml['architectures']
            if 'local' in visible_archs:
                visible_archs.remove('local')
            name += "-" + "-".join(visible_archs)
        if release:
            name += f'-Build{release}'
        if '/' in name:
            die("Illegal product name")
        return name

    def build(self, args):
        flavor = None
        global verbose_level

        if args.flavor:
            f = args.flavor.split('.')
            if f[0] != '':
                flavor = f[0]

        if args.verbose:
            verbose_level = 1

        if not args.out:
            die("No output directory given")

        yml = parse_yaml(args.filename, flavor)

        for arg in args.build_option:
            for option in arg:
                yml['build_options'].append(option)

        if 'architectures' not in yml or not yml['architectures']:
            die(f'No architecture defined for flavor {flavor}')

        directory = os.getcwd()
        if args.filename.startswith('/'):
            directory = os.path.dirname(args.filename)
        reposdir = args.reposdir if args.reposdir else directory + "/repos"

        supportstatus_fn = os.path.join(directory, 'supportstatus.txt')
        if os.path.isfile(supportstatus_fn):
            parse_supportstatus(supportstatus_fn)

        if args.euladir and os.path.isdir(args.euladir):
            parse_eulas(args.euladir)

        pool = Pool()
        note(f"Scanning: {reposdir}")
        pool.scan(reposdir)

        # clean up blacklisted packages
        for u in sorted(pool.lookup_all_updateinfos()):
            for update in u.root.findall('update'):
                if not update.find('blocked_in_product'):
                    continue

                parent = update.findall('pkglist')[0].findall('collection')[0]
                for pkgentry in parent.findall('package'):
                    name = pkgentry.get('name')
                    epoch = pkgentry.get('epoch')
                    version = pkgentry.get('version')
                    pool.remove_rpms(None, name, '=', epoch, version, None)

        if args.clean and os.path.exists(args.out):
            shutil.rmtree(args.out)

        product_base_dir = self.get_product_dir(yml, flavor, args.release)

        create_tree(args.out, product_base_dir, yml, pool, flavor, tree_report, supportstatus, supportstatus_override, eulas, args.vcs, args.disturl)