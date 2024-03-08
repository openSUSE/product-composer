""" Implementation of the command line interface.

"""

import os
import re
import shutil
import subprocess
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


tree_report = {}        # hashed via file name

# hardcoded defaults for now
chksums_tool = 'sha512sum'

# global db for supportstatus
supportstatus = {}
# per package override via supportstatus.txt file
supportstatus_override = {}


def main(argv=None) -> int:
    """ Execute the application CLI.

    :param argv: argument list to parse (sys.argv by default)
    :return: exit status
    """
    #
    # Setup CLI parser
    #
    parser = ArgumentParser('productcomposer', description='An example sub-command implementation')
    subparsers = parser.add_subparsers(required=True, help='sub-command help')

    # One sub parser for each command
    verify_parser = subparsers.add_parser('verify', help='The first sub-command')
    build_parser = subparsers.add_parser('build', help='The second sub-command')

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
    build_parser.add_argument('--vcs', default=None,  help='Define a source repository identifier')
    build_parser.add_argument('--clean', action='store_true',  help='Remove existing output directory first')
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

    if not args.out:
        # No subcommand was specified.
        print("No output directory given")
        parser.print_help()
        die(None)

    yml = parse_yaml(args.filename, flavor)

    directory = os.getcwd()
    if args.filename.startswith('/'):
        directory = os.path.dirname(args.filename)
    reposdir = args.reposdir if args.reposdir else directory + "/repos"

    supportstatus_fn = os.path.join(directory, 'supportstatus.txt')
    if os.path.isfile(supportstatus_fn):
        parse_supportstatus(supportstatus_fn)

    pool = Pool()
    note(f"scanning: {reposdir}")
    pool.scan(reposdir)

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
    if yml['product_compose_schema'] != 0 and yml['product_compose_schema'] != 0.1:
        die(f"Unsupported product composer schema: {yml['product_compose_schema']}")

    if 'flavors' not in yml:
        yml['flavors'] = []

    if flavor:
        if flavor not in yml['flavors']:
            die("Flavor not found: " + flavor)
        f = yml['flavors'][flavor]
        # overwrite global values from flavor overwrites
        if 'architectures' in f:
            yml['architectures'] = f['architectures']
        if 'name' in f:
            yml['name'] = f['name']
        if 'summary' in f:
            yml['summary'] = f['summary']
        if 'version' in f:
            yml['version'] = f['version']

    if 'architectures' not in yml or not yml['architectures']:
        die("No architecture defined. Maybe wrong flavor?")

    if 'build_options' not in yml:
        yml['build_options'] = []

    return yml


def parse_supportstatus(filename):
    with open(filename, 'r') as file:
        for line in file.readlines():
            a = line.strip().split(' ')
            supportstatus_override[a[0]] = a[1]


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


def run_helper(args, cwd=None, stdout=None, stdin=None, failmsg=None):
    if stdout is None:
        stdout = subprocess.PIPE
    if stdin is None:
        stdin = subprocess.PIPE
    popen = subprocess.Popen(args, stdout=stdout, stdin=stdin, cwd=cwd)
    if popen.wait():
        output = popen.stdout.read()
        if failmsg:
            die("Failed to " + failmsg, details=output)
        else:
            die("Failed to run" + args[0], details=output)
    return popen.stdout.read() if stdout == subprocess.PIPE else ''


