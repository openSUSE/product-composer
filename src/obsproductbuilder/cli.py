""" Implementation of the command line interface.

"""
from argparse import ArgumentParser
from inspect import getfullargspec
from os import environ

from . import __version__
#from .api import parse
from .core.config import config
from .core.logger import logger

import os
import re
import rpm
import yaml
import shutil
import subprocess

__all__ = "main",

local_files = {} # sorted by project/repo/arch
local_rpms = {}  # sorted by name/version/release

def main(argv=None) -> int:
    """ Execute the application CLI.

    :param argv: argument list to parse (sys.argv by default)
    :return: exit status
    """
    #
    # Setup CLI parser
    #
    parser = ArgumentParser('obsproductbuilder', description='An example sub-command implementation')
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
        cmd_parser.add_argument('filename', default='default.obsproduct',  help='Filename of product YAML spec')

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

    kwdfile = args.filename.removesuffix('.obsproduct') + '.kwd'
    create_tree(args.out, product_base_dir, yml, kwdfile, flavor, archlist)


def verify(args):
    parse_yaml(args.filename, args.flavor)

def parse_yaml(filename, flavor, default_arch):

    with open(filename, 'r') as file:
       yml = yaml.safe_load(file)

    if yml['obsproduct_schema'] != 0:
        print(yml['obsproduct_schema'])
        print("Unsupported obsproduct_schema")
        raise SystemExit(1)
    if flavor and yml['build_options'] and 'combined_archs' in yml['build_options'].keys():
        print("WARNING: Defined flavor overwrites manual architecture setting via flavor")

    archlist = None
    found = False
    if flavor and 'flavors' in yml['build_options'].keys():
      for f in yml['build_options']['flavors']:
        if next(iter(f)) != flavor:
            continue
        found = True
        if 'combined_archs' in f.keys():
          archlist = f['combined_archs']
    if flavor and not found:
        print("Flavor not found: ", flavor)
        raise SystemExit(1)
    if archlist == None:
      archlist = [default_arch]

    return yml, archlist

def get_product_dir(yml, flavor, archlist, release):
    name = yml['name'] + "-" + str(yml['version'])
    if 'product_directory_name' in yml['build_options'].keys():
        # manual override
        name = yml['build_options']['product_directory_name']
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

    media1 = outdir + '/' + product_base_dir + '-Media1'
    rpmdir = media1 # we may offer to set it up in sub directories

    sourcedir = debugdir = None

    if "source" in yml['build_options'].keys():
      if yml['build_options']['source'] == 'split':
        sourcedir += '-Media3'
      else:
        sourcedir += '-Media1'
    if "debug" in yml['build_options'].keys():
      if yml['build_options']['debug'] == 'split':
        debugdir += '-Media2'
      else:
        debugdir += '-Media1'

    for arch in archlist:
      setup_rpms_to_install(rpmdir, yml, arch, debugdir, sourcedir)

    for arch in archlist:
      unpack_meta_rpms(rpmdir, yml, arch, medium=1) # only for first medium am

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


def unpack_meta_rpms(rpmdir, yml, arch, medium):
    for package in list(yml['unpack_packages']):
        if type(package)==dict:
            if 'only' in package.keys():
                if not arch in package['only']:
                    continue
            package_name = list(package)[0]
        else:
            package_name = package

        if package_name not in local_rpms.keys():
            print("ERROR: package " + package_name + " not found")
            raise SystemExit(1)

        print(package_name)
        rpm = lookup_rpm(arch, package_name)

        tempdir = rpmdir + "/temp"
        os.mkdir(tempdir)
        print(rpm['filename'])
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

def setup_rpms_to_install(rpmdir, yml, arch, debugdir=None, sourcedir=None):
    os.mkdir(rpmdir)
    if debugdir:
       os.mkdir(debugdir)
    if sourcedir:
       os.mkdir(sourcedir)

    for package in list(yml['packages']):
        if type(package)==dict:
            if 'only' in package.keys():
                if not arch in package['only']:
                    continue
            package_name = list(package)[0]
        else:
            package_name = package

        if package_name not in local_rpms.keys():
            print("ERROR: package " + package_name + " not found")
            raise SystemExit(1)

        rpm = lookup_rpm(arch, package_name)
        if not rpm:
            print("ERROR: package " + package_name + " not found for " + arch)
            raise SystemExit(1)
        
        _rpmdir = rpmdir + '/' + rpm['tags']['arch']

        link_file_into_dir(rpm['filename'], _rpmdir)

        # so we need to add also the src rpm
        source_package_name = re.sub('-[^-]*-[^-]*\.rpm$', '', rpm['tags']['sourcerpm'])

        if sourcedir:
          rpm = lookup_rpm('src', source_package_name)
          if not rpm:
              print("ERROR: source rpm package " + package_name + " not found")
              raise SystemExit(1)
          link_file_into_dir(rpm['filename'], sourcedir + '/' + rpm['tags']['arch'])

        if debugdir:
          rpm = lookup_rpm(arch, source_package_name + "-debugsource")
          if not rpm:
              print("ERROR: debug source rpm package " + source_package_name + "-debugsource not found")
              raise SystemExit(1)
          link_file_into_dir(rpm['filename'], debugdir + '/' + rpm['tags']['arch'])

          rpm = lookup_rpm(arch, package_name + "-debuginfo")
          if not rpm:
              print("ERROR: debug info rpm package " + package_name + "-debuginfo not found")
              raise SystemExit(1)
          link_file_into_dir(rpm['filename'], debugdir + '/' + rpm['tags']['arch'])

def link_file_into_dir(filename, directory):
    if not os.path.exists(directory):
        os.mkdir(directory)
    outname = directory + '/' + re.sub('.*/', '', filename)
    if not os.path.exists(outname):
        os.link(filename, outname)


def lookup_rpm(arch, name, version=0, release=0):
    # FIXME: ordering for best version by default
    best_version=list(local_rpms[name])[version]
    best_release=list(local_rpms[name][best_version])[release] # FIXME: order
    for rpm in local_rpms[name][best_version][best_release]:
        if rpm['tags']['arch'] == arch:
            return rpm
    return None

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
        if filename.endswith('.rpm'):
          fname = os.path.join(dirpath,filename)
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
            local_rpms[rpm_object['name']] = {}
          if not rpm_object['version'] in local_rpms[rpm_object['name']].keys():
            local_rpms[rpm_object['name']][rpm_object['version']] = {}
          if not rpm_object['release'] in local_rpms[rpm_object['name']][rpm_object['version']].keys():
            local_rpms[rpm_object['name']][rpm_object['version']][rpm_object['release']] = {}

          if not local_rpms[rpm_object['name']][rpm_object['version']][rpm_object['release']]:
             local_rpms[rpm_object['name']][rpm_object['version']][rpm_object['release']] = []
          local_rpms[rpm_object['name']][rpm_object['version']][rpm_object['release']].append(item)

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
