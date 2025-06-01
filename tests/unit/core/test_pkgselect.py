import pytest
from productcomposer.core.PkgSelect import PkgSelect
from productcomposer.core.Package import Package
from productcomposer.parsers.yamlparser import parse_yaml

def test_pkgselect_matchespkg():
    location = "./tests/assets/tomls/leap16dvd.productcompose"
    yaml = parse_yaml(location, "leap_dvd5_x86_64")
    pkgs = []
    for pkgset in list(yaml['packagesets']):
        if 'packages' in pkgset and pkgset['packages']:
            for pkg in pkgset['packages']:
                pkgsel = PkgSelect(pkg)
                pkgs.append(pkgsel)
    
    location = "./tests/assets/rpms/bash-5.2.37-20.1.x86_64.rpm"
    bash_pkg = Package(location)

    cnt = 0
    for pkg in pkgs:
        if pkg.matchespkg("x86_64", bash_pkg):
            cnt+=1
    
    assert cnt == 2

def test_pkgselect_sub():
    # Versions accepted by self, but not accepted by other

    # cmp == 0 && one release not set
    pkg1 = "zypper >= 1.14.71-150600.8.1"
    pkg2 = "zypper <= 1.14.71"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    with pytest.raises(RuntimeError):
        outpkgsel = pkgsel1.sub(pkgsel2)

    # cmp == 0 && sub_ops == ''
    pkg1 = "zypper <= 1.14.71-150600.8.1"
    pkg2 = "zypper <= 1.14.71-150600.8.1"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel1.sub(pkgsel2)
    assert outpkgsel == None
    
    # cmp == 0 && sub_ops != ''
    pkg1 = "zypper >= 1.14.71-150600.8.1"
    pkg2 = "zypper <= 1.14.71-150600.8.1"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    expout =PkgSelect("zypper > 1.14.71-150600.8.1")
    outpkgsel = pkgsel1.sub(pkgsel2)
    assert outpkgsel == expout

    # cmp < 0  && '<' in other.op
    pkg1 = "zypper = 1.14.71-150600.8.1"
    pkg2 = "zypper <= 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    #pkg2 condition includes pkg1, it's like subtracting itself
    outpkgsel = pkgsel1.sub(pkgsel2)
    assert  outpkgsel == None

    # cmp < 0  && '<' not in other.op
    pkg1 = "zypper = 1.14.71-150600.8.1"
    pkg2 = "zypper >= 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel1.sub(pkgsel2)
    # intersection is empty, so pkg1 remains
    assert outpkgsel == pkgsel1

    # cmp < 0 and '>' in self.op
    # >= 8.1 except 8.2, this is not representable in RPM-style constraints
    pkg1 = "zypper >= 1.14.71-150600.8.1"
    pkg2 = "zypper = 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    with pytest.raises(RuntimeError):
        outpkgsel = pkgsel1.sub(pkgsel2)

    # cmp > 0 and '<' in self.op
    #the difference is: all versions ≤ .8.2, excluding .8.1.
    #this is not representable in RPM-style constraints
    pkg1 = "zypper = 1.14.71-150600.8.1"
    pkg2 = "zypper <= 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    with pytest.raises(RuntimeError):
        outpkgsel = pkgsel2.sub(pkgsel1)

    # cmp > 0 and '>' in other.op
    pkg1 = "zypper >= 1.14.71-150600.8.1"
    pkg2 = "zypper = 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel2.sub(pkgsel1)
    assert outpkgsel == None

    # cmp > 0 and '>' not in other.op
    pkg1 = "zypper = 1.14.71-150600.8.1"
    pkg2 = "zypper >= 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel2.sub(pkgsel1)
    assert outpkgsel == pkgsel2

def test_pkgselect_intersect():
    # cmp == 0 && one release not set
    pkg1 = "zypper >= 1.14.71-150600.8.1"
    pkg2 = "zypper <= 1.14.71"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel1.intersect(pkgsel2)
    expout = PkgSelect("zypper = 1.14.71-150600.8.1")
    assert outpkgsel == expout

    # cmp == 0 && one release not set
    pkg1 = "zypper >= 1.14.71-150600.8.1"
    pkg2 = "zypper <= 1.14.71"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel2.intersect(pkgsel1)
    expout = PkgSelect("zypper = 1.14.71-150600.8.1")
    assert outpkgsel == expout

    # cmp == 0 && subops == ''
    pkg1 = "zypper > 1.14.71-150600.8.1"
    pkg2 = "zypper < 1.14.71-150600.8.1"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel2.intersect(pkgsel1)
    assert outpkgsel == None

    # cmp == 0 && subops == '' && one release not set
    pkg1 = "zypper > 1.14.71-150600.8.1"
    pkg2 = "zypper < 1.14.71"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    with pytest.raises(RuntimeError):
        outpkgsel = pkgsel2.intersect(pkgsel1)

    # cmp < 0  && '>' in self.op && '<' not in other.op
    pkg1 = "zypper > 1.14.71-150600.8.1"
    pkg2 = "zypper >= 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel1.intersect(pkgsel2)
    assert outpkgsel == pkgsel2

    # cmp < 0  && '<' in other.op && '>' not in self.op
    pkg1 = "zypper <= 1.14.71-150600.8.1"
    pkg2 = "zypper < 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel1.intersect(pkgsel2)
    assert outpkgsel == pkgsel1    

    # cmp < 0  && '<' not in other.op && '>' not in self.op
    pkg1 = "zypper <= 1.14.71-150600.8.1"
    pkg2 = "zypper >= 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel1.intersect(pkgsel2)
    assert outpkgsel == None        

    # cmp < 0  && exception > 8.1 && < 8.2 (this is not representable in RPM-style constraints)
    pkg1 = "zypper > 1.14.71-150600.8.1"
    pkg2 = "zypper < 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    with pytest.raises(RuntimeError):
        outpkgsel = pkgsel1.intersect(pkgsel2)

    # cmp > 0 && '>' in other.op && '<' not in self.op
    pkg1 = "zypper >= 1.14.71-150600.8.1"
    pkg2 = "zypper >= 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel2.intersect(pkgsel1)
    assert outpkgsel == pkgsel2     

    # cmp > 0 && '<' in self.op && '>' not in other.op
    pkg1 = "zypper <= 1.14.71-150600.8.1"
    pkg2 = "zypper < 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel2.intersect(pkgsel1)
    assert outpkgsel == pkgsel1    

    # cmp > 0 && '<' not in self.op && '>' not in other.op
    pkg1 = "zypper < 1.14.71-150600.8.1"
    pkg2 = "zypper > 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    outpkgsel = pkgsel2.intersect(pkgsel1)
    assert outpkgsel == None    

    # cmp > 0 && exception
    pkg1 = "zypper >= 1.14.71-150600.8.1"
    pkg2 = "zypper <= 1.14.71-150600.8.2"
    pkgsel1 = PkgSelect(pkg1)
    pkgsel2 = PkgSelect(pkg2)
    with pytest.raises(RuntimeError):
        outpkgsel = pkgsel2.intersect(pkgsel1)   