""" Implementation of the command line interface.

"""

import os
import re
import shutil
import subprocess
from argparse import ArgumentParser
from xml.etree import ElementTree as ET

import rpm
import yaml

from . import __version__
from .core.logger import logger
from .wrappers import CreaterepoWrapper
from .wrappers import ModifyrepoWrapper


__all__ = "main",


ET_ENCODING = "unicode"


local_rpms = {}  # hased via name
local_updateinfos = {}  # sorted by updateinfo_id

tree_report = {}        # hashed via file name

# hardcoded defaults for now
chksums_tool = 'sha512sum'


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
    if not args.out:
        # No subcommand was specified.
        print("No output directory given")
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

    yml, archlist = parse_yaml(args.filename, flavor)
    directory = os.getcwd()
    if args.filename.startswith('/'):
        directory = os.path.dirname(args.filename)
    reposdir = args.reposdir if args.reposdir else directory + "/repos"
    scan_rpms(reposdir, yml)

    if args.clean and os.path.exists(args.out):
        shutil.rmtree(args.out)

    product_base_dir = get_product_dir(yml, flavor, archlist, args.release)

    kwdfile = args.filename.removesuffix('.productcompose') + '.kwd'
    create_tree(args.out, product_base_dir, yml, kwdfile, flavor, archlist)


def verify(args):
    parse_yaml(args.filename, args.flavor)

def parse_yaml(filename, flavor):

    with open(filename, 'r') as file:
        yml = yaml.safe_load(file)

    if 'product_compose_schema' not in yml:
        die('missing product composer schema')
    if yml['product_compose_schema'] != 0:
        die("Unsupported product composer schema: " + yml['product_compose_schema'])

    archlist = None
    if 'architectures' in yml:
        archlist = yml['architectures']
    if flavor:
        if 'flavors' not in yml or flavor not in yml['flavors']:
            die("Flavor not found: " + flavor)
        f = yml['flavors'][flavor]
        if 'architectures' in f:
            archlist = f['architectures']

    if archlist is None:
        die("No architecture defined")

    return yml, archlist

def get_product_dir(yml, flavor, archlist, release):
    name = yml['name'] + "-" + str(yml['version'])
    if 'product_directory_name' in yml:
        # manual override
        name = yml['product_directory_name']
    if flavor and not 'hide_flavor_in_product_directory_name' in yml['build_options']:
        name += "-" + flavor
    if archlist:
        visible_archs = archlist
        if 'local' in visible_archs:
            visible_archs.remove('local')
        name += "-" + "-".join(visible_archs)
    if release:
        name += "-Build" + str(release)
    if '/' in name:
        die("Illegal product name")
    return name


def run_helper(args, cwd=None, stdout=None, failmsg=None):
    if stdout is None:
        stdout=subprocess.PIPE
    popen = subprocess.Popen(args, stdout=stdout, cwd=cwd)
    if popen.wait():
        output = popen.stdout.read()
        if failmsg:
            die("Failed to " + failmsg, details=output)
        else:
            die("Failed to run" + args[0], details=output)
    return popen.stdout.read() if stdout == subprocess.PIPE else ''

def create_tree(outdir, product_base_dir, yml, kwdfile, flavor, archlist):
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    maindir = outdir + '/' + product_base_dir
    rpmdir = maindir # we may offer to set it up in sub directories
    if not os.path.exists(rpmdir):
        os.mkdir(rpmdir)

    sourcedir = debugdir = maindir

    if "source" in yml:
        if yml['source'] == 'split':
            sourcedir = outdir + '/' + product_base_dir + '-Source'
            os.mkdir(sourcedir)
        elif yml['source'] == 'drop':
            sourcedir = None
        else:
            die("Bad source option, must be either 'split' or 'drop'")
    if "debug" in yml:
        if yml['debug'] == 'split':
            debugdir = outdir + '/' + product_base_dir + '-Debug'
            os.mkdir(debugdir)
        elif yml['debug'] == 'drop':
            debugdir = None 
        else:
            die("Bad debug option, must be either 'split' or 'drop'")

    for arch in archlist:
        link_rpms_to_tree(rpmdir, yml, arch, flavor, debugdir, sourcedir)

    for arch in archlist:
        unpack_meta_rpms(rpmdir, yml, arch, flavor, medium=1) # only for first medium am

    post_createrepo(rpmdir, yml['name'])
    if debugdir:
        post_createrepo(debugdir, yml['name'], content=["debug"])
    if sourcedir:
        post_createrepo(sourcedir, yml['name'], content=["source"])

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
        args = [ "/usr/bin/mk_changelog", rpmdir ]
        run_helper(args)

    # ARCHIVES.gz
    if os.path.exists("/usr/bin/mk_listings"):
        args = [ "/usr/bin/mk_listings", rpmdir ]
        run_helper(args)

    # media.X structures FIXME
    mediavendor = yml['vendor'] + ' - ' + product_base_dir
    mediaident = product_base_dir
    # FIXME: calculate from product provides
    mediaproducts = [ yml['vendor'] + '-' + yml['name'] + ' ' + str(yml['version']) + '-1' ]
    create_media_dir(maindir, mediavendor, mediaident, mediaproducts)

    # CHECKSUMS file
    create_checksums_file(maindir)

    # repodata/appdata
    # currently not supported in ALP?
