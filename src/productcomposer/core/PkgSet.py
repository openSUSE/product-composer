""" Package selection set

"""

from .PkgSelect import PkgSelect

class PkgSet:
    def __init__(self, name):
        self.name = name
        self.pkgs = []
        self.byname = None
        self.supportstatus = None

    def _create_byname(self):
        byname = {}
        for sel in self.pkgs:
            name = sel.name
            if name not in byname:
                byname[name] = []
            byname[name].append(sel)
        self.byname = byname

    def add_specs(self, specs):
        for spec in specs:
            sel = PkgSelect(spec, supportstatus=self.supportstatus)
            self.pkgs.append(sel)
        self.byname = None
    
    def add(self, other):
        s1 = set(self)
        for sel in other.pkgs:
            if sel not in s1:
                self.pkgs.append(sel)
                s1.add(sel)
        self.byname = None

    def sub(self, other):
        otherbyname = other.namedict()
        pkgs = []
        for sel in self.pkgs:
            name = sel.name
            if name not in otherbyname:
                pkgs.append(sel)
                continue
            for osel in otherbyname[name]:
                if sel is not None:
                    sel = sel.sub(osel)
            if sel is not None:
                pkgs.append(p)
        self.pkgs = pkgs
        self.byname = None

    def intersect(self, other):
        otherbyname = other.namedict()
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
