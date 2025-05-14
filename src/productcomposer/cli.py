""" Implementation of the command line interface.

"""

import os
import re
import shutil
import subprocess
import gettext
import glob
from datetime import datetime
from argparse import ArgumentParser
from xml.etree import ElementTree as ET

import yaml

from .core.logger import logger
from .core.PkgSet import PkgSet
from .core.Package import Package
from .core.Pool import Pool
from .wrappers import CreaterepoWrapper
from .wrappers import ModifyrepoWrapper


__all__ = "main",


ET_ENCODING = "unicode"
ISO_PREPARER = "Product Composer - http://www.github.com/openSUSE/product-composer"
DEFAULT_EULADIR = "/usr/share/doc/packages/eulas"


tree_report = {}        # hashed via file name

# hardcoded defaults for now
chksums_tool = 'sha512sum'

# global db for supportstatus
supportstatus = {}
# global db for eulas
eulas = {}
# per package override via supportstatus.txt file
supportstatus_override = {}
# debug aka verbose
verbose_level = 0


def main(argv=None) -> int:
    """ Execute the application CLI.

    :param argv: argument list to parse (sys.argv by default)
    :return: exit status
    """
    #
    # Setup CLI parser
    #
    parser = ArgumentParser('productcomposer')
    subparsers = parser.add_subparsers(required=True, help='sub-command help')

    # One sub parser for each command
    verify_parser = subparsers.add_parser('verify', help='Verify the build recipe')
    build_parser = subparsers.add_parser('build', help='Run a product build')

    verify_parser.set_defaults(func=verify)
    build_parser.set_defaults(func=build)

    # Generic options
    for cmd_parser in [verify_parser, build_parser]:
        cmd_parser.add_argument('-f', '--flavor', help='Build a given flavor')
        cmd_parser.add_argument('-v', '--verbose', action='store_true',  help='Enable verbose output')
        cmd_parser.add_argument('--reposdir', action='store',  help='Take packages from this directory')
        cmd_parser.add_argument('filename', default='default.productcompose',  help='Filename of product YAML spec')

    # build command options
    build_parser.add_argument('-r', '--release', default=None,  help='Define a build release counter')
    build_parser.add_argument('--disturl', default=None,  help='Define a disturl')
    build_parser.add_argument('--build-option', action='append', nargs='+', default=[],  help='Set a build option')
    build_parser.add_argument('--vcs', default=None,  help='Define a source repository identifier')
    build_parser.add_argument('--clean', action='store_true',  help='Remove existing output directory first')
    build_parser.add_argument('--euladir', default=DEFAULT_EULADIR, help='Directory containing EULA data')
    build_parser.add_argument('out',  help='Directory to write the result')

    # parse and check
    args = parser.parse_args(argv)
    filename = args.filename
    if not filename:
        # No subcommand was specified.
        print("No filename")
        parser.print_help()
        die(None)

    #
    # Invoke the function
    #
    args.func(args)
    return 0


def die(msg, details=None):
    if msg:
        print("ERROR: " + msg)
    if details:
        print(details)
    raise SystemExit(1)


def warn(msg, details=None):
    print("WARNING: " + msg)
    if details:
        print(details)


def note(msg):
    print(msg)


def build(args):
    flavor = None
    if args.flavor:
        f = args.flavor.split('.')
        if f[0] != '':
            flavor = f[0]
    if args.verbose:
        verbose_level = 1

    if not args.out:
        # No subcommand was specified.
        print("No output directory given")
        parser.print_help()
        die(None)

    yml = parse_yaml(args.filename, flavor)

    for arg in args.build_option:
        for option in arg:
            yml['build_options'].append(option)

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
    note(f"scanning: {reposdir}")
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
                pool.remove_rpms(None, name, '=', epoch, version)

    if args.clean and os.path.exists(args.out):
        shutil.rmtree(args.out)

    product_base_dir = get_product_dir(yml, flavor, args.release)

    create_tree(args.out, product_base_dir, yml, pool, flavor, args.vcs, args.disturl)


def verify(args):
    parse_yaml(args.filename, args.flavor)


def parse_yaml(filename, flavor):

    with open(filename, 'r') as file:
        yml = yaml.safe_load(file)

    if 'product_compose_schema' not in yml:
        die('missing product composer schema')
    if yml['product_compose_schema'] != 0 and yml['product_compose_schema'] != 0.1 and yml['product_compose_schema'] != 0.2:
        die(f"Unsupported product composer schema: {yml['product_compose_schema']}")

    if 'flavors' not in yml:
        yml['flavors'] = []

    if 'build_options' not in yml or yml['build_options'] is None:
        yml['build_options'] = []

    if flavor:
        if flavor not in yml['flavors']:
            die("Flavor not found: " + flavor)
        f = yml['flavors'][flavor]
        # overwrite global values from flavor overwrites
        for tag in ['architectures', 'name', 'summary', 'version', 'update', 'edition',
                    'product-type', 'product_directory_name',
                    'source', 'debug', 'repodata']:
            if tag in f:
                yml[tag] = f[tag]

        # Add additional build_options instead of replacing global defined set.
        if 'build_options' in f:
            for option in f['build_options']:
                yml['build_options'].append(option)

        if 'iso' in f:
            if not 'iso' in yml:
                yml['iso'] = {}
            for tag in ['volume_id', 'publisher', 'tree', 'base']:
                if tag in f['iso']:
                    yml['iso'][tag] = f['iso'][tag]

    if 'architectures' not in yml or not yml['architectures']:
        die("No architecture defined. Maybe wrong flavor?")

    if 'installcheck' in yml and yml['installcheck'] is None:
        yml['installcheck'] = []

    # FIXME: validate strings, eg. right set of chars
    
    return yml


