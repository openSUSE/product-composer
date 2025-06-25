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
        for tag in 'name', 'epoch', 'version', 'release', 'arch', 'sourcerpm', \
                   'buildtime', 'disturl', 'license', 'filesizes', 'filemodes', \
                   'filedevices', 'fileinodes', 'dirindexes', 'basenames', 'dirnames':
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
        if self.epoch and self.epoch != "0":
            return f"{self.epoch}:{self.version}-{self.release}"
        return f"{self.version}-{self.release}"

    @property
    def nevra(self):
        return f"{self.name}-{self.evr}.{self.arch}"

    @property
    def canonfilename(self):
        return f"{self.name}-{self.version}-{self.release}.{self.arch}.rpm"

    @property
    def provides(self):
        h = self._read_rpm_header()
        if h is None:
            return None
        return [dep.DNEVR()[2:] for dep in rpm.ds(h, 'provides')]

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

    def get_src_package(self):
        if not self.sourcerpm:
            return None
        match = re.match(r'^(.*)-([^-]*)-([^-]*)\.([^\.]*)\.rpm$', self.sourcerpm)
        if not match:
            return None
        srcpkg = Package()
        srcpkg.name = match.group(1)
        srcpkg.epoch = None             # sadly unknown
        srcpkg.version = match.group(2)
        srcpkg.release = match.group(3)
        srcpkg.arch = match.group(4)
        return srcpkg

    def matches(self, arch, name, op, epoch, version, release):
        if name is not None and self.name != name:
            return False
        if arch is not None and self.arch != arch:
            if arch in ('src', 'nosrc') or self.arch != 'noarch':
                return False
        if op is None:
            return True
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

    def get_directories(self):
        h = self._read_rpm_header()
        if h is None:
            return None
        dirs = {}
        filedevs = h['filedevices']
        fileinos= h['fileinodes']
        filesizes = h['filesizes']
        filemodes = h['filemodes']
        dirnames = h['dirnames']
        dirindexes = h['dirindexes']
        basenames = h['basenames']
        if not basenames:
            return dirs
        for basename, dirindex, filesize, filemode, filedev, fileino in zip(basenames, dirindexes, filesizes, filemodes, filedevs, fileinos):
            dirname = dirnames[dirindex]
            if isinstance(basename, bytes):
                basename = basename.decode('utf-8')
            if isinstance(dirname, bytes):
                dirname = dirname.decode('utf-8')
            if dirname != '' and not dirname.endswith('/'):
                dirname += '/'
            if dirname not in dirs:
                dirs[dirname] = []
            cookie = f"{filedev}/{fileino}"
            if (filemode & 0o170000) != 0o100000:
                filesize = 0
            dirs[dirname].append((basename, filesize, cookie))
        return dirs



# vim: sw=4 et
