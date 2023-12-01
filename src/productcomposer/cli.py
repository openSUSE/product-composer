""" Implementation of the command line interface.

"""
from argparse import ArgumentParser
from inspect import getfullargspec
from os import environ

from . import __version__
#from .api import parse
from .core.config import config
from .core.logger import logger

from xml.etree import ElementTree as ET
ET_ENCODING = "unicode"

import os
import re
import rpm
import yaml
import shutil
import subprocess
import tempfile

__all__ = "main",

local_rpms = {}  # hased via name
local_updateinfos = {}  # sorted by updateinfo_id


def main(argv=None) -> int:
    """ Execute the application CLI.

    :param argv: argument list to parse (sys.argv by default)
    :return: exit status
    """
    #
    # Setup CLI parser
    #
    parser = ArgumentParser('productcomposer', description='An example sub-command implementation')
    subparsers = parser.add_subparsers(help='sub-command help')

    # One sub parser for each command
    verify_parser = subparsers.add_parser('verify', help='The first sub-command')
    build_parser = subparsers.add_parser('build', help='The second sub-command')

    verify_parser.set_defaults(func=verify)
    build_parser.set_defaults(func=build)

    # Generic options
    for cmd_parser in [verify_parser, build_parser]:
        cmd_parser.add_argument('-f', '--flavor', default='.x86_64',  help='Build a given flavor')
        cmd_parser.add_argument('-v', '--verbose', action='store_true',  help='Enable verbose output')
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
        raise SystemExit(1)
    if not args.out:
        # No subcommand was specified.
        print("No output directory given")
        parser.print_help()
        raise SystemExit(1)

    #
    # Invoke the function
    #
    args.func(args)
    return 0
 

def build(args):
    f = args.flavor.split('.')
    flavor = None
    if f[0] != '':
        flavor = f[0]
    if len(f) == 2:
        default_arch = f[1]
    else:
        default_arch = 'x86_64'

    yml, archlist = parse_yaml(args.filename, flavor, default_arch)
    directory = os.getcwd()
    if args.filename.startswith('/'):
        directory = os.path.dirname(args.filename)
    scan_rpms(directory + "/repos", yml)

    if args.clean and os.path.exists(args.out):
        shutil.rmtree(args.out)

    product_base_dir = get_product_dir(yml, flavor, archlist, args.release)

    kwdfile = args.filename.removesuffix('.productcompose') + '.kwd'
    create_tree(args.out, product_base_dir, yml, kwdfile, flavor, archlist)


def verify(args):
    parse_yaml(args.filename, args.flavor)

def parse_yaml(filename, flavor, default_arch):

    with open(filename, 'r') as file:
        yml = yaml.safe_load(file)

    if yml['product_compose_schema'] != 0:
        print(yml['product_compose_schema'])
        print("Unsupported product composer schema")
        raise SystemExit(1)

    archlist = None
    if flavor:
        if not yml['flavors'] or flavor not in yml['flavors']:
            print("ERROR: Flavor not found: ", flavor)
            raise SystemExit(1)
        f = yml['flavors'][flavor]
        if 'architectures' in f:
            archlist = f['architectures']

    if archlist == None:
      archlist = [default_arch]

    return yml, archlist

def get_product_dir(yml, flavor, archlist, release):
    name = yml['name'] + "-" + str(yml['version'])
    if 'product_directory_name' in yml:
        # manual override
        name = yml['product_directory_name']
    if flavor and not 'hide_flavor_in_product_directory_name' in yml['build_options']:
        name += "-" + flavor
    if archlist:
        name += "-"
        name += "-".join(archlist)
    if release:
        name += "-Build" + str(release)
    if '/' in name:
        print("Illegal product name")
        raise SystemExit(1)
    return name


def run_helper(args, cwd=None, stdout=None, failmsg=None):
    if stdout is None:
        stdout=subprocess.PIPE
    popen = subprocess.Popen(args, stdout=stdout, cwd=cwd)
    if popen.wait():
        if failmsg:
            print("ERROR: Failed to " + failmsg)
        else:
            print("ERROR: Failed to run" + args[0])
        print(popen.stdout.read())
        raise SystemExit(1)
    return popen.stdout.read() if stdout == subprocess.PIPE else ''

