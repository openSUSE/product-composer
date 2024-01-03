""" Implementation of the command line interface.

"""

import os
import re
import shutil
import subprocess
from argparse import ArgumentParser
from xml.etree import ElementTree as ET

import yaml

from . import __version__
from .core.logger import logger
from .rpm import split_nevra
from .solv import Pool
from .updateinfo import Updateinfo
from .wrappers import CreaterepoWrapper
from .wrappers import ModifyrepoWrapper


__all__ = "main",


ET_ENCODING = "unicode"


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

    pool = Pool()
    pool.repo.add_rpms(reposdir)
    pool.internalize()

    updateinfo = Updateinfo()
    updateinfo.add_xmls(reposdir)

    if args.clean and os.path.exists(args.out):
        shutil.rmtree(args.out)

    product_base_dir = get_product_dir(yml, flavor, archlist, args.release)

    kwdfile = args.filename.removesuffix('.productcompose') + '.kwd'
    create_tree(args.out, product_base_dir, yml, pool, updateinfo, kwdfile, flavor, archlist)

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

def create_tree(outdir, product_base_dir, yml, pool, updateinfo, kwdfile, flavor, archlist):
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

    included_rpms = set()
    for arch in archlist:
        included_rpms |= link_rpms_to_tree(rpmdir, yml, pool, arch, flavor, debugdir, sourcedir)

    for arch in archlist:
        unpack_meta_rpms(rpmdir, yml, pool, arch, flavor, medium=1) # only for first medium am

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

    _, unmatched = updateinfo.filter_packages(included_rpms, archlist)
    if unmatched and not "ignore_missing_packages" in yml["build_options"]:
        die('Abort due to missing packages: ' + ", ".join(sorted([str(i) for i in unmatched])))

    if updateinfo:
        # TODO: use a temp dir
        updateinfo_path = os.path.join(rpmdir, "updateinfo.xml")

        with open(updateinfo_path, "w") as f:
            f.write(updateinfo.to_string())

        mr = ModifyrepoWrapper(
            file=updateinfo_path,
            directory=rpmdir,
        )
        mr.run_cmd()

        os.unlink(updateinfo_path)

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


def unpack_meta_rpms(rpmdir, yml, pool, arch, flavor, medium):
    if not yml['unpack_packages']:
        return

    missing_package = False
    for pattern in create_package_list(yml['unpack_packages'], arch, flavor):
        print(f"Unpacking {pattern}...")
        rpms = pool.match(pattern, arch=arch, latest=True)
        assert len(rpms) <= 1

        if not rpms:
            warn(f"package {pattern} not found")
            missing_package = True
            continue

        rpm = rpms[0]

        tempdir = rpmdir + "/temp"
        os.mkdir(tempdir)
        run_helper(['unrpm', '-q', rpm.location], cwd=tempdir, failmsg=f"extract {rpm.location}")

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


def link_rpms_to_tree(rpmdir, yml, pool, arch, flavor, debugdir=None, sourcedir=None):
    result = set()

    singlemode = True
    if 'take_all_available_versions' in yml['build_options']:
        singlemode = False

    missing_package = None
    for package in create_package_list(yml['packages'], arch, flavor):
        rpms = pool.match(package, arch=arch, latest=singlemode)

        if not rpms:
            warn(f"package '{package}' not found for architecture '{arch}'")
            missing_package = True
            continue

        for rpm in rpms:
            assert rpm.arch in [arch, "noarch"]

            link_entry_into_dir(rpm, rpmdir)
            result.add(rpm)

            srpm_name, srpm_epoch, srpm_version, srpm_release, srpm_arch = split_nevra(rpm.sourcerpm)

            if sourcedir:
                # so we need to add also the src rpm
                pattern = f"{srpm_name} = {srpm_version}-{srpm_release}"
                source_rpms = pool.match(pattern, arch="src")

                if not source_rpms:
                    details=f"         required by {rpm}"
                    warn(f"source rpm package {rpm.sourcerpm} not found", details=details)
                    missing_package = True

                for i in source_rpms:
                    link_entry_into_dir(i, sourcedir)

            if debugdir:
                pattern = f"{srpm_name}-debugsource = {srpm_version}-{srpm_release}"
                debugsource_rpms = pool.match(pattern, arch=arch)
                for i in debugsource_rpms:
                    link_entry_into_dir(i, debugdir)

                pattern = f"{rpm.name}-debuginfo = {rpm.version}-{rpm.release}"
                debuginfo_rpms = pool.match(pattern, arch=arch)
                for i in debuginfo_rpms:
                    link_entry_into_dir(i, debugdir)

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        die('Abort due to missing packages')

    return result

def link_file_into_dir(filename, directory):
    if not os.path.exists(directory):
        os.mkdir(directory)
    outname = directory + '/' + os.path.basename(filename)
    if not os.path.exists(outname):
        os.link(filename, outname)

def link_entry_into_dir(rpm, directory):
    # TODO: store list of linked files instead of maintaining `tree_report`
    link_file_into_dir(rpm.location, directory + '/' + rpm.arch)
    add_entry_to_report(rpm, directory)

def add_entry_to_report(rpm, directory):
    outname = directory + '/' + rpm.arch + '/' + os.path.basename(rpm.location)
    # first one wins, see link_file_into_dir
    if outname not in tree_report:
        tree_report[outname] = {
            # TODO: set proper value to origin
            "origin": os.path.basename(rpm.location),
            "rpm": rpm,
        }

def write_report_file(directory, outfile):
    root = ET.Element('report')
    if not directory.endswith('/'):
        directory += '/'

    # TODO: properly order by package nevra?
    for fn, entry in sorted(tree_report.items()):
        if not fn.startswith(directory):
            continue

        binary = ET.SubElement(root, 'binary')
        binary.text = f"obs://{entry['origin']}"

        rpm = entry["rpm"]

        for tag in ("name", "epoch", "version", "release", "arch", "buildtime", "disturl", "license"):
            value = getattr(rpm, tag)

            if not value:
                continue

            if isinstance(value, int):
                value = str(value)

            if tag == "epoch" and value == "0":
                continue

            if tag == "arch":
                tag = "binaryarch"

            binary.set(tag, value)

        if rpm.product_cpeid:
            binary.set("cpeid", rpm.product_cpeid)

    tree = ET.ElementTree(root)
    ET.indent(root)
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