def create_tree(outdir, product_base_dir, yml, pool, flavor, vcs=None, disturl=None):
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    maindir = outdir + '/' + product_base_dir
    rpmdir = maindir  # we may offer to set it up in sub directories
    if not os.path.exists(rpmdir):
        os.mkdir(rpmdir)

    sourcedir = debugdir = maindir

    if "source" in yml:
        if yml['source'] == 'split':
            sourcedir = outdir + '/' + product_base_dir + '-Source'
            os.mkdir(sourcedir)
        elif yml['source'] == 'drop':
            sourcedir = None
        elif yml['source'] != 'include':
            die("Bad source option, must be either 'include', 'split' or 'drop'")
    if "debug" in yml:
        if yml['debug'] == 'split':
            debugdir = outdir + '/' + product_base_dir + '-Debug'
            os.mkdir(debugdir)
        elif yml['debug'] == 'drop':
            debugdir = None
        elif yml['debug'] != 'include':
            die("Bad debug option, must be either 'include', 'split' or 'drop'")

    for arch in yml['architectures']:
        link_rpms_to_tree(rpmdir, yml, pool, arch, flavor, debugdir, sourcedir)

    for arch in yml['architectures']:
        unpack_meta_rpms(rpmdir, yml, pool, arch, flavor, medium=1)  # only for first medium am

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
    for file in os.listdir(rpmdir):
        if not file.startswith('gpg-pubkey-'):
            continue

        args = ['gpg', '--no-keyring', '--no-default-keyring', '--with-colons',
              '--import-options', 'show-only', '--import', '--fingerprint']
        out = run_helper(args, stdin=open(f'{rpmdir}/{file}', 'rb'),
                         failmsg="Finger printing of gpg file")
        for line in out.splitlines():
            if not str(line).startswith("b'fpr:"):
                continue

            default_content.append(str(line).split(':')[9])

    post_createrepo(rpmdir, yml, content=default_content, repos=repos)
    if debugdir:
        post_createrepo(debugdir, yml, content=["debug"], repos=repos)
    if sourcedir:
        post_createrepo(sourcedir, yml, content=["source"], repos=repos)

    if not os.path.exists(rpmdir + '/repodata'):
        return

    write_report_file(maindir, maindir + '.report')
    if sourcedir and maindir != sourcedir:
        write_report_file(sourcedir, sourcedir + '.report')
    if debugdir and maindir != debugdir:
        write_report_file(debugdir, debugdir + '.report')

    # CHANGELOG file
    # the tools read the subdirectory of the rpmdir from environment variable
    os.environ['ROOT_ON_CD'] = '.'
    if os.path.exists("/usr/bin/mk_changelog"):
        args = ["/usr/bin/mk_changelog", rpmdir]
        run_helper(args)

    # ARCHIVES.gz
    if os.path.exists("/usr/bin/mk_listings"):
        args = ["/usr/bin/mk_listings", rpmdir]
        run_helper(args)

    # media.X structures FIXME
    mediavendor = yml['vendor'] + ' - ' + product_base_dir
    mediaident = product_base_dir
    # FIXME: calculate from product provides
    mediaproducts = [yml['vendor'] + '-' + yml['name'] + ' ' + str(yml['version']) + '-1']
    create_media_dir(maindir, mediavendor, mediaident, mediaproducts)

    create_checksums_file(maindir)

    create_susedata_xml(rpmdir, yml)

    process_updateinfos(rpmdir, yml, pool, flavor, debugdir, sourcedir)

    # Add License File and create extra .license directory
    licensefilename = '/license.tar'
    if os.path.exists(rpmdir + '/license-' + yml['name'] + '.tar') or os.path.exists(rpmdir + '/license-' + yml['name'] + '.tar.gz'):
        licensefilename = '/license-' + yml['name'] + '.tar'
    if os.path.exists(rpmdir + licensefilename + '.gz'):
        run_helper(['gzip', '-d', rpmdir + licensefilename + '.gz'],
                   failmsg="Uncompress of license.tar.gz failed")
    if os.path.exists(rpmdir + licensefilename):
        licensedir = rpmdir + ".license"
        if not os.path.exists(licensedir):
            os.mkdir(licensedir)
        args = ['tar', 'xf', rpmdir + licensefilename, '-C', licensedir]
        output = run_helper(args, failmsg="extract license tar ball")
        if not os.path.exists(licensedir + "/license.txt"):
            die("No license.txt extracted", details=output)

        mr = ModifyrepoWrapper(
            file=rpmdir + licensefilename,
            directory=os.path.join(rpmdir, "repodata"),
        )
        mr.run_cmd()
        os.unlink(rpmdir + licensefilename)
        # meta package may bring a second file or expanded symlink, so we need clean up
        if os.path.exists(rpmdir + '/license.tar'):
            os.unlink(rpmdir + '/license.tar')
        if os.path.exists(rpmdir + '/license.tar.gz'):
            os.unlink(rpmdir + '/license.tar.gz')

    # detached signature
    args = ['/usr/lib/build/signdummy', '-d', rpmdir + "/repodata/repomd.xml"]
    run_helper(args, failmsg="create detached signature")
    args = ['/usr/lib/build/signdummy', '-d', maindir + '/CHECKSUMS']
    run_helper(args, failmsg="create detached signature for CHECKSUMS")

    # pubkey
    with open(rpmdir + "/repodata/repomd.xml.key", 'w') as pubkey_file:
        args = ['/usr/lib/build/signdummy', '-p']
        run_helper(args, stdout=pubkey_file, failmsg="write signature public key")

    # do we need an ISO file?
    if 'iso' in yml:
        for workdir in [maindir, sourcedir, debugdir]:
            application_id = re.sub(r'^.*/', '', maindir)
            args = ['/usr/bin/mkisofs', '-quiet', '-p', 'Product Composer - http://www.github.com/openSUSE/product-composer']
            args += ['-r', '-pad', '-f', '-J', '-joliet-long']
            # FIXME: do proper multi arch handling
            isolinux = 'boot/' + yml['architectures'][0] + '/loader/isolinux.bin'
            if os.path.isfile(workdir + '/' + isolinux):
                args += ['-no-emul-boot', '-boot-load-size', '4', '-boot-info-table']
                args += ['-hide', 'glump', '-hide-joliet', 'glump']
                args += ['-eltorito-alt-boot', '-eltorito-platform', 'efi']
                args += ['-no-emul-boot']
                # args += [ '-sort', $sort_file ]
                # args += [ '-boot-load-size', block_size("boot/"+arch+"/loader") ]
                args += ['-b', isolinux]
            if 'publisher' in yml['iso']:
                args += ['-publisher', yml['iso']['publisher']]
            if 'volume_id' in yml['iso']:
                args += ['-V', yml['iso']['volume_id']]
            args += ['-A', application_id]
            args += ['-o', workdir + '.iso', workdir]
            run_helper(args, cwd=maindir, failmsg="create iso file")

    # create SBOM data
    if os.path.exists("/usr/lib/build/generate_sbom"):
        spdx_distro = "ALP"
        spdx_distro += "-" + str(yml['version'])
        # SPDX
        args = ["/usr/lib/build/generate_sbom",
                 "--format", 'spdx',
                 "--distro", spdx_distro,
                 "--product", rpmdir
               ]
        with open(rpmdir + ".spdx.json", 'w') as sbom_file:
            run_helper(args, stdout=sbom_file, failmsg="run generate_sbom for SPDX")

        # CycloneDX
        args = ["/usr/lib/build/generate_sbom",
                 "--format", 'cyclonedx',
                 "--distro", spdx_distro,
                 "--product", rpmdir
               ]
        with open(rpmdir + ".cdx.json", 'w') as sbom_file:
            run_helper(args, stdout=sbom_file, failmsg="run generate_sbom for CycloneDX")