def parse_supportstatus(filename):
    with open(filename, 'r') as file:
        for line in file.readlines():
            a = line.strip().split(' ')
            supportstatus_override[a[0]] = a[1]


def parse_eulas(euladir):
    note(f"reading eula data from {euladir}")
    for dirpath, dirs, files in os.walk(euladir):
        for filename in files:
            if filename.startswith('.'):
                continue
            pkgname = filename.removesuffix('.en')
            with open(os.path.join(dirpath, filename), encoding="utf-8") as f:
                eulas[pkgname] = f.read()


def get_product_dir(yml, flavor, release):
    name = yml['name'] + "-" + str(yml['version'])
    if 'product_directory_name' in yml:
        # manual override
        name = yml['product_directory_name']
    if flavor and not 'hide_flavor_in_product_directory_name' in yml['build_options']:
        name += "-" + flavor
    if yml['architectures']:
        visible_archs = yml['architectures']
        if 'local' in visible_archs:
            visible_archs.remove('local')
        name += "-" + "-".join(visible_archs)
    if release:
        name += "-Build" + str(release)
    if '/' in name:
        die("Illegal product name")
    return name


def run_helper(args, cwd=None, fatal=True, stdout=None, stdin=None, failmsg=None, verbose=False):
    if verbose:
        note("Calling {args}")
    if stdout is None:
        stdout = subprocess.PIPE
    if stdin is None:
        stdin = subprocess.PIPE
    popen = subprocess.Popen(args, stdout=stdout, stdin=stdin, cwd=cwd)

    output = popen.communicate()[0]
    if isinstance(output, bytes):
        output = output.decode(errors='backslashreplace')

    if popen.returncode:
        if failmsg:
            msg="Failed to " + failmsg
        else:
            msg="Failed to run " + args[0]
        if fatal:
            die(msg, details=output)
        else:
            warn(msg, details=output)
    return output if stdout == subprocess.PIPE else ''

def create_sha256_for(filename):
    with open(filename + '.sha256', 'w') as sha_file:
        # argument must not have the path
        args = [ 'sha256sum', filename.split('/')[-1] ]
        run_helper(args, cwd=("/"+os.path.join(*filename.split('/')[:-1])), stdout=sha_file, failmsg="create .sha256 file")

def create_iso(outdir, yml, pool, flavor, workdir, application_id):
    verbose = True if verbose_level > 0 else False
    args = ['/usr/bin/mkisofs', '-quiet', '-p', ISO_PREPARER]
    args += ['-r', '-pad', '-f', '-J', '-joliet-long']
    if 'publisher' in yml['iso'] and yml['iso']['publisher'] is not None:
        args += ['-publisher', yml['iso']['publisher']]
    if 'volume_id' in yml['iso'] and yml['iso']['volume_id'] is not None:
        args += ['-V', yml['iso']['volume_id']]
    args += ['-A', application_id]
    args += ['-o', workdir + '.iso', workdir]
    run_helper(args, cwd=outdir, failmsg="create iso file", verbose=verbose)
    # simple tag media call ... we may add options for pading or triggering media check later
    args = [ 'tagmedia' , '--digest' , 'sha256', workdir + '.iso' ]
    run_helper(args, cwd=outdir, failmsg="tagmedia iso file", verbose=verbose)
    # creating .sha256 for iso file
    create_sha256_for(workdir + ".iso")

def create_agama_iso(outdir, yml, pool, flavor, workdir, application_id, arch):
    verbose = True if verbose_level > 0 else False
    base = yml['iso']['base']
    if verbose:
        note(f"Looking for baseiso-{base} rpm on {arch}")
    agama = pool.lookup_rpm(arch, f"baseiso-{base}")
    if not agama:
        die(f"Base iso in baseiso-{base} rpm was not found")
    baseisodir = f"{outdir}/baseiso"
    os.mkdir(baseisodir)
    args = ['unrpm', '-q', agama.location]
    run_helper(args, cwd=baseisodir, failmsg=f"extract {agama.location}", verbose=verbose)
    files = glob.glob(f"usr/libexec/base-isos/{base}*.iso", root_dir=baseisodir)
    if not files:
        die(f"Base iso {base} not found in {agama}")
    if len(files) > 1:
        die(f"Multiple base isos for {base} found in {agama}")
    agamaiso = f"{baseisodir}/{files[0]}"
    if verbose:
        note(f"Found base iso image {agamaiso}")

    # create new iso
    tempdir = f"{outdir}/mksusecd"
    os.mkdir(tempdir)
    if not 'base_skip_packages' in yml['build_options']:
        args = ['cp', '-al', workdir, f"{tempdir}/install"]
        run_helper(args, failmsg="Adding tree to agama image")
    args = ['mksusecd', agamaiso, tempdir, '--create', workdir + '.install.iso']
    # mksusecd would take the volume_id, publisher, application_id, preparer from the agama iso
    args += ['--preparer', ISO_PREPARER]
    if 'publisher' in yml['iso'] and yml['iso']['publisher'] is not None:
        args += ['--vendor', yml['iso']['publisher']]
    if 'volume_id' in yml['iso'] and yml['iso']['volume_id'] is not None:
        args += ['--volume', yml['iso']['volume_id']]
    args += ['--application', application_id]
    run_helper(args, failmsg="Adding tree to agama image", verbose=verbose)
    # mksusecd already did a tagmedia call with a sha256 digest
    # cleanup directories
    shutil.rmtree(tempdir)
    shutil.rmtree(baseisodir)
    # just for the bootable image, signature is not yet applied, so ignore that error
    run_helper(['verifymedia', workdir + '.install.iso', '--ignore', 'ISO is signed'], fatal=False, failmsg="Verification of install.iso")
    # creating .sha256 for iso file
    create_sha256_for(workdir + '.install.iso')