#   if os.path.exists("/usr/bin/openSUSE-appstream-process"):
#       args = [ "/usr/bin/openSUSE-appstream-process",
#                rpmdir, rpmdir + "/repodata" ]
#       run_helper(args)

    # repodata/*susedata*
    if os.path.exists("/usr/bin/add_product_susedata"):
        args = [ "/usr/bin/add_product_susedata", '-u',
                 '-k', kwdfile, '-p',
                 '-e', '/usr/share/doc/packages/eulas',
                 '-d', rpmdir ]
        run_helper(args)

    if local_updateinfos:
        process_updateinfos(rpmdir, yml, archlist, flavor, debugdir, sourcedir)

    # Add License File and create extra .license directory
    if os.path.exists(rpmdir + "/license.tar.gz"):
        run_helper(['gzip', '-d', rpmdir + "/license.tar.gz"],
                   failmsg="Uncompress of license.tar.gz failed")
    if os.path.exists(rpmdir + "/license.tar"):
        licensedir = rpmdir + ".license"
        if not os.path.exists(licensedir):
            os.mkdir(licensedir)
        args = [ 'tar', 'xf', rpmdir + "/license.tar", '-C', licensedir ]
        output = run_helper(args, failmsg="extract license tar ball")
        if not os.path.exists(licensedir + "/license.txt"):
            die("No license.txt extracted", details=output)

        mr = ModifyrepoWrapper(
            file=os.path.join(rpmdir, "license.tar"),
            directory=rpmdir,
        )
        mr.run_cmd()
        os.unlink(rpmdir + '/license.tar')

    # detached signature
    args = [ '/usr/lib/build/signdummy', '-d', rpmdir + "/repodata/repomd.xml" ]
    run_helper(args, failmsg="create detached signature")
    args = [ '/usr/lib/build/signdummy', '-d', maindir + '/CHECKSUMS' ]
    run_helper(args, failmsg="create detached signature for CHECKSUMS")

    # detached pubkey
    args = [ '/usr/lib/build/signdummy', '-p', rpmdir + "/repodata/repomd.xml" ]
    with open(rpmdir + "/repodata/repomd.xml.key", 'w') as pubkey_file:
        run_helper(args, stdout=pubkey_file, failmsg="write signature public key")

    # do we need an ISO file?
    if 'iso' in yml:
        application_id = re.sub(r'^.*/', '', maindir)
        args = [ '/bin/mkisofs', '-p', 'Product Composer - http://www.github.com/openSUSE/product-composer' ]
        if True: # x86_64 efi only atm
            args += [ '-r', '-pad', '-f', '-J', '-joliet-long' ]
            args += [ '-no-emul-boot', '-boot-load-size', '4', '-boot-info-table' ]
            args += [ '-hide', 'glump', '-hide-joliet', 'glump' ]
            #args += [ '-eltorito-alt-boot', '-eltorito-platform', 'efi' ]
            args += [ '-no-emul-boot' ]
            #args += [ '-sort', $sort_file ]
            #args += [ '-boot-load-size', block_size("boot/"+arch+"/loader") ]
            # FIXME: cannot use arch, we have an archlist!
            args += [ '-b', "boot/"+arch+"/loader/isolinux.bin"]
        if 'publisher' in yml['iso']:
            args += [ '-publisher', yml['iso']['publisher'] ]
        if 'volume_id' in yml['iso']:
            args += [ '-V', yml['iso']['volume_id'] ]
        args += [ '-A', application_id ]
        args += [ '-o', maindir + '.iso', maindir ]
        run_helper(args, cwd=maindir, failmsg="create iso file")

    # create SBOM data
    if os.path.exists("/usr/lib/build/generate_sbom"):
        spdx_distro = "ALP"
        spdx_distro += "-" + str(yml['version'])
        # SPDX
        args = [ "/usr/lib/build/generate_sbom",
                 "--format", 'spdx',
                 "--distro", spdx_distro,
                 "--product", rpmdir 
               ]
        with open(rpmdir + ".spdx.json", 'w') as sbom_file:
            run_helper(args, stdout=sbom_file, failmsg="run generate_sbom for SPDX")

        # CycloneDX
        args = [ "/usr/lib/build/generate_sbom",
                 "--format", 'cyclonedx',
                 "--distro", spdx_distro,
                 "--product", rpmdir 
               ]
        with open(rpmdir + ".cdx.json", 'w') as sbom_file:
            run_helper(args, stdout=sbom_file, failmsg="run generate_sbom for CycloneDX")

