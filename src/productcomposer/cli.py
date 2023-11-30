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

local_files = {} # sorted by project/repo/arch
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
    found = False
    if flavor and 'flavors' in yml.keys():
      for f in yml['flavors']:
        if next(iter(f)) != flavor:
            continue
        found = True
        if 'architectures' in f[flavor]:
            archlist = f[flavor]['architectures']
    if flavor and not found:
        print("ERROR: Flavor not found: ", flavor)
        raise SystemExit(1)
    if archlist == None:
      archlist = [default_arch]

    return yml, archlist

def get_product_dir(yml, flavor, archlist, release):
    name = yml['name'] + "-" + str(yml['version'])
    if 'product_directory_name' in yml.keys():
        # manual override
        name = yml['product_directory_name']
    if flavor:
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


def create_tree(outdir, product_base_dir, yml, kwdfile, flavor, archlist):
    if not os.path.exists(outdir):
      os.mkdir(outdir)

    maindir = outdir + '/' + product_base_dir
    rpmdir = maindir # we may offer to set it up in sub directories

    sourcedir = debugdir = None

    if "source" in yml.keys():
      if yml['source'] == 'split':
        sourcedir = outdir + '/' + product_base_dir + '-Source'
      else:
        sourcedir = maindir
    if "debug" in yml.keys():
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

    if os.path.exists("/usr/bin/openSUSE-appstream-process"):
      args = [ "/usr/bin/openSUSE-appstream-process",
               rpmdir,
               rpmdir + "/repodata"
             ]
      popen = subprocess.Popen(args, stdout=subprocess.PIPE)
      if popen.wait():
          print("ERROR: Failed to run openSUSE-appstream-process")
          print(popen.stdout.read())
          raise SystemExit(1)
      output = popen.stdout.read()

    if os.path.exists("/usr/bin/add_product_susedata"):
      args = [ "/usr/bin/add_product_susedata",
               '-u', '-k', kwdfile, '-p', '-e', '/usr/share/doc/packages/eulas',
               '-d', rpmdir ]
      popen = subprocess.Popen(args, stdout=subprocess.PIPE)
      if popen.wait():
          print("ERROR: Failed to run add_product_susedata")
          print(popen.stdout.read())
          raise SystemExit(1)
      output = popen.stdout.read()

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
      popen = subprocess.Popen(args, stdout=subprocess.PIPE)
      if popen.wait():
          print("ERROR: Unable to add updateinfo.xml to repo meta data")
          print(popen.stdout.read())
          raise SystemExit(1)
      os.unlink(rpmdir + '/updateinfo.xml')

    # Add License File and create extra .license directory
    if os.path.exists(rpmdir + "/license.tar"):
        licensedir = rpmdir + ".license"
        if not os.path.exists(licensedir):
            os.mkdir(licensedir)
        args = [ 'tar', 'xf', rpmdir + "/license.tar", '-C', licensedir ]
        popen = subprocess.Popen(args, stdout=subprocess.PIPE)
        if popen.wait():
            print("ERROR: Failed to extract license tar ball")
            print(popen.stdout.read())
            raise SystemExit(1)
        output = popen.stdout.read()
        if not os.path.exists(licensedir + "/license.txt"):
            print("ERROR: No license.txt extracted")
            print(popen.stdout.read())
            raise SystemExit(1)
        args = [ 'modifyrepo', '--unique-md-filenames', '--checksum=sha256',
                 rpmdir + 'license.tar',
                 rpmdir + '/repodata' ]
        popen = subprocess.Popen(args, stdout=subprocess.PIPE)
        if popen.wait():
            print("ERROR: Unable to add license.tar to repo meta data")
            print(popen.stdout.read())
            raise SystemExit(1)
        output = popen.stdout.read()

        os.unlink(rpmdir + 'license.tar')

    # detached signature
    args = [ '/usr/lib/build/signdummy', '-d', rpmdir + "/repodata/repomd.xml" ]
    popen = subprocess.Popen(args, stdout=subprocess.PIPE)
    if popen.wait():
        print("ERROR: Failed to created detached signature")
        print(popen.stdout.read())
        raise SystemExit(1)
    output = popen.stdout.read()

    # detached pubkey
    args = [ '/usr/lib/build/signdummy', '-p', rpmdir + "/repodata/repomd.xml" ]
    pubkey_file = open(rpmdir + "/repodata/repomd.xml.key", 'w')
    popen = subprocess.Popen(args, stdout=pubkey_file)
    if popen.wait():
        print("ERROR: Failed to write signature public key")
        print(popen.stderr.read())
        raise SystemExit(1)
    pubkey_file.close()

    # do we need an ISO file?
    if 'iso' in yml.keys():
      application_id = re.sub(r'^.*/', '', maindir)
      args = [ '/bin/mkisofs', '-p', 'Product Composer - http://www.github.com/openSUSE/product-composer' ]
      if True: # x86_64 efi only atm
        args += [ '-r', '-pad', '-f', '-J', '-joliet-long' ]
        args += [ '-no-emul-boot', '-boot-load-size', '4', '-boot-info-table' ]
        args += [ '-hide', 'glump', '-hide-joliet', 'glump' ]
