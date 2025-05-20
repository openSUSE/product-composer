from xml.etree import ElementTree as ET

# get the file name from repomd.xml
def find_primary(directory):
    ns = '{http://linux.duke.edu/metadata/repo}'
    tree = ET.parse(directory + '/repodata/repomd.xml')
    return directory + '/' + tree.find(f".//{ns}data[@type='primary']/{ns}location").get('href')