# create media info files
def create_media_dir(maindir, vendorstr, identstr, products):
    media1dir = maindir + '/' + 'media.1'
    os.mkdir(media1dir) # we do only support seperate media atm
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

# create a fake entry from an updateinfo package spec
def create_updateinfo_entry(pkgentry):
    tags = {}
    for tag in 'name', 'epoch', 'version', 'release', 'arch':
        tags[tag] = pkgentry.get(tag)
    return { "tags": tags }

def create_updateinfo_packagefilter(yml, archlist, flavor):
    package_filter = {}
    for arch in archlist:
        for package in create_package_list(yml['packages'], arch, flavor):
            name = package
            match = re.match(r'([^><=]*)([><=]=?)(.*)', name.replace(' ', ''))
            if match:
                name = match.group(1)
            if name not in package_filter:
                package_filter[name] = [ package ]
            else:
                package_filter[name].append(package)
    return package_filter

def entry_matches_updateinfo_packagefilter(entry, package_filter):
    name = entry['tags']['name']
    if name in package_filter:
        for pfspec in package_filter[name]:
            pfname, pfop, pfepoch, pfversion, pfrelease = split_package_spec(pfspec)
            if entry_qualifies(entry, None, pfname, pfop, pfepoch, pfversion, pfrelease):
                return True
    return False

# Add updateinfo.xml to metadata
def process_updateinfos(rpmdir, yml, archlist, flavor, debugdir, sourcedir):
    missing_package = False
    package_filter = create_updateinfo_packagefilter(yml, archlist, flavor)
    uitemp = None

    for ufn, u in sorted(local_updateinfos.items()):
        note("Add updateinfo " + ufn)
        for update in u.findall('update'):
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
                if pkgarch != 'noarch' and pkgarch not in archlist:
                    parent.remove(pkgentry)
                    continue

                # check if we should have this package
                if name in package_filter:
                    entry = create_updateinfo_entry(pkgentry)
                    if entry_matches_updateinfo_packagefilter(entry, package_filter):
                        warn("package " + entry_nvra(entry) + " not found")
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
            directory=rpmdir,
        )
        mr.run_cmd()

        os.unlink(rpmdir + '/updateinfo.xml')

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        die('Abort due to missing packages')


def post_createrepo(rpmdir, product_name, content=None):
    # FIXME
    distroname = "testgin"

    # FIXME
    content = content or []
    # content.append("pool"]

    cr = CreaterepoWrapper(directory=".")
    cr.distro = distroname
    # cr.split = True
    # cr.baseurl = "media://"
    cr.content = content
    cr.excludes = ["boot"]
    cr.run_cmd(cwd=rpmdir, stdout=subprocess.PIPE)


def unpack_meta_rpms(rpmdir, yml, arch, flavor, medium):
    if not yml['unpack_packages']:
        return

    missing_package = False
    for package in create_package_list(yml['unpack_packages'], arch, flavor):
        name, op, epoch, version, release = split_package_spec(package)
        rpm = lookup_rpm(arch, name, op, epoch, version, release)
        if not rpm:
            warn("package " + package + " not found")
            missing_package = True
            continue

        tempdir = rpmdir + "/temp"
        os.mkdir(tempdir)
        run_helper(['unrpm', '-q', rpm['filename']], cwd=tempdir, failmsg=("extract " + rpm['filename']))

        skel_dir = tempdir + "/usr/lib/skelcd/CD" + str(medium)
        if os.path.exists(skel_dir):
            shutil.copytree(skel_dir, rpmdir, dirs_exist_ok=True)

        shutil.rmtree(tempdir)

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        die('Abort due to missing packages')

