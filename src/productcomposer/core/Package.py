""" Package base class

"""
import os
import re
import rpm
import functools

@functools.total_ordering
class Package:
    def __init__(self, location=None, rpm_ts=None):
        if location is None:
            return
        self.location = location
        h = self._read_rpm_header(rpm_ts=rpm_ts)
        for tag in 'name', 'epoch', 'version', 'release', 'arch', 'sourcerpm', 'buildtime', 'disturl', 'license':
            val = h[tag]
            if isinstance(val, bytes):
                val = val.decode('utf-8')
            setattr(self, tag, val)
        if not self.sourcerpm:
            self.arch = 'nosrc' if h['nosource'] or h['nopatch'] else 'src'

    def __eq__(self, other):
        return (self.name, self.evr) == (other.name, other.evr)

    def __lt__(self, other):
        if self.name == other.name:
            return rpm.labelCompare((self.epoch, self.version, self.release), (other.epoch, other.version, other.release)) == -1
        return self.name < other.name

    def __str__(self):
        return self.nevra

    @property
    def evr(self):
        if self.epoch:
            return f"{self.epoch}:{self.version}-{self.release}"
        return f"{self.version}-{self.release}"

    @property
    def nevra(self):
        return f"{self.name}-{self.evr}.{self.arch}"

    @property
    def provides(self):
        h = self._read_rpm_header()
        if h is None:
            return None
        return [ dep.DNEVR()[2:] for dep in rpm.ds(h, 'provides') ]

    def _read_rpm_header(self, rpm_ts=None):
        if self.location is None:
            return None
        if rpm_ts is None:
            rpm_ts = rpm.TransactionSet()
            rpm_ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)
        fd = os.open(self.location, os.O_RDONLY)
        h = rpm_ts.hdrFromFdno(fd)
        os.close(fd)
        return h

    @staticmethod
    def _cpeid_hexdecode(p):
        pout = ''
        while True:
            match = re.match(r'^(.*?)%([0-9a-fA-F][0-9a-fA-F])(.*)', p)
            if not match:
                return pout + p
            pout = pout + match.group(1) + chr(int(match.group(2), 16))
            p = match.group(3)

    @functools.cached_property
    def product_cpeid(self):
        cpeid_prefix = "product-cpeid() = "
        for dep in self.provides:
            if dep.startswith(cpeid_prefix):
                return Package._cpeid_hexdecode(dep[len(cpeid_prefix):])
        return None

    def matches(self, arch, name, op, epoch, version, release):
        if name is not None and self.name != name:
            return False
        if arch is not None and self.arch != arch:
            if arch == 'src' or arch == 'nosrc' or self.arch != 'noarch':
                return False
        if op:
            # special case a missing release or epoch in the match as labelCompare
            # does not handle it
            tepoch = self.epoch if epoch is not None else None
            trelease = self.release if release is not None else None
            cmp = rpm.labelCompare((tepoch, self.version, trelease), (epoch, version, release))
            if cmp > 0:
                return '>' in op
            if cmp < 0:
                return '<' in op
            return '=' in op

# vim: sw=4 et
