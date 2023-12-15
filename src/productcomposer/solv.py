import functools
import os
import re
import urllib.parse

import rpm
import solv


SOLVABLE_DISTURL = "solvable:disturl"
SOLVABLE_PRODUCT_CPEID = "solvable:product_cpeid"


def create_rpm_ts():
    ts = rpm.TransactionSet()
    ts.setKeyring(rpm.keyring())
    ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS)
    return ts


def get_rpm_hdr(path, ts=None):
    if ts is None:
        ts = create_rpm_ts()
    fd = os.open(path, os.O_RDONLY)
    hdr = ts.hdrFromFdno(fd)
    os.close(fd)
    return hdr


def split_nevr(nevr):
    epoch = ""
    name, version, release = nevr.rsplit("-", 2)
    if ":" in version:
        epoch, version = version.split(":")

    return name, epoch, version, release


def split_nevra(nevra):
    # strip path
    nevra = os.path.basename(nevra)

    # strip .rpm suffix
    if nevra.endswith(".rpm"):
        nevra = nevra[:-4]

    nevr, arch = nevra.rsplit(".", 1)
    name, epoch, version, release = split_nevr(nevr)
    return name, epoch, version, release, arch


class CmdlineRepo:
    def __init__(self, pool):
        self.pool = pool
        self.name = "@commandline"
        self.solv_repo = pool.solv_pool.add_repo(self.name)
        self.solv_repo.appdata = self
        self.solv_repodata = self.solv_repo.add_repodata(solv.Repo.REPO_REUSE_REPODATA)
        self.rpm_ts = create_rpm_ts()

    def add_rpm(self, path):
        path = os.path.abspath(path)
        solvable = self.solv_repo.add_rpm(path, solv.Repo.REPO_REUSE_REPODATA | solv.Repo.REPO_NO_INTERNALIZE)
        assert solvable
        self._add_rpm_postprocess(path, solvable)
        return solvable

    def _add_rpm_postprocess(self, path, solvable):
        # Package.disturl
        if path:
            # HACK: libsolv currently doesn't support loading rpm headers in the python bindings
            hdr = get_rpm_hdr(path, ts=self.rpm_ts)

            if hdr["disturl"] is not None:
                self.solv_repodata.set_str(solvable.id, self.pool.solv_pool.str2id(SOLVABLE_DISTURL), hdr["disturl"])

        # Package.product_cpeid
        if solvable.name.endswith("-release"):
            product_cpeid = None
            cpeid_prefix = "product-cpeid() = "
            for dep in solvable.lookup_deparray(solv.SOLVABLE_PROVIDES):
                dep_str = dep.str()
                if dep_str.startswith(cpeid_prefix):
                    product_cpeid = dep_str[len(cpeid_prefix):]
                    continue
            if product_cpeid:
                product_cpeid = urllib.parse.unquote(product_cpeid)
                self.solv_repodata.set_str(solvable.id, self.pool.solv_pool.str2id(SOLVABLE_PRODUCT_CPEID), product_cpeid)

    def add_rpms(self, topdir):
        for root, dirs, files in os.walk(topdir):
            for fn in files:
                if not fn.endswith(".rpm"):
                    continue
                path = os.path.join(root, fn)
                self.add_rpm(path)


class Pool:
    def __init__(self):
        self.solv_pool = solv.Pool()
        self.repo = CmdlineRepo(self)

    def internalize(self):
        self.repo.solv_repo.internalize()

    def match(self, pattern, arch, latest=False):
        if re.search(r"[/]", pattern) is not None:
            raise ValueError(f"Invalid package pattern: {pattern}")

        if arch == "src":
            # selects both arch and noarch packages
            selection_flag = solv.Selection.SELECTION_SOURCE_ONLY | solv.Selection.SELECTION_REL
        else:
            selection_flag = solv.Selection.SELECTION_NAME | solv.Selection.SELECTION_GLOB | solv.Selection.SELECTION_REL

        sel = self.solv_pool.matchdeps(pattern, selection_flag, solv.SOLVABLE_NAME)

        result = []
        for s in sel.solvables():
            package = Package(s)
            # for binary packages match given arch and "noarch"
            if arch and arch != "src" and package.arch not in [arch, "noarch"]:
                continue
            result.append(package)

        if latest and result:
            # return the latest package for each arch
            result_by_arch = {}
            for package in result:
                result_by_arch.setdefault(package.arch, []).append(package)
            result = [sorted(i)[-1] for i in result_by_arch.values()]

        return result


@functools.total_ordering
class Package:
    def __init__(self, solvable):
        self.solvable = solvable

    def __str__(self):
        return self.nevra

    def __repr__(self):
        result = super().__repr__()
        result = f"{result}({self.__str__()})"
        return result

    def __eq__(self, other):
        return (self.name, self.evr) == (other.name, other.evr)

    def __lt__(self, other):
        if self.name == other.name:
            return rpm.labelCompare((self.epoch, self.version, self.release), (other.epoch, other.version, other.release)) == -1
        return self.name < other.name

    @property
    def location(self):
        result = self.solvable.lookup_location()
        result = result[0]
        return result

    @property
    def name(self):
        return self.solvable.name

    @property
    def evr(self):
        return self.solvable.evr

    @property
    def nevra(self):
        return f"{self.name}-{self.evr}.{self.arch}"

    def get_parsed_evr(self):
        epoch = ""
        version, release = self.evr.split("-")
        if ":" in version:
            epoch, version = version.split(":")
        return epoch, version, release

    @property
    def epoch(self):
        return self.get_parsed_evr()[0]

    @property
    def version(self):
        return self.get_parsed_evr()[1]

    @property
    def release(self):
        return self.get_parsed_evr()[2]

    @property
    def arch(self):
        return self.solvable.arch

    @property
    def sourcerpm(self):
        return self.solvable.lookup_sourcepkg()

    @property
    def disturl(self):
        return self.solvable.lookup_str(self.solvable.pool.str2id(SOLVABLE_DISTURL))

    @property
    def license(self):
        return self.solvable.lookup_str(solv.SOLVABLE_LICENSE)

    @property
    def buildtime(self):
        return self.solvable.lookup_num(solv.SOLVABLE_BUILDTIME)

    @property
    def product_cpeid(self):
        return self.solvable.lookup_str(self.solvable.pool.str2id(SOLVABLE_PRODUCT_CPEID))

    @property
    def provides(self):
        result = []
        for dep in self.solvable.lookup_deparray(solv.SOLVABLE_PROVIDES):
            result.append(dep.str())
        return result