def create_package_list(yml, arch, flavor):
    packages = []
    for entry in list(yml):
        if type(entry) == dict:
            if 'flavors' in entry:
                if flavor not in entry['flavors']:
                    continue
            if 'architectures' in entry:
                if arch not in entry['architectures']:
                    continue
            packages += entry['packages']
        else:
            packages.append(entry)

    return packages

def split_package_spec(pkgspec):
    name = pkgspec
    match = re.match(r'([^><=]*)([><=]=?)(.*)', name.replace(' ', ''))
    if match:
        name    = match.group(1)
        op      = match.group(2)
        epoch = '0'
        version = match.group(3)
        release = None
        if ':' in version:
            (epoch, version) = version.split(':', 2)
        if '-' in version:
            (version, release) = version.rsplit('-', 2)
        return (name, op, epoch, version, release)
    return (name, None, None, None, None)


def link_rpms_to_tree(rpmdir, yml, arch, flavor, debugdir=None, sourcedir=None):
    singlemode = True
    if 'take_all_available_versions' in yml['build_options']:
        singlemode = False

    missing_package = None
    for package in create_package_list(yml['packages'], arch, flavor):
        name, op, epoch, version, release = split_package_spec(package)
        if singlemode:
            rpm = lookup_rpm(arch, name, op, epoch, version, release)
            rpms = [rpm] if rpm else []
        else:
            rpms = lookup_all_rpms(arch, name, op, epoch, version, release)

        if not rpms:
            warn("package " + package + " not found for " + arch)
            missing_package = True
            continue

        for rpm in rpms:
            link_entry_into_dir(rpm, rpmdir)

            match = re.match(r'^(.*)-([^-]*)-([^-]*)\.([^\.]*)\.rpm$', rpm['tags']['sourcerpm'])
            if not match:
                warn("package " + entry_nvra(rpm) + " does not have a source rpm")
                continue

            source_package_name    = match.group(1)
            # no chance to get a epoch from file name
            source_package_version = match.group(2)
            source_package_release = match.group(3)
            source_package_arch    = match.group(4)
            if sourcedir:
                # so we need to add also the src rpm
                srpm = lookup_rpm(source_package_arch, source_package_name, '=', None, source_package_version, source_package_release)
                if srpm:
                    link_entry_into_dir(srpm, sourcedir)
                else:
                    details="         required by  " + entry_nvra(rpm)
                    warn("source rpm package " + source_package_name + "-" + source_package_version + '-' + 'source_package_release' + '.' + source_package_arch + " not found", details=details)
                    missing_package = True

            if debugdir:
                drpm = lookup_rpm(arch, source_package_name + "-debugsource", '=', None, source_package_version, source_package_release)
                if drpm:
                    link_entry_into_dir(drpm, debugdir)

                drpm = lookup_rpm(arch, rpm['tags']['name'] + "-debuginfo", '=', rpm['tags']['epoch'], rpm['tags']['version'], rpm['tags']['release'])
                if drpm:
                    link_entry_into_dir(drpm, debugdir)

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        die('Abort due to missing packages')

def link_file_into_dir(filename, directory):
    if not os.path.exists(directory):
        os.mkdir(directory)
    outname = directory + '/' + os.path.basename(filename)
    if not os.path.exists(outname):
        os.link(filename, outname)


def link_entry_into_dir(entry, directory):
    link_file_into_dir(entry['filename'], directory + '/' + entry['tags']['arch'])
    add_entry_to_report(entry, directory)

def add_entry_to_report(entry, directory):
    outname = directory + '/' + entry['tags']['arch'] + '/' + os.path.basename(entry['filename'])
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
        binary.text = 'obs://' + entry['origin']
        tags = entry['tags']
        for tag in 'name', 'epoch', 'version', 'release', 'arch', 'buildtime', 'disturl', 'license':
            if tags[tag] is None or tags[tag] == '':
                continue
            if tag == 'epoch' and tags[tag] == 0:
                continue
            if tag == 'arch':
                binary.set('binaryarch', str(tags[tag]))
            else:
                binary.set(tag, str(tags[tag]))
        if tags['name'].endswith('-release'):
            cpeid = read_cpeid(entry['filename'])
            if cpeid:
                binary.set('cpeid', cpeid)
    tree = ET.ElementTree(root)
    tree.write(outfile)

