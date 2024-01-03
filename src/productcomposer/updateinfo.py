import os
from xml.etree import ElementTree as ET

from . import rpm


"""
Files must match the following pattern: *updateinfo*.xml
Compressed files are out of scope.

TODO: join entries into one resulting updateinfo.xml
TODO: sort the resulting updateinfo.xml
TODO: pretty-print (ET.indent() is not enough, we need to strip some spaces as well)
TODO: deduplicate records in __ior__() / __or__()
"""


class Updateinfo:
    def __init__(self, path=None):
        if path:
            self.path = os.path.abspath(path)
            self.root = ET.parse(path).getroot()
        else:
            self.path = None
            self.root = ET.Element("updates")
        self.remove_elements_without_packages = True

    def __ior__(self, other):
        self.root.extend(other.root)
        return self

    def __or__(self, other):
        result = Updateinfo()
        result |= self
        result |= other
        return result

    def __bool__(self):
        return len(self.root) > 0

    def indent(self):
        def strip_text(node):
            if node.text and not node.text.strip():
                node.text = None
            for child in node:
                strip_text(child)

        strip_text(self.root)
        ET.indent(self.root)

    def to_string(self):
        self.indent()
        return ET.tostring(self.root).decode("utf-8")

    def add_xmls(self, topdir):
        for root, dirs, files in os.walk(topdir):
            for fn in files:
                if not fn.endswith(".xml"):
                    continue
                if not "updateinfo" in fn:
                    continue
                path = os.path.join(root, fn)
                self |= Updateinfo(path)

    def filter_packages(self, nevra_list, arch_list):
        nevra_by_name_arch = {}
        for nevra in nevra_list:
            if isinstance(nevra, str):
                nevra = rpm.Nevra.from_string(nevra)
            key = (nevra.name, nevra.arch)
            nevra_by_name_arch.setdefault(key, []).append(nevra)

        matched = []
        unmatched = []

        for update in self.root.findall("update"):
            for pkglist in update.findall("pkglist"):
                for collection in pkglist.findall("collection"):
                    for package in collection.findall("package"):
                        updateinfo_nevra = rpm.Nevra.from_dict(package.attrib)

                        if updateinfo_nevra.is_debuginfo:
                            # remove debuginfo packages from updateinfo
                            collection.remove(package)
                            continue

                        if updateinfo_nevra.is_source:
                            # remove source packages from updateinfo
                            collection.remove(package)
                            continue

                        if updateinfo_nevra.arch not in arch_list:
                            # remove packages that do not match the provided arch list
                            collection.remove(package)
                            continue

                        # TODO: arch->noarch and noarch->arch transitions
                        keep = False
                        key = (updateinfo_nevra.name, updateinfo_nevra.arch)
                        nevra_list = nevra_by_name_arch.get(key, [])
                        for nevra in nevra_list:
                            # it's safe to compare, because name & arch are identical due to previous grouping and we're comparing evr only
                            if nevra >= updateinfo_nevra:
                                keep = True
                                break

                        if keep:
                            matched.append(updateinfo_nevra)
                        else:
                            # remove package that doesn't match any provided nevra from the nevra_list
                            collection.remove(package)
                            unmatched.append(updateinfo_nevra)

                    # remove <collection> that has no <package> from <pkglist>
                    if self.remove_elements_without_packages and not collection.findall("package"):
                        pkglist.remove(collection)

                # remove <pkglist> that has no <collection> from <update>
                if self.remove_elements_without_packages and not pkglist.findall("collection"):
                    update.remove(pkglist)

            # remove <update> that has no <pkglist> from <updates>
            if self.remove_elements_without_packages and not update.findall("pkglist"):
                self.root.remove(update)

        return matched, unmatched

    def sort(self):
        self.root[:] = sorted(self.root, key=lambda child: child.find("id").text)