# create media info files


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
        if dir == '':
            dir = '/usr/src/packages/'
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

# Create the main susedata.xml with support and disk usage informations


def create_susedata_xml(rpmdir, yml):
    # get supported translations based on local packages
    i18ndir = '/usr/share/locale/en_US/LC_MESSAGES/'
    p = re.compile('package-translations-(.+).mo')
    languages = []
    i18ndata = {}
    i18ndata_count = {}
    i18ntrans = {}
    import gettext
    for file in os.listdir(i18ndir):
        m = p.match(file)
        if m:
            lang = m.group(1)
            languages.append(lang)
            i18ntrans[lang] = gettext.translation(f'package-translations-{lang}',
                                                  languages=['en_US'])

    # read repomd.xml
    ns = '{http://linux.duke.edu/metadata/repo}'
    tree = ET.parse(rpmdir + '/repodata/repomd.xml')
    primary_fn = tree.find(f".//{ns}data[@type='primary']/{ns}location").get('href')

    # read compressed primary.xml
    openfunction = None
    if primary_fn.endswith('.gz'):
        import gzip
        openfunction = gzip.open
    elif primary_fn.endswith('.zst'):
        import zstandard
        openfunction = zstandard.open
    else:
        die(f"unsupported primary compression type ({primary_fm})")
    tree = ET.parse(openfunction(rpmdir + '/' + primary_fn, 'rb'))
    ns = '{http://linux.duke.edu/metadata/common}'

    # Create susedata structure
    susedata = ET.Element('susedata')
    susedata.set('xmlns', 'http://linux.duke.edu/metadata/susedata')
    # go for every rpm file of the repo via the primary
    count = 0
    for pkg in tree.findall(f".//{ns}package[@type='rpm']"):
        name = pkg.find(f'{ns}name').text
        pkgid = pkg.find(f'{ns}checksum').text
        arch = pkg.find(f'{ns}arch').text
        version = pkg.find(f'{ns}version').attrib

        package = ET.SubElement(susedata, 'package')
        package.set('name', name)
        package.set('pkgid', pkgid)
        package.set('arch', arch)
        ET.SubElement(package, 'version', version)
        if name in supportstatus and supportstatus[name] is not None:
            ET.SubElement(package, 'keyword').text = f'support_{supportstatus[name]}'
        location = pkg.find(f'{ns}location').get('href')
        if os.path.exists(rpmdir + '/' + location):
            p = Package()
            p.location = rpmdir + '/' + location
            dudata = generate_du_data(p, 3)
            if dudata:
                duelement = ET.SubElement(package, 'diskusage')
                dirselement = ET.SubElement(duelement, 'dirs')
                for duitem in dudata:
                    ET.SubElement(dirselement, 'dir', { 'name': duitem[0], 'size': str(duitem[1]), 'count': str(duitem[2]) })
        count += 1

        # look for pattern category
        category = None
        for c in pkg.findall(".//{http://linux.duke.edu/metadata/rpm}entry[@name='pattern-category()']"):
            category = Package._cpeid_hexdecode(c.get('ver'))

        # looking for translations for this package
        summary = pkg.find(f'{ns}summary').text
        description = pkg.find(f'{ns}description').text
        for lang in languages:
            isummary = i18ntrans[lang].gettext(summary)
            idescription = i18ntrans[lang].gettext(description)
            icategory = i18ntrans[lang].gettext(category) if category else None
            if isummary == summary and idescription == description and icategory == category:
                continue
            if lang not in i18ndata:
                i18ndata[lang] = ET.Element('susedata')
                i18ndata[lang].set('xmlns', 'http://linux.duke.edu/metadata/susedata')
                i18ndata_count[lang] = 0
            i18ndata_count[lang] += 1
            ipackage = ET.SubElement(i18ndata[lang], 'package')
            ipackage.set('name', name)
            ipackage.set('pkgid', pkgid)
            ipackage.set('arch', arch)
            ET.SubElement(ipackage, 'version', version)
            if isummary != summary:
                ET.SubElement(ipackage, 'summary', {'lang': lang}).text = isummary
            if idescription != description:
                ET.SubElement(ipackage, 'description', {'lang': lang}).text = idescription
            if icategory != category:
                ET.SubElement(ipackage, 'category', {'lang': lang}).text = icategory
    susedata.set('packages', str(count))
    ET.indent(susedata, space="    ", level=0)

    susedata_fn = rpmdir + '/susedata.xml'
    with open(susedata_fn, 'x') as sd_file:
        sd_file.write(ET.tostring(susedata, encoding=ET_ENCODING))
    mr = ModifyrepoWrapper(
        file=susedata_fn,
        directory=os.path.join(rpmdir, "repodata"),
    )
    mr.run_cmd()
    os.unlink(susedata_fn)

    for lang in i18ndata:
        i18ndata[lang].set('packages', str(i18ndata_count[lang]))
        susedata_fn = rpmdir + f'/susedata.{lang}.xml'
        ET.indent(i18ndata[lang], space="    ", level=0)

        with open(susedata_fn, 'x') as sd_file:
            sd_file.write(ET.tostring(i18ndata[lang], encoding=ET_ENCODING))
        mr = ModifyrepoWrapper(
            file=susedata_fn,
            mdtype=f'susedata.{lang}',
            directory=os.path.join(rpmdir, "repodata"),
        )
        mr.run_cmd()
        os.unlink(susedata_fn)