def create_tree(outdir, product_base_dir, yml, pool, flavor, vcs=None, disturl=None):
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    maindir = outdir + '/' + product_base_dir
    if not os.path.exists(maindir):
        os.mkdir(maindir)

    workdirectories = [ maindir ]
    debugdir = sourcedir = None
    if "source" in yml:
        if yml['source'] == 'split':
            sourcedir = outdir + '/' + product_base_dir + '-Source'
            os.mkdir(sourcedir)
            workdirectories.append(sourcedir)
        elif yml['source'] == 'include':
            sourcedir = maindir
        elif yml['source'] != 'drop':
            die("Bad source option, must be either 'include', 'split' or 'drop'")
    if "debug" in yml:
        if yml['debug'] == 'split':
            debugdir = outdir + '/' + product_base_dir + '-Debug'
            os.mkdir(debugdir)
            workdirectories.append(debugdir)
        elif yml['debug'] == 'include':
            debugdir = maindir
        elif yml['debug'] != 'drop':
            die("Bad debug option, must be either 'include', 'split' or 'drop'")

    for arch in yml['architectures']:
        note(f"Linking rpms for {arch}")
        link_rpms_to_tree(maindir, yml, pool, arch, flavor, debugdir, sourcedir)

    for arch in yml['architectures']:
        note(f"Unpack rpms for {arch}")
        unpack_meta_rpms(maindir, yml, pool, arch, flavor, medium=1)  # only for first medium am

    repos = []
    if disturl:
        match = re.match("^obs://([^/]*)/([^/]*)/.*", disturl)
        if match:
            obsname = match.group(1)
            project = match.group(2)
            repo = f"obsproduct://{obsname}/{project}/{yml['name']}/{yml['version']}"
            repos = [repo]
    if vcs:
        repos.append(vcs)

    default_content = ["pool"]
    for file in os.listdir(maindir):
        if not file.startswith('gpg-pubkey-'):
            continue

        args = ['gpg', '--no-keyring', '--no-default-keyring', '--with-colons',
              '--import-options', 'show-only', '--import', '--fingerprint']
        out = run_helper(args, stdin=open(f'{maindir}/{file}', 'rb'),
                         failmsg="Finger printing of gpg file")
        for line in out.splitlines():
            if line.startswith("fpr:"):
                content = f"{file}?fpr={line.split(':')[9]}"
                default_content.append(content)

    note("Create rpm-md data")
    run_createrepo(maindir, yml, content=default_content, repos=repos)
    if debugdir:
        note("Create rpm-md data for debug directory")
        run_createrepo(debugdir, yml, content=["debug"], repos=repos)
    if sourcedir:
        note("Create rpm-md data for source directory")
        run_createrepo(sourcedir, yml, content=["source"], repos=repos)

    repodatadirectories = workdirectories.copy()
    if 'repodata' in yml:
        if yml['repodata'] != 'all':
            repodatadirectories = []
        for workdir in workdirectories:
            if sourcedir and sourcedir == workdir:
                continue
            for arch in yml['architectures']:
                if os.path.exists(workdir + f"/{arch}"):
                    repodatadirectories.append(workdir + f"/{arch}")

    note("Write report file")
    write_report_file(maindir, maindir + '.report')
    if sourcedir and maindir != sourcedir:
        note("Write report file for source directory")
        write_report_file(sourcedir, sourcedir + '.report')
    if debugdir and maindir != debugdir:
        note("Write report file for debug directory")
        write_report_file(debugdir, debugdir + '.report')

    # CHANGELOG file
    # the tools read the subdirectory of the maindir from environment variable
    os.environ['ROOT_ON_CD'] = '.'
    if os.path.exists("/usr/bin/mk_changelog"):
        args = ["/usr/bin/mk_changelog", maindir]
        run_helper(args)

    # ARCHIVES.gz
    if os.path.exists("/usr/bin/mk_listings"):
        args = ["/usr/bin/mk_listings", maindir]
        run_helper(args)

    # media.X structures FIXME
    mediavendor = yml['vendor'] + ' - ' + product_base_dir
    mediaident = product_base_dir
    # FIXME: calculate from product provides
    mediaproducts = [yml['vendor'] + '-' + yml['name'] + ' ' + str(yml['version']) + '-1']
    create_media_dir(maindir, mediavendor, mediaident, mediaproducts)

    create_checksums_file(maindir)

    for repodatadir in repodatadirectories:
        if os.path.exists(f"{repodatadir}/repodata"):
            create_susedata_xml(repodatadir, yml)

    if 'installcheck' in yml:
       for arch in yml['architectures']:
           note(f"Run installcheck for {arch}")
           args = ['installcheck', arch, '--withsrc']
           subdir = ""
           if 'repodata' in yml:
               subdir = f"/{arch}"
           if not os.path.exists(maindir + subdir):
               warn(f"expected path is missing, no rpm files matched? ({maindir}{subdir})")
               continue
           args.append(find_primary(maindir + subdir))
           if debugdir:
               args.append(find_primary(debugdir + subdir))
           run_helper(args, fatal=(not 'ignore_errors' in yml['installcheck']), failmsg="run installcheck validation")

    if 'skip_updateinfos' not in yml['build_options']:
        create_updateinfo_xml(maindir, yml, pool, flavor, debugdir, sourcedir)

    # Add License File and create extra .license directory
    licensefilename = '/license.tar'
    if os.path.exists(maindir + '/license-' + yml['name'] + '.tar') or os.path.exists(maindir + '/license-' + yml['name'] + '.tar.gz'):
        licensefilename = '/license-' + yml['name'] + '.tar'
    if os.path.exists(maindir + licensefilename + '.gz'):
        run_helper(['gzip', '-d', maindir + licensefilename + '.gz'],
                   failmsg="Uncompress of license.tar.gz failed")
    if os.path.exists(maindir + licensefilename):
        note("Setup .license directory")
        licensedir = maindir + ".license"
        if not os.path.exists(licensedir):
            os.mkdir(licensedir)
        args = ['tar', 'xf', maindir + licensefilename, '-C', licensedir]
        output = run_helper(args, failmsg="extract license tar ball")
        if not os.path.exists(licensedir + "/license.txt"):
            die("No license.txt extracted", details=output)

        mr = ModifyrepoWrapper(
            file=maindir + licensefilename,
            directory=os.path.join(maindir, "repodata"),
        )
        mr.run_cmd()
        os.unlink(maindir + licensefilename)
        # meta package may bring a second file or expanded symlink, so we need clean up
        if os.path.exists(maindir + '/license.tar'):
            os.unlink(maindir + '/license.tar')
        if os.path.exists(maindir + '/license.tar.gz'):
            os.unlink(maindir + '/license.tar.gz')

    for repodatadir in repodatadirectories:
        # detached signature
        args = ['/usr/lib/build/signdummy', '-d', repodatadir + "/repodata/repomd.xml"]
        run_helper(args, failmsg="create detached signature")

        # pubkey
        with open(repodatadir + "/repodata/repomd.xml.key", 'w') as pubkey_file:
            args = ['/usr/lib/build/signdummy', '-p']
            run_helper(args, stdout=pubkey_file, failmsg="write signature public key")

    for workdir in workdirectories:
        if os.path.exists(workdir + '/CHECKSUMS'):
            args = ['/usr/lib/build/signdummy', '-d', workdir + '/CHECKSUMS']
            run_helper(args, failmsg="create detached signature for CHECKSUMS")

        application_id = product_base_dir
        # When using the baseiso feature, the primary media should be
        # the base iso, with the packages added.
        # Other medias/workdirs would then be generated as usual, as
        # presumably you wouldn't need a bootable iso for source and
        # debuginfo packages.
        if workdir == maindir and 'base' in yml.get('iso', {}):
            agama_arch = yml['architectures'][0]
            note(f"Export main tree into agama iso file for {agama_arch}")
            create_agama_iso(outdir, yml, pool, flavor, workdir, application_id, agama_arch)
        elif 'iso' in yml:
            create_iso(outdir, yml, pool, flavor, workdir, application_id);

        # cleanup
        if yml.get('iso', {}).get('tree') == 'drop':
            shutil.rmtree(workdir)

    # create SBOM data
    generate_sbom_call = None
    if os.path.exists("/usr/lib/build/generate_sbom"):
        generate_sbom_call = ["/usr/lib/build/generate_sbom"]

    # Take sbom generation from OBS server
    # Con: build results are not reproducible
    # Pro: SBOM formats are constant changing, we don't need to adapt always all distributions for that
    if os.path.exists("/.build/generate_sbom"):
        # unfortunatly, it is not exectuable by default
        generate_sbom_call = ['env', 'BUILD_DIR=/.build', 'perl', '/.build/generate_sbom']

    if generate_sbom_call:
        spdx_distro = f"{yml['name']}-{yml['version']}"
        note(f"Creating sboom data for {spdx_distro}")
        # SPDX
        args = generate_sbom_call + [
                 "--format", 'spdx',
                 "--distro", spdx_distro,
                 "--product", maindir
               ]
        with open(maindir + ".spdx.json", 'w') as sbom_file:
            run_helper(args, stdout=sbom_file, failmsg="run generate_sbom for SPDX")

        # CycloneDX
        args = generate_sbom_call + [
                  "--format", 'cyclonedx',
                  "--distro", spdx_distro,
                  "--product", maindir
               ]
        with open(maindir + ".cdx.json", 'w') as sbom_file:
            run_helper(args, stdout=sbom_file, failmsg="run generate_sbom for CycloneDX")

    # cleanup main repodata if wanted and existing
    if 'repodata' in yml and yml['repodata'] != 'all':
        for workdir in workdirectories:
            repodatadir = workdir + "/repodata"
            if os.path.exists(repodatadir):
                shutil.rmtree(repodatadir)


