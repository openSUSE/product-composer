""" Package selection set

"""

from .PkgSelect import PkgSelect

class PkgSet:
    def __init__(self, name):
        self.name = name
        self.pkgs = []

    def namedict(self):
        namedict = {}
        for sel in self.pkgs:
            name = sel.name
            if name not in namedict:
                namedict[name] = []
            namedict[name].append(sel)
        return namedict

    def add_specs(self, specs):
        for spec in specs:
            sel = PkgSelect(spec)
            self.pkgs.append(sel)
    
    def add(self, other):
        s1 = set(self)
        for sel in other.pkgs:
            if sel not in s1:
                self.pkgs.append(sel)
                s1.add(sel)

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

    def matchespkg(self, arch, pkg):
        name = tags['name']
        namedict = self.namedict()
        if name not in namedict:
            return False
        for sel in namedict[name]:
            if sel.matchespkg(arch, pkg):
                return True
        return False

    def __str__(self):
        return self.name + "(" + ", ".join(str(p) for p in self.pkgs) + ")"

    def __iter__(self):
        return iter(self.pkgs)
        
# vim: sw=4 et
