import os
import re
import shutil
from ..utils.runhelper import run_helper
from ..utils.loggerutils import (die, warn, note)
from ..utils.rpmutils import (link_rpms_to_tree, unpack_meta_rpms)
from ..utils.runcreaterepo import run_createrepo
from ..createartifacts.createmediadir import create_media_dir
from ..createartifacts.createchecksumfile import create_checksums_file
from ..createartifacts.createsusedataxml import create_susedata_xml
from ..createartifacts.createappstream import create_appstream
from ..createartifacts.createupdateinfoxml import create_updateinfo_xml
from ..createartifacts.createagamaiso import create_agama_iso
from ..createartifacts.createiso import create_iso
from ..utils.report import (write_report_file)
from ..utils.repomdutils import find_primary
from ..wrappers import ModifyrepoWrapper

def create_tree(outdir, product_base_dir, yml, pool, flavor, tree_report, supporstatus, supportstatus_override, eulas, vcs=None, disturl=None):
    if not os.path.exists(outdir):
        os.mkdir(outdir)

    maindir = outdir + '/' + product_base_dir
    if not os.path.exists(maindir):
        os.mkdir(maindir)

    workdirectories = [maindir]
    debugdir = sourcedir = None

    if yml['source']:
        match yml['source']:
            case 'split':
                sourcedir = outdir + '/' + product_base_dir + '-Source'
                os.mkdir(sourcedir)
                workdirectories.append(sourcedir)
            case 'include':
                sourcedir = maindir
            case 'drop':
                pass
            case _:
                die("Bad source option, must be either 'include', 'split' or 'drop'")

    if yml['debug']:
        match yml['debug']:
            case 'split':
                debugdir = outdir + '/' + product_base_dir + '-Debug'
                os.mkdir(debugdir)
                workdirectories.append(debugdir)
            case 'include':
                debugdir = maindir
            case 'drop':
                pass
            case _:
                die("Bad debug option, must be either 'include', 'split' or 'drop'")

    for arch in yml['architectures']:
        note(f"Linking rpms for {arch}")
        link_rpms_to_tree(maindir, yml, pool, arch, flavor, tree_report, supporstatus, supportstatus_override, debugdir, sourcedir)

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
                         failmsg="get fingerprint of gpg file")
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
    if yml['repodata']:
        if yml['repodata'] != 'all':
            repodatadirectories = []
        for workdir in workdirectories:
            if sourcedir and sourcedir == workdir:
                continue
            for arch in yml['architectures']:
                if os.path.exists(workdir + f"/{arch}"):
                    repodatadirectories.append(workdir + f"/{arch}")

    note("Write report file")
    write_report_file(tree_report, maindir, maindir + '.report')
    if sourcedir and maindir != sourcedir:
        note("Write report file for source directory")
        write_report_file(tree_report, sourcedir, sourcedir + '.report')
    if debugdir and maindir != debugdir:
        note("Write report file for debug directory")
        write_report_file(tree_report, debugdir, debugdir + '.report')

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
            create_appstream(repodatadir)
            create_susedata_xml(repodatadir, yml, supporstatus, eulas)

    if yml['installcheck']:
       for arch in yml['architectures']:
           note(f"Run installcheck for {arch}")
           args = ['installcheck', arch, '--withsrc']
           subdir = ""
           if yml['repodata']:
               subdir = f"/{arch}"
           if not os.path.exists(maindir + subdir):
               warn(f"expected path is missing, no rpm files matched? ({maindir}{subdir})")
               continue
           args.append(find_primary(maindir + subdir))
           if debugdir:
               args.append(find_primary(debugdir + subdir))
           run_helper(args, fatal=('ignore_errors' not in yml['installcheck']), failmsg="run installcheck validation")

    if 'skip_updateinfos' not in yml['build_options']:
        create_updateinfo_xml(maindir, yml, pool, flavor, debugdir, sourcedir)

    # Add License File and create extra .license directory
    if yml['iso'] and yml['iso'].get('tree', None) != 'drop':
      licensefilename = '/license.tar'
      if os.path.exists(maindir + '/license-' + yml['name'] + '.tar') or os.path.exists(maindir + '/license-' + yml['name'] + '.tar.gz'):
          licensefilename = '/license-' + yml['name'] + '.tar'
      if os.path.exists(maindir + licensefilename + '.gz'):
          run_helper(['gzip', '-d', maindir + licensefilename + '.gz'],
                     failmsg="uncompress license.tar.gz")
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
        if yml['iso']:
           if workdir == maindir and yml['iso']['base']:
               agama_arch = yml['architectures'][0]
               note(f"Export main tree into agama iso file for {agama_arch}")
               create_agama_iso(outdir, yml['iso'], pool, workdir, application_id, agama_arch)
           else:
               create_iso(outdir, yml['iso'], workdir, application_id);

           # cleanup
           if yml['iso']['tree'] == 'drop':
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
    if yml['repodata'] and yml['repodata'] != 'all':
        for workdir in workdirectories:
            repodatadir = workdir + "/repodata"
            if os.path.exists(repodatadir):
                shutil.rmtree(repodatadir)