def create_media_dir(maindir, vendorstr, identstr, products):
    media1dir = maindir + '/' + 'media.1'
    if not os.path.isdir(media1dir):
        os.mkdir(media1dir)  # we do only support seperate media atm
    with open(media1dir + '/media', 'w') as media_file:
        media_file.write(vendorstr + "\n")
        media_file.write(identstr + "\n")
        media_file.write("1\n")
    if products:
        with open(media1dir + '/products', 'w') as products_file:
            for productname in products:
                products_file.write('/ ' + productname + "\n")


def create_checksums_file(maindir):
    with open(maindir + '/CHECKSUMS', 'a') as chksums_file:
        for subdir in ('boot', 'EFI', 'docu', 'media.1'):
            if not os.path.exists(maindir + '/' + subdir):
                continue
            for root, dirnames, filenames in os.walk(maindir + '/' + subdir):
                for name in filenames:
                    relname = os.path.relpath(root + '/' + name, maindir)
                    run_helper([chksums_tool, relname], cwd=maindir, stdout=chksums_file)

# create a fake package entry from an updateinfo package spec


def create_updateinfo_package(pkgentry):
    entry = Package()
    for tag in 'name', 'epoch', 'version', 'release', 'arch':
        setattr(entry, tag, pkgentry.get(tag))
    return entry

