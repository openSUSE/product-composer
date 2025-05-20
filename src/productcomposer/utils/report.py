from xml.etree import ElementTree as ET

def add_entry_to_report(tree_report, entry, outname):
    # first one wins, see link_file_into_dir
    if outname not in tree_report:
        tree_report[outname] = entry

def write_report_file(tree_report, directory, outfile):
    root = ET.Element('report')
    if not directory.endswith('/'):
        directory += '/'
    for fn, entry in sorted(tree_report.items()):
        if not fn.startswith(directory):
            continue
        binary = ET.SubElement(root, 'binary')
        binary.text = 'obs://' + entry.origin
        for tag in (
            'name',
            'epoch',
            'version',
            'release',
            'arch',
            'buildtime',
            'disturl',
            'license',
        ):
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
