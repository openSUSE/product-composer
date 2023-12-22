""" Pool base class

"""

import os
import rpm

from .Package import Package
from .Updateinfo import Updateinfo

class Pool:
    def __init__(self):
        self.rpms = {}
        self.updateinfos = {}

    def make_rpm(self, location, rpm_ts=None):
        return Package(location, rpm_ts=rpm_ts)

    def make_updateinfo(self, location):
        return Updateinfo(location)

    def add_rpm(self, pkg, origin=None):
        if origin is not None:
            pkg.origin = origin
        name = pkg.name
        if not name in self.rpms:
            self.rpms[name] = []
        self.rpms[name].append(pkg)

    def add_updateinfo(self, uinfo):
        self.updateinfos[uinfo.location] = uinfo

    def scan(self, directory):
        ts = rpm.TransactionSet()
        ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)

        for dirpath, dirs, files in os.walk(directory):
            reldirpath = os.path.relpath(dirpath, directory)
            for filename in files:
                fname = os.path.join(dirpath, filename)
                if filename.endswith('updateinfo.xml'):
                    uinfo = self.make_updateinfo(fname)
                    self.add_updateinfo(uinfo)
                elif filename.endswith('.rpm'):
                    pkg = self.make_rpm(fname, rpm_ts=ts)
                    self.add_rpm(pkg, os.path.join(reldirpath, filename))
        
    def lookup_all_rpms(self, arch, name, op=None, epoch=None, version=None, release=None):
        if name not in self.rpms:
            return []
        return [ rpm for rpm in self.rpms[name] if rpm.matches(arch, name, op, epoch, version, release) ]

    def lookup_rpm(self, arch, name, op=None, epoch=None, version=None, release=None):
        return max(self.lookup_all_rpms(arch, name, op, epoch, version, release), default=None)

    def lookup_all_updateinfos(self):
        return self.updateinfos.values()

# vim: sw=4 et
