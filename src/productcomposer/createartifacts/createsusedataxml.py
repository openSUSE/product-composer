import os
import re
import gettext
from xml.etree import ElementTree as ET
from ..utils.repomdutils import find_primary
from ..utils.loggerutils import (die)
from ..core.Package import Package
from ..config import ET_ENCODING
from ..wrappers import ModifyrepoWrapper


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

def generate_du_data(pkg, maxdepth):
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
        kilobyte = size / 1024
        dudata.append((dir, kilobyte, dudata_count[dir]))
    return dudata

# Create the main susedata.xml with translations, support, and disk usage information
def create_susedata_xml(rpmdir, yml, supportstatus, eulas):
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
            ieula = eulas.get(name + '.' + lang, eula) if eula is not None else None
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