def generate_du_data(pkg, maxdepth):
    dirs = pkg.get_directories()
    seen = set()
    dudata_size = {}
    dudata_count = {}
    for dir, filedatas in pkg.get_directories().items():
        size = 0
        count = 0
        for filedata in filedatas:
            (basename, filesize, cookie) = filedata
            if cookie:
                if cookie in seen:
                    next
                seen.add(cookie)
            size += filesize
            count += 1
        if dir == '':
            dir = '/usr/src/packages/'
        dir = '/' + dir.strip('/')
        subdir = ''
        depth = 0
        for comp in dir.split('/'):
            if comp == '' and subdir != '':
                next
            subdir += comp + '/'
            if subdir not in dudata_size:
                dudata_size[subdir] = 0
                dudata_count[subdir] = 0
            dudata_size[subdir] += size
            dudata_count[subdir] += count
            depth += 1
            if depth > maxdepth:
                break
    dudata = []
    for dir, size in sorted(dudata_size.items()):
        dudata.append((dir, size, dudata_count[dir]))
    return dudata

# Get supported translations based on installed packages
def get_package_translation_languages():
    i18ndir = '/usr/share/locale/en_US/LC_MESSAGES'
    p = re.compile('package-translations-(.+).mo')
    languages = set()
    for file in os.listdir(i18ndir):
        m = p.match(file)
        if m:
            languages.add(m.group(1))
    return sorted(list(languages))

# get the file name from repomd.xml
def find_primary(directory):
    ns = '{http://linux.duke.edu/metadata/repo}'
    tree = ET.parse(directory + '/repodata/repomd.xml')
    return directory + '/' + tree.find(f".//{ns}data[@type='primary']/{ns}location").get('href')

# Create the main susedata.xml with translations, support, and disk usage information
def create_susedata_xml(rpmdir, yml):
    susedatas = {}
    susedatas_count = {}

    # find translation languages
    languages = get_package_translation_languages()

    # create gettext translator object
    i18ntrans = {}
    for lang in languages:
        i18ntrans[lang] = gettext.translation(f'package-translations-{lang}',
                                              languages=['en_US'])

    primary_fn = find_primary(rpmdir)

    # read compressed primary.xml
    openfunction = None
    if primary_fn.endswith('.gz'):
        import gzip
        openfunction = gzip.open
    elif primary_fn.endswith('.zst'):
        import zstandard
        openfunction = zstandard.open
    else:
        die(f"unsupported primary compression type ({primary_fn})")
    tree = ET.parse(openfunction(primary_fn, 'rb'))
    ns = '{http://linux.duke.edu/metadata/common}'

    # Create main susedata structure
    susedatas[''] = ET.Element('susedata')
    susedatas_count[''] = 0

    # go for every rpm file of the repo via the primary
    for pkg in tree.findall(f".//{ns}package[@type='rpm']"):
        name = pkg.find(f'{ns}name').text
        arch = pkg.find(f'{ns}arch').text
        pkgid = pkg.find(f'{ns}checksum').text
        version = pkg.find(f'{ns}version').attrib

        susedatas_count[''] += 1
        package = ET.SubElement(susedatas[''], 'package', {'name': name, 'arch': arch, 'pkgid': pkgid})
        ET.SubElement(package, 'version', version)

        # add supportstatus
        if name in supportstatus and supportstatus[name] is not None:
            ET.SubElement(package, 'keyword').text = f'support_{supportstatus[name]}'

        # add disk usage data
        location = pkg.find(f'{ns}location').get('href')
        if os.path.exists(rpmdir + '/' + location):
            p = Package()
            p.location = rpmdir + '/' + location
            dudata = generate_du_data(p, 3)
            if dudata:
                duelement = ET.SubElement(package, 'diskusage')
                dirselement = ET.SubElement(duelement, 'dirs')
                for duitem in dudata:
                    ET.SubElement(dirselement, 'dir', {'name': duitem[0], 'size': str(duitem[1]), 'count': str(duitem[2])})

        # add eula
        eula = eulas.get(name)
        if eula:
            ET.SubElement(package, 'eula').text = eula

        # get summary/description/category of the package
        summary = pkg.find(f'{ns}summary').text
        description = pkg.find(f'{ns}description').text
        category = pkg.find(".//{http://linux.duke.edu/metadata/rpm}entry[@name='pattern-category()']")
        category = Package._cpeid_hexdecode(category.get('ver')) if category else None

        # look for translations
        for lang in languages:
            isummary = i18ntrans[lang].gettext(summary)
            idescription = i18ntrans[lang].gettext(description)
            icategory = i18ntrans[lang].gettext(category) if category is not None else None
            ieula = eulas.get(name + '.' + lang, default=eula) if eula is not None else None
            if isummary == summary and idescription == description and icategory == category and ieula == eula:
                continue
            if lang not in susedatas:
                susedatas[lang] = ET.Element('susedata')
                susedatas_count[lang] = 0
            susedatas_count[lang] += 1
            ipackage = ET.SubElement(susedatas[lang], 'package', {'name': name, 'arch': arch, 'pkgid': pkgid})
            ET.SubElement(ipackage, 'version', version)
            if isummary != summary:
                ET.SubElement(ipackage, 'summary', {'lang': lang}).text = isummary
            if idescription != description:
                ET.SubElement(ipackage, 'description', {'lang': lang}).text = idescription
            if icategory != category:
                ET.SubElement(ipackage, 'category', {'lang': lang}).text = icategory
            if ieula != eula:
                ET.SubElement(ipackage, 'eula', {'lang': lang}).text = ieula

    # write all susedata files
    for lang, susedata in sorted(susedatas.items()):
        susedata.set('xmlns', 'http://linux.duke.edu/metadata/susedata')
        susedata.set('packages', str(susedatas_count[lang]))
        ET.indent(susedata, space="    ", level=0)
        mdtype = (f'susedata.{lang}' if lang else 'susedata')
        susedata_fn = f'{rpmdir}/{mdtype}.xml'
        with open(susedata_fn, 'x') as sd_file:
            sd_file.write(ET.tostring(susedata, encoding=ET_ENCODING))
        mr = ModifyrepoWrapper(
            file=susedata_fn,
            mdtype=mdtype,
            directory=os.path.join(rpmdir, "repodata"),
        )
        mr.run_cmd()
        os.unlink(susedata_fn)


