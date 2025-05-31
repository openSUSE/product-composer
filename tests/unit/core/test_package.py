import pytest
from productcomposer.core.Package import Package

def test_initpackage_ok():
    location = "./tests/assets/rpms/bash-5.2.37-20.1.x86_64.rpm"
    pkg = Package(location)
    assert pkg.arch == "x86_64"
    assert pkg.canonfilename == "bash-5.2.37-20.1.x86_64.rpm" 
    assert pkg.evr == "5.2.37-20.1"
    assert pkg.nevra == "bash-5.2.37-20.1.x86_64"
    assert pkg.product_cpeid == None
    assert "/bin/bash" in pkg.provides
    assert pkg.get_src_package().canonfilename == "bash-5.2.37-20.1.src.rpm"
    dirs = pkg.get_directories()
    assert "bash.1.gz" in [entry[0] for entry in dirs["/usr/share/man/man1/"]]


def test_initpackage_ok_with_cpe():
    location = "./tests/assets/rpms/openSUSE-release-20250305-3407.1.x86_64.rpm"
    pkg = Package(location)
    assert "openSUSE-release = 20250305-3407.1" in pkg.provides 
    assert pkg.product_cpeid == "cpe:/o:opensuse:opensuse:20250305"

def test_initpackage_missing_file():
    location = "./tests/assets/rpms/dummy-2.3.x86_64.rpm"
    with pytest.raises(FileNotFoundError):
        pkg = Package(location)

def test_inequality_packages():
    location = "./tests/assets/rpms/openSUSE-release-20250305-3407.1.x86_64.rpm"
    pkg1 = Package(location)
    location = "./tests/assets/rpms/bash-5.2.37-20.1.x86_64.rpm"
    pkg2 = Package(location)
    assert pkg1 != pkg2