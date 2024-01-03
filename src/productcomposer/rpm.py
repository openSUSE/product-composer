import abc
import functools
import os

import rpm


# TODO: document how we should deal with epoch '' and '0' - are they equal?


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


@functools.total_ordering
class NevraBase(abc.ABC):

    def __str__(self):
        return self.nevra

    def __repr__(self):
        result = super().__repr__()
        result = f"{result}({self.__str__()})"
        return result

    def __eq__(self, other):
        one = (self.name, self.epoch, self.version, self.release, self.arch)
        two = (other.name, other.epoch, other.version, other.release, other.arch)
        return one == two

    def __lt__(self, other):
        if self.name != other.name:
            return self.name < other.name
        if rpm.labelCompare((self.epoch, self.version, self.release), (other.epoch, other.version, other.release)) == -1:
            return True
        if self.arch != other.arch:
            return self.arch < other.arch
        return False

    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def epoch(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def version(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def release(self) -> str:
        pass

    @property
    @abc.abstractmethod
    def arch(self) -> str:
        pass

    @property
    def nevra(self) -> str:
        return f"{self.name}-{self.evr}.{self.arch}"

    @property
    def evr(self) -> str:
        if self.epoch:
            return f"{self.epoch}:{self.version}-{self.release}"
        return f"{self.version}-{self.release}"

    @property
    def is_debuginfo(self):
        return self.name.endswith(("-debuginfo", "-debugsource"))

    @property
    def is_source(self):
        return self.arch in ["src", "nosrc"]


class Nevra(NevraBase):
    @classmethod
    def from_string(cls, nevra):
        values = split_nevra(nevra)
        return cls(*values)

    @classmethod
    def from_dict(cls, nevra):
        keys = ["name", "epoch", "version", "release", "arch"]
        values = [nevra[i] for i in keys]
        return cls(*values)

    def __init__(self, name, epoch, version, release, arch):
        self._name = name
        self._epoch = epoch
        self._version = version
        self._release = release
        self._arch = arch

    @property
    def name(self) -> str:
        return self._name

    @property
    def epoch(self) -> str:
        return self._epoch

    @property
    def version(self) -> str:
        return self._version

    @property
    def release(self) -> str:
        return self._release

    @property
    def arch(self) -> str:
        return self._arch