# Add updateinfo.xml to metadata
def create_updateinfo_xml(rpmdir, yml, pool, flavor, debugdir, sourcedir):
    if not pool.updateinfos:
        return

    missing_package = False

    # build the union of the package sets for all requested architectures
    main_pkgset = PkgSet('main')
    for arch in yml['architectures']:
        pkgset = main_pkgset.add(create_package_set(yml, arch, flavor, 'main', pool=pool))
    main_pkgset_names = main_pkgset.names()

    uitemp = None

    for u in sorted(pool.lookup_all_updateinfos()):
        note("Add updateinfo " + u.location)
        for update in u.root.findall('update'):
            needed = False
            parent = update.findall('pkglist')[0].findall('collection')[0]

            # drop OBS internal patchinforef element
            for pr in update.findall('patchinforef'):
                update.remove(pr)

            if 'set_updateinfo_from' in yml:
                update.set('from', yml['set_updateinfo_from'])

            id_node = update.find('id')
            if 'set_updateinfo_id_prefix' in yml:
                # avoid double application of same prefix
                id_text = re.sub(r'^'+yml['set_updateinfo_id_prefix'], '', id_node.text)
                id_node.text = yml['set_updateinfo_id_prefix'] + id_text

            for pkgentry in parent.findall('package'):
                src = pkgentry.get('src')

                # check for embargo date
                embargo = pkgentry.get('embargo_date')
                if embargo is not None:
                    try:
                        embargo_time = datetime.strptime(embargo, '%Y-%m-%d %H:%M')
                    except ValueError:
                        embargo_time = datetime.strptime(embargo, '%Y-%m-%d')

                    if embargo_time > datetime.now():
                        warn(f"Update is still under embargo! {update.find('id').text}")
                        if 'block_updates_under_embargo' in yml['build_options']:
                            die("shutting down due to block_updates_under_embargo flag")

                # clean internal attributes
                for internal_attributes in ['supportstatus', 'superseded_by', 'embargo_date']:
                    pkgentry.attrib.pop(internal_attributes, None)

                # check if we have files for the entry
                if os.path.exists(rpmdir + '/' + src):
                    needed = True
                    continue
                if debugdir and os.path.exists(debugdir + '/' + src):
                    needed = True
                    continue
                if sourcedir and os.path.exists(sourcedir + '/' + src):
                    needed = True
                    continue
                name = pkgentry.get('name')
                pkgarch = pkgentry.get('arch')

                # do not insist on debuginfo or source packages
                if pkgarch == 'src' or pkgarch == 'nosrc':
                    parent.remove(pkgentry)
                    continue
                if name.endswith('-debuginfo') or name.endswith('-debugsource'):
                    parent.remove(pkgentry)
                    continue
                # ignore unwanted architectures
                if pkgarch != 'noarch' and pkgarch not in yml['architectures']:
                    parent.remove(pkgentry)
                    continue

                # check if we should have this package
                if name in main_pkgset_names:
                    updatepkg = create_updateinfo_package(pkgentry)
                    if main_pkgset.matchespkg(None, updatepkg):
                        warn(f"package {updatepkg} not found")
                        missing_package = True

                parent.remove(pkgentry)

            if not needed:
                if 'abort_on_empty_updateinfo' in yml['build_options']:
                    die(f'Stumbled over an updateinfo.xml where no rpm is used: {id_node.text}')
                continue

            if not uitemp:
                uitemp = open(rpmdir + '/updateinfo.xml', 'x')
                uitemp.write("<updates>\n  ")
            uitemp.write(ET.tostring(update, encoding=ET_ENCODING))

    if uitemp:
        uitemp.write("</updates>\n")
        uitemp.close()

        mr = ModifyrepoWrapper(
                file=os.path.join(rpmdir, "updateinfo.xml"),
                directory=os.path.join(rpmdir, "repodata"),
                )
        mr.run_cmd()

        os.unlink(rpmdir + '/updateinfo.xml')

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        die('Abort due to missing packages for updateinfo')