#        args += [ '-eltorito-alt-boot', '-eltorito-platform', 'efi' ]
        args += [ '-no-emul-boot' ]
        #args += [ '-sort', $sort_file ]
        #args += [ '-boot-load-size', block_size("boot/"+arch+"/loader") ]
        args += [ '-b', "boot/"+arch+"/loader/isolinux.bin"]
      if 'publisher' in yml['iso'].keys():
        args += [ '-publisher', yml['iso']['publisher'] ]
      if 'volume_id' in yml['iso'].keys():
        args += [ '-V', yml['iso']['volume_id'] ]
      args += [ '-A', application_id ]
      args += [ '-o', maindir + '.iso', maindir ]
      popen = subprocess.Popen(args, stdout=subprocess.PIPE, cwd=maindir)
      if popen.wait():
          print("ERROR: Failed to create iso file")
          print(popen.stderr.read())
          raise SystemExit(1)

    # create SBOM data
    if os.path.exists("/usr/lib/build/generate_sbom"):
      spdx_distro = "ALP"
      spdx_distro += "-" + str(yml['version'])
      args = [ "/usr/lib/build/generate_sbom",
               "--distro", spdx_distro,
               "--product", rpmdir 
             ]

      # SPDX
      sbom_file = open(rpmdir + ".spdx.json", 'w')
      popen = subprocess.Popen(args, stdout=sbom_file)
      if popen.wait():
          print("ERROR: Failed to run generate_sbom for SPDX")
          print(popen.stderr.read())
          raise SystemExit(1)
      sbom_file.close()

      # CycloneDX
      args = [ "/usr/lib/build/generate_sbom",
               "--format", 'cyclonedx',
               "--distro", spdx_distro,
               "--product", rpmdir 
             ]
      print(args)
      sbom_file = open(rpmdir + ".cdx.json", 'w')
      popen = subprocess.Popen(args, stdout=sbom_file)
      if popen.wait():
          print("ERROR: Failed to run generate_sbom for CycloneDX")
          print(popen.stderr.read())
          raise SystemExit(1)
      sbom_file.close()


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
    popen = subprocess.Popen(args, stdout=subprocess.PIPE, cwd=rpmdir)
    if popen.wait():
        print("ERROR: Failed to run createrepo")
        print(popen.stdout.read())
        raise SystemExit(1)
    output = popen.stdout.read()


def unpack_meta_rpms(rpmdir, yml, arch, flavor, medium):
    if not yml['unpack_packages']:
        return
    for package in create_package_list(yml['unpack_packages'], arch, flavor):
        if package not in local_rpms.keys():
            if 'ignore_missing_packages' in yml['build_options']:
               print("WARNING: package " + package + " not found")
               continue
            else:
               print("ERROR: package " + package + " not found")
               raise SystemExit(1)

        rpm = lookup_rpm(arch, package)

        tempdir = rpmdir + "/temp"
        os.mkdir(tempdir)
        popen = subprocess.Popen(['unrpm', '-q', rpm['filename']], stdout=subprocess.PIPE, cwd=tempdir)
        if popen.wait():
            print("ERROR: Failed to extract")
            print(popen.stdout.read())
            raise SystemExit(1)
        output = popen.stdout.read()

        skel_dir = tempdir + "/usr/lib/skelcd/CD" + str(medium)
        if os.path.exists(skel_dir):
            shutil.copytree(skel_dir, rpmdir, dirs_exist_ok=True)

        shutil.rmtree(tempdir)