# Add updateinfo.xml to metadata
def process_updateinfos(rpmdir, yml, pool, flavor, debugdir, sourcedir):
    if not pool.updateinfos:
        return

    missing_package = False

    # build the union of the package sets for all requested architectures
    main_pkgset = PkgSet('main')
    for arch in yml['architectures']:
        pkgset = main_pkgset.add(create_package_set(yml, arch, flavor, 'main'))
    main_pkgset_names = main_pkgset.names()

    uitemp = None

    for u in sorted(pool.lookup_all_updateinfos()):
        note("Add updateinfo " + u.location)
        for update in u.root.findall('update'):
            needed = False
            parent = update.findall('pkglist')[0].findall('collection')[0]

            for pkgentry in parent.findall('package'):
                src = pkgentry.get('src')
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
        die('Abort due to missing packages')


def post_createrepo(rpmdir, yml, content=[], repos=[]):
    product_name = yml['name']
    product_summary = yml['summary'] or yml['name']
    product_summary += " " + str(yml['version'])

    cr = CreaterepoWrapper(directory=".")
    cr.distro = product_summary
    # FIXME: /o is only for operating systems, we have nothing else atm
    cr.cpeid = f"cpe:/o:{yml['vendor']}:{yml['name']}:{yml['version']}"
    cr.repos = repos