def create_tree(outdir, product_base_dir, yml, kwdfile, flavor, archlist):
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    maindir = outdir + '/' + product_base_dir
    rpmdir = maindir # we may offer to set it up in sub directories

    sourcedir = debugdir = None

    if "source" in yml:
        if yml['source'] == 'split':
            sourcedir = outdir + '/' + product_base_dir + '-Source'
        else:
            sourcedir = maindir
    if "debug" in yml:
        if yml['debug'] == 'split':
            debugdir = outdir + '/' + product_base_dir + '-Debug'
        else:
            debugdir = maindir

    for arch in archlist:
        setup_rpms_to_install(rpmdir, yml, arch, flavor, debugdir, sourcedir)

    for arch in archlist:
        unpack_meta_rpms(rpmdir, yml, arch, flavor, medium=1) # only for first medium am

    post_createrepo(rpmdir, yml['name'])
    if debugdir:
        post_createrepo(debugdir, yml['name'], content="debug")
    if sourcedir:
        post_createrepo(sourcedir, yml['name'], content="source")

    if not os.path.exists(rpmdir + '/repodata'):
        return

    # CHANGELOG file
    if os.path.exists("/usr/bin/mk_changelog"):
        args = [ "/usr/bin/mk_changelog", rpmdir ]
        run_helper(args)

    # ARCHIVES.gz
    if os.path.exists("/usr/bin/mk_listings"):
        args = [ "/usr/bin/mk_listings", rpmdir ]
        run_helper(args)

    # repodata/appdata
    if os.path.exists("/usr/bin/openSUSE-appstream-process"):
        args = [ "/usr/bin/openSUSE-appstream-process",
                 rpmdir, rpmdir + "/repodata" ]
        run_helper(args)

    if os.path.exists("/usr/bin/add_product_susedata"):
        args = [ "/usr/bin/add_product_susedata",
                 '-u', '-k', kwdfile, '-p', '-e', '/usr/share/doc/packages/eulas',
                 '-d', rpmdir ]
        run_helper(args)

    # Adding updateinfo.xml
    uitemp = None
    for ui in local_updateinfos:
        print("Add updateinfo", ui)
        u = ET.parse(ui).getroot()
        for update in u.findall('update'):
            needed=False
            parent = update.findall('pkglist')[0].findall('collection')[0]
            for pkgentry in parent.findall('package'):
                src = pkgentry.get('src')
                if os.path.exists(rpmdir + '/' + src):
                    needed=True
                else:
                    # FIXME: special handling for debug and src rpms are needed
                    parent.remove(pkgentry)

            if needed:
                if not uitemp:
                    uitemp = open(rpmdir + '/updateinfo.xml', 'x')
                    uitemp.write("<updates>\n  ")

                uitemp.write(ET.tostring(update, encoding=ET_ENCODING))
    if uitemp:
        uitemp.write('</updates>')
        uitemp.close()
        args = [ 'modifyrepo', '--unique-md-filenames', '--checksum=sha256',
                 rpmdir + '/updateinfo.xml',
                 rpmdir + '/repodata' ]
        run_helper(args, failmsg="add updateinfo.xml to repo meta data")
        os.unlink(rpmdir + '/updateinfo.xml')

    # Add License File and create extra .license directory
    if os.path.exists(rpmdir + "/license.tar"):
        licensedir = rpmdir + ".license"
        if not os.path.exists(licensedir):
            os.mkdir(licensedir)
        args = [ 'tar', 'xf', rpmdir + "/license.tar", '-C', licensedir ]
        output = run_helper(args, failmsg="extract license tar ball")
        if not os.path.exists(licensedir + "/license.txt"):
            print("ERROR: No license.txt extracted")
            print(output)
            raise SystemExit(1)
        args = [ 'modifyrepo', '--unique-md-filenames', '--checksum=sha256',
                 rpmdir + 'license.tar',
                 rpmdir + '/repodata' ]
        run_helper(args, failmsg="add license.tar to repo meta data")
        os.unlink(rpmdir + 'license.tar')

    # detached signature
    args = [ '/usr/lib/build/signdummy', '-d', rpmdir + "/repodata/repomd.xml" ]
    run_helper(args, failmsg="create detached signature")

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

def post_createrepo(rpmdir, product_name, content=None):
    distroname="testgin"

    args = [ 'createrepo', '--unique-md-filenames', '--excludes=boot', '--checksum=sha256',
             '--no-database' ]
    if distroname:
        args.append("--distro=\""+distroname+"\"")
    if False:
        args.append("--split")
        args.append("--baseurl=media://")
    if content:
        args.append("--content=\""+content+"\"")
    if False:
        args.append("--content=pool")
    args.append('.')
    run_helper(args, cwd=rpmdir)


def unpack_meta_rpms(rpmdir, yml, arch, flavor, medium):
    if not yml['unpack_packages']:
        return

    missing_package = False
    for package in create_package_list(yml['unpack_packages'], arch, flavor):
        rpm = lookup_rpm(arch, package)
        if not rpm:
            if 'ignore_missing_packages' in yml['build_options']:
               print("WARNING: package " + package + " not found")
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
        print('ERROR: Abort due to missing packages')
        raise SystemExit(1)

def create_package_list(yml, arch, flavor):
    packages = []
    for entry in list(yml):
        if type(entry) == dict:
            if 'flavors' in entry:
                if not flavor in entry['flavors']:
                    continue
            if 'architectures' in entry:
                if not arch in entry['architectures']:
                    continue
            packages += entry['packages']
        else:
            packages.append(entry)

    return packages