def entry_qualifies(entry, arch, name, op, epoch, version, release):
    tags = entry['tags']

    if name and tags['name'] != name:
        return False

    if arch and tags['arch'] != arch:
        if arch == 'src' or arch == 'nosrc' or tags['arch'] != 'noarch':
            return False

    if op:
        # We must not hand over the release when the release is not required by the user
        # or the equal case will never be true.
        tepoch = tags['epoch'] if epoch is not None else None
        trelease = tags['release'] if release is not None else None
        cmp = rpm.labelCompare((tepoch, tags['version'], trelease), (epoch, version, release))
        if cmp > 0:
            return op[0] == '>'
        if cmp < 0:
            return op[0] == '<'
        return '=' in op

    return True

def entry_nvra(entry):
    tags = entry['tags']
    return tags['name'] + "-" + tags['version'] + "-" + tags['release'] + "." + tags['arch']

def lookup_all_rpms(arch, name, op=None, epoch=None, version=None, release=None):
    if not name in local_rpms:
        return []

    rpms = []
    for lrpm in local_rpms[name]:
        if entry_qualifies(lrpm, arch, name, op, epoch, version, release):
            rpms.append(lrpm)
    return rpms

def lookup_rpm(arch, name, op=None, epoch=None, version=None, release=None):
    if not name in local_rpms:
        return None

    candidate = None
    for lrpm in local_rpms[name]:
        if not entry_qualifies(lrpm, arch, name, op, epoch, version, release):
            continue
        if candidate:
            # version compare
            tags = lrpm['tags']
            ctags = candidate['tags']
            if rpm.labelCompare((tags['epoch'], tags['version'], tags['release']), (ctags['epoch'], ctags['version'], ctags['release'])) <= 0:
                continue
        candidate = lrpm

    return candidate

def scan_rpms(directory, yml):
    # This function scans all local available rpms and builds up the
    # query database
    ts = rpm.TransactionSet()
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)

    for dirpath, dirs, files in os.walk(directory):
        reldirpath = os.path.relpath(dirpath, directory)
        subdirs = reldirpath.split('/')
        if len(subdirs) < 1:
            continue
        arch = subdirs[-1]
        note("scanning: " + reldirpath)
        for filename in files:
            fname = os.path.join(dirpath, filename)
            if arch == 'updateinfo':
                local_updateinfos[fname] = ET.parse(fname).getroot()
                continue
            if filename.endswith('.rpm'):
                fd = os.open(fname, os.O_RDONLY)
                h = ts.hdrFromFdno(fd)
                os.close(fd)
                tags = {}
                for tag in 'name', 'epoch', 'version', 'release', 'arch', 'sourcerpm', 'nosource', 'nopatch', 'buildtime', 'disturl', 'license':
                    tags[tag] = h[tag]

                if not tags['sourcerpm']:
                    tags['arch'] = 'nosrc' if tags['nosource'] or tags['nopatch'] else 'src'

                item = { 'filename': fname, 'origin':os.path.join(reldirpath, filename), 'tags': tags }

                # add entry to local_rpms hash
                name = tags['name']
                if not name in local_rpms:
                    local_rpms[name] = []
                local_rpms[name].append(item)

def cpeid_hexdecode(p):
    pout = ''
    while True:
        match = re.match(r'^(.*?)%([0-9a-fA-F][0-9a-fA-F])(.*)', p)
        if not match:
            return pout + p
        pout = pout + match.group(1) + chr(int(match.group(2), 16))
        p = match.group(3)

def read_cpeid(fname):
    ts = rpm.TransactionSet()
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
    fd = os.open(fname, os.O_RDONLY)
    h = ts.hdrFromFdno(fd)
    os.close(fd)
    pn = h['providename']
    pf = h['provideflags']
    pv = h['provideversion']
    if pn and pf and pv:
        idx = 0
        for p in h['providename']:
            if p == 'product-cpeid()':
                f = pf[idx]
                v = pv[idx]
                if v and f and (f & 14) == 8:
                    return cpeid_hexdecode(v)
            idx = idx + 1
    return None

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