def run_createrepo(rpmdir, yml, content=[], repos=[]):
    product_name = product_summary = yml['name']
    if 'summary' in yml:
        product_summary = yml['summary']
    product_summary += " " + str(yml['version'])

    product_type = '/o'
    if 'product-type' in yml:
        if yml['product-type'] == 'base':
            product_type = '/o'
        elif yml['product-type'] in ['module', 'extension']:
            product_type = '/a'
        else:
            die('Undefined product-type')
    cr = CreaterepoWrapper(directory=".")
    cr.distro = product_summary
    cr.cpeid = f"cpe:{product_type}:{yml['vendor']}:{yml['name']}:{yml['version']}"
    if 'update' in yml:
        cr.cpeid = cr.cpeid + f":{yml['update']}"
        if 'edition' in yml:
            cr.cpeid = cr.cpeid + f":{yml['edition']}"
    elif 'edition' in yml:
        cr.cpeid = cr.cpeid + f"::{yml['edition']}"
    cr.repos = repos
# cr.split = True
    # cr.baseurl = "media://"
    cr.content = content
    cr.excludes = ["boot"]
    # default case including all architectures. Unique URL for all of them.
    # we need it in any case at least temporarly
    cr.run_cmd(cwd=rpmdir, stdout=subprocess.PIPE)
    # multiple arch specific meta data set
    if 'repodata' in yml:
        cr.complete_arch_list = yml['architectures']
        for arch in yml['architectures']:
            if os.path.isdir(f"{rpmdir}/{arch}"):
                cr.arch_specific_repodata = arch
                cr.run_cmd(cwd=rpmdir, stdout=subprocess.PIPE)


def unpack_one_meta_rpm(rpmdir, rpm, medium):
    tempdir = rpmdir + "/temp"
    os.mkdir(tempdir)
    run_helper(['unrpm', '-q', rpm.location], cwd=tempdir, failmsg=f"extract {rpm.location}")

    skel_dir = tempdir + "/usr/lib/skelcd/CD" + str(medium)
    if os.path.exists(skel_dir):
        shutil.copytree(skel_dir, rpmdir, dirs_exist_ok=True)
    shutil.rmtree(tempdir)


def unpack_meta_rpms(rpmdir, yml, pool, arch, flavor, medium):
    missing_package = False
    for unpack_pkgset_name in yml.get('unpack', []):
        unpack_pkgset = create_package_set(yml, arch, flavor, unpack_pkgset_name, pool=pool)
        for sel in unpack_pkgset:
            rpm = pool.lookup_rpm(arch, sel.name, sel.op, sel.epoch, sel.version, sel.release)
            if not rpm:
                warn(f"package {sel} not found")
                missing_package = True
                continue
            unpack_one_meta_rpm(rpmdir, rpm, medium)

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        die('Abort due to missing meta packages')


def create_package_set_compat(yml, arch, flavor, setname):
    if setname == 'main':
        oldname = 'packages'
    elif setname == 'unpack':
        oldname = 'unpack_packages'
    else:
        return None
    if oldname not in yml:
        return PkgSet(setname) if setname == 'unpack' else None
    pkgset = PkgSet(setname)
    for entry in list(yml[oldname]):
        if type(entry) == dict:
            if 'flavors' in entry:
                if flavor is None or flavor not in entry['flavors']:
                    continue
            if 'architectures' in entry:
                if arch not in entry['architectures']:
                    continue
            pkgset.add_specs(entry['packages'])
        else:
            pkgset.add_specs([str(entry)])
    return pkgset


def create_package_set_all(setname, pool, arch):
    if pool is None:
        die('need a package pool to create the __all__ package set')
    pkgset = PkgSet(setname)
    pkgset.add_specs([n for n in pool.names(arch) if not (n.endswith('-debuginfo') or n.endswith('-debugsource'))])

    return pkgset

def create_package_set(yml, arch, flavor, setname, pool=None):
    if 'packagesets' not in yml:
        pkgset = create_package_set_compat(yml, arch, flavor, setname)
        if pkgset is None:
            die(f'package set {setname} is not defined')
        return pkgset

    pkgsets = {}
    for entry in list(yml['packagesets']):
        name = entry['name'] if 'name' in entry else 'main'
        if name in pkgsets and pkgsets[name] is not None:
            die(f'package set {name} is already defined')
        pkgsets[name] = None
        if 'flavors' in entry:
            if flavor is None or entry['flavors'] is None:
                continue
            if flavor not in entry['flavors']:
                continue
        if 'architectures' in entry:
            if arch not in entry['architectures']:
                continue
        pkgset = PkgSet(name)
        pkgsets[name] = pkgset
        if 'supportstatus' in entry:
            pkgset.supportstatus = entry['supportstatus']
        if 'packages' in entry and entry['packages']:
            pkgset.add_specs(entry['packages'])
        for setop in 'add', 'sub', 'intersect':
            if setop not in entry:
                continue
            for oname in entry[setop]:
                if oname == '__all__' and oname not in pkgsets:
                    pkgsets[oname] = create_package_set_all(oname, pool, arch)
                if oname == name or oname not in pkgsets:
                    die(f'package set {oname} does not exist')
                if pkgsets[oname] is None:
                    pkgsets[oname] = PkgSet(oname)      # instantiate
                if setop == 'add':
                    pkgset.add(pkgsets[oname])
                elif setop == 'sub':
                    pkgset.sub(pkgsets[oname])
                elif setop == 'intersect':
                    pkgset.intersect(pkgsets[oname])
                else:
                    die(f"unsupported package set operation '{setop}'")

    if setname not in pkgsets:
        die(f'package set {setname} is not defined')
    if pkgsets[setname] is None:
        pkgsets[setname] = PkgSet(setname)      # instantiate
    return pkgsets[setname]


