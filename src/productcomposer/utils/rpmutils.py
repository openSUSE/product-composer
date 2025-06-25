import os
import re
import shutil

from ..core.PkgSet import PkgSet
from ..utils.loggerutils import die, note, warn
from ..utils.report import add_entry_to_report
from ..utils.runhelper import run_helper


def create_package_set_all(setname, pool, arch):
    if pool is None:
        die('need a package pool to create the __all__ package set')
    pkgset = PkgSet(setname)
    pkgset.add_specs([n for n in pool.names(arch) if not (n.endswith('-debuginfo') or n.endswith('-debugsource'))])
    return pkgset

def filter_pkgsets(yml, arch, flavor):
    pkgsets_raw = {}
    for entry in list(yml['packagesets']):
        name = entry['name'] if 'name' in entry else 'main'
        if name not in pkgsets_raw:
            pkgsets_raw[name] = None    # mark as known
        if flavor and entry['flavors'] and flavor not in entry['flavors']:
            continue
        if entry['architectures'] and arch not in entry['architectures']:
            continue
        if pkgsets_raw.get(name):
            die(f'package set {name} is already defined')
        pkgsets_raw[name] = entry
    return pkgsets_raw
    
def create_package_set_cached(yml, arch, flavor, setname, pkgsetcache, pkgsets_rawcache, pool=None):
    if flavor is None:
        flavor = ''

    # process arch/flavor overwrites
    m = re.fullmatch(r'(\S+)(?:\s+architecture=(\S+))?(?:\s+flavor=(\S*))?(?:\s+architecture=(\S+))?\s*', setname)
    if m:
        setname = m[1]
        arch = m[4] or m[2] or arch
        flavor = m[3] or flavor

    if setname == '__all__':
        setkey = f"{setname}/{arch}"
        if not pkgsetcache.get(setkey):
            pkgsetcache[setkey] = create_package_set_all(setname, pool, arch)
        return pkgsetcache[setkey]

    setkey = f"{setname}/{arch}/{flavor}"
    if setkey in pkgsetcache:
        if not pkgsetcache[setkey]:
            die(f"cyclic definition of package set '{setname}'")
        return pkgsetcache[setkey]
    pkgsetcache[setkey] = None  # mark as in progress for cycle detection

    rawcachekey = f"{arch}/{flavor}"
    pkgsets_raw = pkgsets_rawcache.get(rawcachekey)
    if not pkgsets_raw:
        pkgsets_raw = filter_pkgsets(yml, arch, flavor)
        pkgsets_rawcache[rawcachekey] = pkgsets_raw

    if setname not in pkgsets_raw:
        die(f'package set {setname} does not exist')

    pkgset = PkgSet(setname)

    entry = pkgsets_raw.get(setname)
    if not entry:
        pkgsetcache[setkey] = pkgset
        return pkgset    # return empty package set if there is no matching flavor/arch

    if entry['supportstatus']:
        pkgset.supportstatus = entry['supportstatus']
        if pkgset.supportstatus.startswith('='):
            pkgset.override_supportstatus = True
            pkgset.supportstatus = pkgset.supportstatus[1:]
    if entry['packages']:
        pkgset.add_specs(entry['packages'])
    for setop in 'add', 'sub', 'intersect':
        if entry.get(setop) is None:
            continue
        for oname in entry[setop]:
            opkgset = create_package_set_cached(yml, arch, flavor, oname, pkgsetcache, pkgsets_rawcache, pool=pool)
            match setop:
                case 'add':
                    pkgset.add(opkgset)
                case 'sub':
                    pkgset.sub(opkgset)
                case 'intersect':
                    pkgset.intersect(opkgset)
                case _:
                    die(f"unsupported package set operation '{setop}'")
    pkgsetcache[setkey] = pkgset
    return pkgset

def create_package_set(yml, arch, flavor, setname, pool=None):
    return create_package_set_cached(yml, arch, flavor, setname, {}, {}, pool=pool)


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


def link_entry_into_dir(tree_report, entry, directory, add_slsa=False):
    canonfilename = entry.canonfilename
    outname = directory + '/' + entry.arch + '/' + canonfilename
    if not os.path.exists(outname):
        link_file_into_dir(entry.location, directory + '/' + entry.arch, name=canonfilename)
        add_entry_to_report(tree_report, entry, outname)
        if add_slsa:
            slsalocation = entry.location.removesuffix('.rpm') + '.slsa_provenance.json'
            if os.path.exists(slsalocation):
                slsaname = canonfilename.removesuffix('.rpm') + '.slsa_provenance.json'
                link_file_into_dir(slsalocation, directory + '/' + entry.arch, name=slsaname)

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

    if missing_package and 'ignore_missing_packages' not in yml['build_options']:
        die('Abort due to missing meta packages')

def link_rpms_to_tree(rpmdir, yml, pool, arch, flavor, tree_report, supportstatus, supportstatus_override, debugdir=None, sourcedir=None):
    singlemode = True
    if 'take_all_available_versions' in yml['build_options']:
        singlemode = False
    add_slsa = False
    if 'add_slsa_provenance' in yml['build_options']:
        add_slsa = True

    referenced_update_rpms = None
    if 'updateinfo_packages_only' in yml['build_options']:
        if not pool.updateinfos:
            warn("filtering for updates enabled, but no updateinfo found")
        if singlemode:
            die("filtering for updates enabled, but take_all_available_versions is not set")

        referenced_update_rpms = {}
        for u in sorted(pool.lookup_all_updateinfos()):
            for update in u.root.findall('update'):
                parent = update.findall('pkglist')[0].findall('collection')[0]
                for pkgentry in parent.findall('package'):
                    referenced_update_rpms[pkgentry.get('src')] = 1

    ### This needs to be kept in sync with src/productcomposer/createartifacts/createupdateinfoxml.py
    ### or factored out
    main_pkgset = PkgSet(None)
    for pkgset_name in yml['content']:
       main_pkgset.add(create_package_set(yml, arch, flavor, pkgset_name, pool=pool))
    ###

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

            link_entry_into_dir(tree_report, rpm, rpmdir, add_slsa=add_slsa)
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
                    link_entry_into_dir(tree_report, srpm, sourcedir, add_slsa=add_slsa)
                else:
                    warn(f"source rpm package {srcrpm} not found", details=f"         required by  {rpm}")
                    missing_package = True

            if debugdir:
                drpm = pool.lookup_rpm(arch, srcrpm.name + "-debugsource", '=', None, srcrpm.version, srcrpm.release)
                if drpm:
                    link_entry_into_dir(tree_report, drpm, debugdir, add_slsa=add_slsa)

                drpm = pool.lookup_rpm(arch, rpm.name + "-debuginfo", '=', rpm.epoch, rpm.version, rpm.release)
                if drpm:
                    link_entry_into_dir(tree_report, drpm, debugdir, add_slsa=add_slsa)

    if missing_package and 'ignore_missing_packages' not in yml['build_options']:
        die('Abort due to missing packages')