def setup_rpms_to_install(rpmdir, yml, arch, flavor, debugdir=None, sourcedir=None):
    os.mkdir(rpmdir)
    if debugdir:
        os.mkdir(debugdir)
    if sourcedir:
        os.mkdir(sourcedir)

    singlemode = True
    if 'take_all_available_versions' in yml['build_options']:
        singlemode = False

    missing_package = None
    for package in create_package_list(yml['packages'], arch, flavor):
        name = package
        op = epoch = version = release = None

        # Is the user requesting a specific version?
        match = re.match('([^><=]*)([><=]=?)(.*)', name.replace(' ', ''))
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

        if name not in local_rpms:
            print("WARNING: package " + package + " not found")
            missing_package = True
            continue

        # We may want to put multiple candidates on the medium
        if singlemode:
            rpm = lookup_rpm(arch, name, op, epoch, version, release)
            rpms = [rpm] if rpm else []
        else:
            rpms = lookup_all_rpms(arch, name, op, epoch, version, release)

        if not rpms:
            print("WARNING: package " + package + " not found for " + arch)
            missing_package = True
            continue

        for rpm in rpms:
            link_entry_into_dir(rpm, rpmdir)

            match = re.match('^(.*)-([^-]*)-([^-]*)\.([^\.]*)\.rpm$', rpm['tags']['sourcerpm'])
            if not match:
                print("WARNING: rpm package " + rpm['tags']['name'] + "-" + rpm['tags']['version'] + "-" + rpm['tags']['release'] + " does not have a source rpm")
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
                    print("WARNING: source rpm package " + source_package_name + "-" + source_package_version + '-' + 'source_package_release' + '.' + source_package_arch + " not found")
                    print("         required by  " + rpm['tags']['name'] + "-" + rpm['tags']['version'] + "-" + rpm['tags']['release'])
                    missing_package = True

            if debugdir:
                drpm = lookup_rpm(arch, source_package_name + "-debugsource", '=', None, source_package_version, source_package_release)
                if drpm:
                    link_entry_into_dir(drpm, debugdir)

                drpm = lookup_rpm(arch, rpm['tags']['name'] + "-debuginfo", '=', None, rpm['tags']['version'], rpm['tags']['release'])
                if drpm:
                    link_entry_into_dir(drpm, debugdir)

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
        print('ERROR: Abort due to missing packages')
        raise SystemExit(1)

def link_file_into_dir(filename, directory):
    if not os.path.exists(directory):
        os.mkdir(directory)
    outname = directory + '/' + re.sub('.*/', '', filename)
    if not os.path.exists(outname):
        os.link(filename, outname)

def link_entry_into_dir(entry, directory):
    link_file_into_dir(entry['filename'], directory + '/' + entry['tags']['arch'])

def _lookup_rpm_is_qualifing(entry, arch, name, op, epoch, version, release):
    tags = entry['tags']

    if tags['arch'] != arch:
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

def lookup_all_rpms(arch, name, op=None, epoch=None, version=None, release=None):
    if not name in local_rpms:
        return []

    rpms = []
    for lrpm in local_rpms[name]:
        if _lookup_rpm_is_qualifing(lrpm, arch, name, op, epoch, version, release):
            rpms.append(lrpm)
    return rpms

def lookup_rpm(arch, name, op=None, epoch=None, version=None, release=None):
    if not name in local_rpms:
        return None

    candidate = None
    for lrpm in local_rpms[name]:
        if not _lookup_rpm_is_qualifing(lrpm, arch, name, op, epoch, version, release):
            continue

        # first hit?
        if candidate == None:
            candidate = lrpm
            continue
        # version compare
        tags = lrpm['tags']
        ctags = candidate['tags']
        if rpm.labelCompare((tags['epoch'], tags['version'], tags['release']), (ctags['epoch'], ctags['version'], ctags['release'])) > 0:
            candidate = lrpm

    return candidate

def scan_rpms(directory, yml):
    # This function scans all local available rpms and builds up the
    # query database
    ts = rpm.TransactionSet()
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)

    for dirpath, dirs, files in os.walk(directory):
        subdirs = dirpath.replace(directory,'').split('/')
        if len(subdirs) < 4:
            continue
        project = subdirs[-3]
        repository = subdirs[-2]
        arch = subdirs[-1]
  # we try to avoid second path config for now
  #      if not project+"/"+repository in yml['repositories']:
  #          print("Warning: local repo not listed in yml file: " + project + "/" + repository)
  #          continue
        print("scanning: " + project + "/" + repository)
        for filename in files:
            fname = os.path.join(dirpath,filename)
            if arch == 'updateinfo':
                local_updateinfos[fname] = ET.parse(fname).getroot()
                continue
            if filename.endswith('.rpm'):
              fd = os.open(fname, os.O_RDONLY)
              h = ts.hdrFromFdno(fd)
              os.close(fd)
              rpm_object = {}
              for tag in 'name', 'version', 'release', 'epoch', 'arch', 'sourcerpm', 'nosource', 'nopatch':
                  rpm_object[tag] = h[tag]

              if not rpm_object['sourcerpm']:
                  rpm_object['arch'] = 'nosrc' if rpm_object['nosource'] or rpm_object['nopatch'] else 'src'

              item = {'filename': fname, 'tags': rpm_object}

              if not rpm_object['name'] in local_rpms:
                  local_rpms[rpm_object['name']] = []
              local_rpms[rpm_object['name']].append(item)

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