def link_rpms_to_tree(rpmdir, yml, pool, arch, flavor, debugdir=None, sourcedir=None):
    singlemode = True
    if 'take_all_available_versions' in yml['build_options']:
        singlemode = False
    add_slsa = False
    if 'add_slsa_provenance' in yml['build_options']:
        add_slsa = True

    referenced_update_rpms = None
    if 'updateinfo_packages_only' in yml['build_options']:
        if not pool.updateinfos:
            die("filtering for updates enabled, but no updateinfo found")
        if singlemode:
            die("filtering for updates enabled, but take_all_available_versions is not set")

        referenced_update_rpms = {}
        for u in sorted(pool.lookup_all_updateinfos()):
            for update in u.root.findall('update'):
                parent = update.findall('pkglist')[0].findall('collection')[0]
                for pkgentry in parent.findall('package'):
                    referenced_update_rpms[pkgentry.get('src')] = 1


    main_pkgset = create_package_set(yml, arch, flavor, 'main', pool=pool)

    missing_package = None
    for sel in main_pkgset:
        if singlemode:
            rpm = pool.lookup_rpm(arch, sel.name, sel.op, sel.epoch, sel.version, sel.release)
            rpms = [rpm] if rpm else []
        else:
            rpms = pool.lookup_all_rpms(arch, sel.name, sel.op, sel.epoch, sel.version, sel.release)

        if not rpms:
            if referenced_update_rpms is not None:
                continue
            warn(f"package {sel} not found for {arch}")
            missing_package = True
            continue

        for rpm in rpms:
            if referenced_update_rpms is not None:
                if (rpm.arch + '/' + rpm.canonfilename) not in referenced_update_rpms:
                    note(f"No update for {rpm}")
                    continue

            link_entry_into_dir(rpm, rpmdir, add_slsa=add_slsa)
            if rpm.name in supportstatus_override:
                supportstatus[rpm.name] = supportstatus_override[rpm.name]
            else:
                supportstatus[rpm.name] = sel.supportstatus

            srcrpm = rpm.get_src_package()
            if not srcrpm:
                warn(f"package {rpm} does not have a source rpm")
                continue

            if sourcedir:
                # so we need to add also the src rpm
                srpm = pool.lookup_rpm(srcrpm.arch, srcrpm.name, '=', None, srcrpm.version, srcrpm.release)
                if srpm:
                    link_entry_into_dir(srpm, sourcedir, add_slsa=add_slsa)
                else:
                    details = f"         required by  {rpm}"
                    warn(f"source rpm package {srcrpm} not found", details=details)
                    missing_package = True

            if debugdir:
                drpm = pool.lookup_rpm(arch, srcrpm.name + "-debugsource", '=', None, srcrpm.version, srcrpm.release)
                if drpm:
                    link_entry_into_dir(drpm, debugdir, add_slsa=add_slsa)

                drpm = pool.lookup_rpm(arch, rpm.name + "-debuginfo", '=', rpm.epoch, rpm.version, rpm.release)
                if drpm:
                    link_entry_into_dir(drpm, debugdir, add_slsa=add_slsa)

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        die('Abort due to missing packages')


def link_file_into_dir(source, directory, name=None):
    if not os.path.exists(directory):
        os.mkdir(directory)
    if name is None:
        name = os.path.basename(source)
    outname = directory + '/' + name
    if not os.path.exists(outname):
        if os.path.islink(source):
            # osc creates a repos/ structure with symlinks to it's cache
            # but these would point outside of our media
            shutil.copyfile(source, outname)
        else:
            os.link(source, outname)


def link_entry_into_dir(entry, directory, add_slsa=False):
    canonfilename = entry.canonfilename
    outname = directory + '/' + entry.arch + '/' + canonfilename
    if not os.path.exists(outname):
        link_file_into_dir(entry.location, directory + '/' + entry.arch, name=canonfilename)
        add_entry_to_report(entry, outname)
        if add_slsa:
            slsalocation = entry.location.removesuffix('.rpm') + '.slsa_provenance.json'
            if os.path.exists(slsalocation):
                slsaname = canonfilename.removesuffix('.rpm') + '.slsa_provenance.json'
                link_file_into_dir(slsalocation, directory + '/' + entry.arch, name=slsaname)

def add_entry_to_report(entry, outname):
    # first one wins, see link_file_into_dir
    if outname not in tree_report:
        tree_report[outname] = entry


def write_report_file(directory, outfile):
    root = ET.Element('report')
    if not directory.endswith('/'):
        directory += '/'
    for fn, entry in sorted(tree_report.items()):
        if not fn.startswith(directory):
            continue
        binary = ET.SubElement(root, 'binary')
        binary.text = 'obs://' + entry.origin
        for tag in 'name', 'epoch', 'version', 'release', 'arch', 'buildtime', 'disturl', 'license':
            val = getattr(entry, tag, None)
            if val is None or val == '':
                continue
            if tag == 'epoch' and val == 0:
                continue
            if tag == 'arch':
                binary.set('binaryarch', str(val))
            else:
                binary.set(tag, str(val))
        if entry.name.endswith('-release'):
            cpeid = entry.product_cpeid
            if cpeid:
                binary.set('cpeid', cpeid)
    tree = ET.ElementTree(root)
    tree.write(outfile)


if __name__ == "__main__":
    try:
        status = main()
    except Exception as err:
        # Error handler of last resort.
        logger.error(repr(err))
        logger.critical("shutting down due to fatal error")
        raise  # print stack trace
    else:
        raise SystemExit(status)

# vim: sw=4 et
