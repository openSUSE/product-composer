""" Package selection set

"""

from .PkgSelect import PkgSelect


class PkgSet:
    def __init__(self, name):
        self.name = name
        self.pkgs = []
        self.byname = None
        self.supportstatus = None
        self.override_supportstatus = False
        self.ignore_binaries_newer_than = None

    def _create_byname(self):
        byname = {}
        for sel in self.pkgs:
            name = sel.name
            if name not in byname:
                byname[name] = []
            byname[name].append(sel)
        self.byname = byname

    def _byname(self):
        if self.byname is None:
            self._create_byname()
        return self.byname

    def add_specs(self, specs):
        for spec in specs:
            sel = PkgSelect(spec, supportstatus=self.supportstatus, ignore_binaries_newer_than=self.ignore_binaries_newer_than)
            self.pkgs.append(sel)
        self.byname = None

    def add(self, other):
        s1 = set(self)
        for sel in other.pkgs:
            if sel not in s1:
                if self.override_supportstatus or (self.supportstatus is not None and sel.supportstatus is None):
                    sel = sel.copy()
                    sel.supportstatus = self.supportstatus
                self.pkgs.append(sel)
                s1.add(sel)
        self.byname = None

    def sub(self, other):
        otherbyname = other._byname()
        pkgs = []
        for sel in self.pkgs:
            name = sel.name
            if name not in otherbyname:
                pkgs.append(sel)
                continue
            for other_sel in otherbyname[name]:
                if sel is not None:
                    sel = sel.sub(other_sel)
            if sel is not None:
                pkgs.append(sel)
        self.pkgs = pkgs
        self.byname = None

    def intersect(self, other):
        otherbyname = other._byname()
        pkgs = []
        s1 = set()
        pkgs = []
        for sel in self.pkgs:
            name = sel.name
            if name not in otherbyname:
                continue
            for osel in otherbyname[name]:
                isel = sel.intersect(osel)
                if isel and isel not in s1:
                    pkgs.append(isel)
                    s1.add(isel)
        self.pkgs = pkgs
        self.byname = None

    def matchespkg(self, arch, pkg):
        if self.byname is None:
            self._create_byname()
        if pkg.name not in self.byname:
            return False
        for sel in self.byname[pkg.name]:
            if sel.matchespkg(arch, pkg):
                return True
        return False

    def names(self):
        if self.byname is None:
            self._create_byname()
        return set(self.byname.keys())

    def __str__(self):
        return self.name + "(" + ", ".join(str(p) for p in self.pkgs) + ")"

    def __iter__(self):
        return iter(self.pkgs)

# vim: sw=4 et