# cr.split = True
    # cr.baseurl = "media://"
    cr.content = content
    cr.excludes = ["boot"]
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
    for unpack_pkgset_name in yml.get('unpack', ['unpack']):
        unpack_pkgset = create_package_set(yml, arch, flavor, unpack_pkgset_name)
        for sel in unpack_pkgset:
            rpm = pool.lookup_rpm(arch, sel.name, sel.op, sel.epoch, sel.version, sel.release)
            if not rpm:
                warn(f"package {sel} not found")
                missing_package = True
                continue
            unpack_one_meta_rpm(rpmdir, rpm, medium)

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        die('Abort due to missing packages')


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


def create_package_set(yml, arch, flavor, setname):
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
            if flavor is None or flavor not in entry['flavors']:
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

    main_pkgset = create_package_set(yml, arch, flavor, 'main')

    missing_package = None
    for sel in main_pkgset:
        if singlemode:
            rpm = pool.lookup_rpm(arch, sel.name, sel.op, sel.epoch, sel.version, sel.release)
            rpms = [rpm] if rpm else []
        else:
            rpms = pool.lookup_all_rpms(arch, sel.name, sel.op, sel.epoch, sel.version, sel.release)

        if not rpms:
            warn(f"package {sel} not found for {arch}")
            missing_package = True
            continue

        for rpm in rpms:
            link_entry_into_dir(rpm, rpmdir)
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
                    link_entry_into_dir(srpm, sourcedir)
                else:
                    details = f"         required by  {rpm}"
                    warn(f"source rpm package {srcrpm} not found", details=details)
                    missing_package = True

            if debugdir:
                drpm = pool.lookup_rpm(arch, srcrpm.name + "-debugsource", '=', None, srcrpm.version, srcrpm.release)
                if drpm:
                    link_entry_into_dir(drpm, debugdir)

                drpm = pool.lookup_rpm(arch, rpm.name + "-debuginfo", '=', rpm.epoch, rpm.version, rpm.release)
                if drpm:
                    link_entry_into_dir(drpm, debugdir)

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        die('Abort due to missing packages')


def link_file_into_dir(filename, directory):
    if not os.path.exists(directory):
        os.mkdir(directory)
    outname = directory + '/' + os.path.basename(filename)
    if not os.path.exists(outname):
        if os.path.islink(filename):
            # osc creates a repos/ structure with symlinks to it's cache
            # but these would point outside of our media
            shutil.copyfile(filename, outname)
        else:
            os.link(filename, outname)


def link_entry_into_dir(entry, directory):
    link_file_into_dir(entry.location, directory + '/' + entry.arch)
    add_entry_to_report(entry, directory)


def add_entry_to_report(entry, directory):
    outname = directory + '/' + entry.arch + '/' + os.path.basename(entry.location)
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
