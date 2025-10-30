import os
import re
from datetime import datetime
from xml.etree import ElementTree as ET
from ..utils.rpmutils import create_package_set
from ..utils.loggerutils import (note, warn, die)
from ..core.PkgSet import PkgSet
from ..core.Package import Package
from ..wrappers import ModifyrepoWrapper
from ..config import ET_ENCODING

# create a fake package entry from an updateinfo package spec
def create_updateinfo_package(pkgentry):
    entry = Package()
    for tag in ('name', 'epoch', 'version', 'release', 'arch'):
        setattr(entry, tag, pkgentry.get(tag))
    return entry

# Add updateinfo.xml to metadata
def create_updateinfo_xml(rpmdir, yml, pool, flavor, debugdir, sourcedir, archsubdir=None):
    if not pool.updateinfos:
        return

    missing_package = False

    # build the union of the package sets for all requested architectures

    ### This needs to be kept in sync with src/productcomposer/utils/rpmutils.py
    ### or factored out
    main_pkgset = PkgSet(None)
    for pkgset_name in yml['content']:
        for arch in yml['architectures']:
            main_pkgset.add(create_package_set(yml, arch, flavor, pkgset_name, pool=pool))

    main_pkgset_names = main_pkgset.names()
    ###

    uitemp = None

    archlist = yml['architectures']
    subarchpath = ""
    if archsubdir:
        archlist = [ archsubdir, "noarch" ]
        subarchpath = archsubdir + "/"

    updateinfo_file = os.path.join(rpmdir, subarchpath, "updateinfo.xml")

    export_updates = {}
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
            if len(yml['set_updateinfo_id_prefix']) > 0:
                # avoid double application of same prefix
                id_text = re.sub(r'^'+yml['set_updateinfo_id_prefix'], '', id_node.text)
                id_node.text = yml['set_updateinfo_id_prefix'] + id_text

            for pkgentry in parent.findall('package'):
                src = pkgentry.get('src')
                if archsubdir:
                    src = "../" + pkgentry.get('src')
                    pkgentry.set('src', src)

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
                for internal_attributes in (
                    'supportstatus',
                    'superseded_by',
                    'embargo_date',
                ):
                    pkgentry.attrib.pop(internal_attributes, None)

                # check if we have files for the entry
                if os.path.exists(rpmdir + '/' + subarchpath + src):
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
                if name in main_pkgset_names and not archsubdir:
                    updatepkg = create_updateinfo_package(pkgentry)
                    if main_pkgset.matchespkg(None, updatepkg):
                        warn(f"package {updatepkg} not found")
                        missing_package = True

                parent.remove(pkgentry)

            if not needed:
                if 'abort_on_empty_updateinfo' in yml['build_options']:
                    die(f'Stumbled over an updateinfo.xml where no rpm is used: {id_node.text}')
                continue

            update_id = update.find('id').text
            if update_id in export_updates:
                # same entry id, compare allmost all elements
                for element in update:
                    if element.tag == 'pkglist':
                        # we merged it before
                        continue
                    if element.tag == 'issued':
                        # we accept a difference here
                        continue
                    # compare element effective result only
                    if ET.tostring(element) != ET.tostring(export_updates[update_id].find(element.tag)):
                        die(f"Error: updateinfos {update_id} differ in element {element.tag}")

                if len(update) != len(export_updates[update_id]):
                    die(f"Error: updateinfos {update_id} have different amount of elements")

                # entry already exists, we need to merge it
                export_collection = export_updates[update_id].findall('pkglist')[0].findall('collection')[0]
                collection = update.findall('pkglist')[0].findall('collection')[0]
                for pkgentry in collection.findall('package'):
                    for existing_entry in export_collection.findall('package'):
                        if existing_entry.get('name') != pkgentry.get('name'):
                            continue
                        if existing_entry.get('epoch') != pkgentry.get('epoch'):
                            continue
                        if existing_entry.get('version') != pkgentry.get('version'):
                            continue
                        if existing_entry.get('release') != pkgentry.get('release'):
                            continue
                        if existing_entry.get('arch') != pkgentry.get('arch'):
                            continue
                        break # same entry exists, so break for skipping the else part
                    else:
                        # add the pkgentry to existing element
                        export_collection.append(pkgentry)
            else:
                # new entry
                export_updates[update_id] = update

    if export_updates:
        uitemp = open(updateinfo_file, 'x')
        uitemp.write("<updates>\n  ")
        for update in sorted(export_updates):
            uitemp.write(ET.tostring(export_updates[update], encoding=ET_ENCODING))
        uitemp.write("</updates>\n")
        uitemp.close()

        mr = ModifyrepoWrapper(
                file=updateinfo_file,
                directory=os.path.join(rpmdir, subarchpath, "repodata"),
                )
        mr.run_cmd()

        os.unlink(updateinfo_file)

    if missing_package and 'ignore_missing_packages' not in yml['build_options']:
        die('Abort due to missing packages for updateinfo')