def create_package_list(yml, arch, flavor):

    packages = []
    for entry in list(yml):
        if type(entry)==dict:
            if 'flavors' in entry.keys():
                if not flavor in entry['flavors']:
                    continue
            if 'architectures' in entry.keys():
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

    singleone = True
    if 'take_all_available_versions' in yml['build_options']:
        singleone = False

    missing_package = None
    for package in create_package_list(yml['packages'], arch, flavor):
        name = package
        op = version = release = None

        # Is the user requesting a specific version?
        match = re.match('([^><=]*)([><=]=?)(.*)', name.replace(' ', ''))
        if match:
            name    = match.group(1)
            op      = match.group(2)
            epoch = version = release = None
            if ':' in match.group(3):
                (epoch, version) = match.group(3).split(':')
            else:
                version = match.group(3)
            if '-' in version:
                (version, release) = match.version.split('-')

        if name not in local_rpms.keys():
            print("WARNING: package " + package + " not found")
            raise SystemExit(1)
            missing_package = True
            continue

        # We may want to put multiple candidates on the medium
        if singleone:
            rpms = [lookup_rpm(arch, name, op, epoch, version, release)]
        else:
            rpms = lookup_all_rpms(arch, name, op, epoch, version, release)

        if not rpms:
            print("WARNING: package " + package + " not found for " + arch)
            missing_package = True
            continue

        for rpm in rpms:
            rpmarchdir = rpmdir + '/' + rpm['tags']['arch']

            link_file_into_dir(rpm['filename'], rpmarchdir)

            # so we need to add also the src rpm
            match = re.match('^(.*)-([^-]*)-([^-]*)\.([^\.]*)\.rpm$', rpm['tags']['sourcerpm'])
            source_package_name    = match.group(1)
            # no chance to get a epoch from file name
            source_package_version = match.group(2)
            source_package_release = match.group(3)
            source_package_arch    = match.group(4)

            if sourcedir:
              srpm = lookup_rpm(source_package_arch, source_package_name, '=', None, source_package_version, source_package_release)
              if not srpm:
                  print("WARNING: source rpm package " + source_package_name + "-" + source_package_version + '-' + 'source_package_release' + '.' + source_package_arch + " not found")
                  print("         required by  " + rpm['tags']['name'] + "-" + rpm['tags']['version'] + "-" + rpm['tags']['release'])
                  missing_package = True
                  continue
              link_file_into_dir(srpm['filename'], sourcedir + '/' + source_package_arch)

            if debugdir:
              drpm = lookup_rpm(arch, source_package_name + "-debugsource", '=', None, source_package_version, source_package_release)
              if drpm:
                  link_file_into_dir(drpm['filename'], debugdir + '/' + drpm['tags']['arch'])

              drpm = lookup_rpm(arch, rpm['tags']['name'] + "-debuginfo", '=', None, rpm['tags']['version'], rpm['tags']['release'])
              if drpm:
                  link_file_into_dir(drpm['filename'], debugdir + '/' + drpm['tags']['arch'])

    if missing_package and not 'ignore_missing_packages' in yml['build_options']:
       print('ERROR: Abort due to missing packages')
       raise SystemExit(1)

def link_file_into_dir(filename, directory):
    if not os.path.exists(directory):
        os.mkdir(directory)
    outname = directory + '/' + re.sub('.*/', '', filename)
    if not os.path.exists(outname):
        os.link(filename, outname)


def _lookup_rpm_is_qualifing(entry, arch, name, op, epoch, version, release):
    tags = entry['tags']

    if tags['arch'] != arch:
        if arch == 'src' or arch == 'nosrc' or tags['arch'] != 'noarch':
            return False

    if op:
        # We must not hand over the release when the release is not required by the user
        # or the equal case will never be true.
        trelease = None
        if release:
            trelease = tags['release']
        cmp = rpm.labelCompare((tags['epoch'], tags['version'], trelease), (epoch, version, release))
        if cmp > 0:
            return op[0] == '>'
        if cmp < 0:
            return op[0] == '<'
        return '=' in op

    return True

def lookup_all_rpms(arch, name, op=None, epoch=None, version=None, release=None):
    if not name in local_rpms.keys():
        return None

    rpms = []
    for lrpm in local_rpms[name]:
        if not _lookup_rpm_is_qualifing(lrpm, arch, name, op, epoch, version, release):
            continue

        rpms.append(lrpm)
    return rpms

def lookup_rpm(arch, name, op=None, epoch=None, version=None, release=None):
    if not name in local_rpms.keys():
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
        if rpm.labelCompare((tags['epoch'], tags['version'], tags['release']), (candidate['tags']['epoch'], candidate['tags']['version'], candidate['tags']['release'])):
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
      if not project in local_files.keys():
        local_files[project] = {}
      if not repository in local_files[project].keys():
        local_files[project][repository] = {}
      if not arch in local_files[project][repository].keys():
        local_files[project][repository][arch] = {}
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
              rpm_object['arch'] = 'src'
              if rpm_object['nosource'] or rpm_object['nopatch']:
                  rpm_object['arch'] = 'nosrc'

          item = {}
          item['filename'] = fname
          item['tags'] = rpm_object
          local_files[project][repository][arch] = item

          if not rpm_object['name'] in local_rpms.keys():
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
