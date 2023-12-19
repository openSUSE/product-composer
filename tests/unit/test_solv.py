import pytest

import solv

from productcomposer.solv import Package
from productcomposer.solv import Pool


def add_package(pool, name, evr, arch, provides=None):
    s = pool.repo.solv_repo.add_solvable()
    s.name = name
    s.evr = evr
    s.arch = arch

    provides = provides or []
    for name, flag, evr in provides:
        rel = pool.solv_pool.rel2id(pool.solv_pool.str2id(name), pool.solv_pool.str2id(evr), flag)
        dep = solv.Dep(pool.solv_pool, rel)
        s.add_provides(dep)

    pool.repo._add_rpm_postprocess(path=None, solvable=s)


@pytest.fixture
def pool(request):
    p = Pool()

    add_package(p, "foo", "2-0", "noarch")
    add_package(p, "foo", "2-0", "src")
    add_package(p, "foo", "1-0", "noarch")
    add_package(p, "foo", "1-0", "nosrc")
    add_package(p, "bar", "1-0", "noarch")
    add_package(p, "bar", "1-0", "src")

    add_package(p, "arch-pkg", "1-0", "x86_64")
    add_package(p, "arch-pkg", "1-0", "i586")
    add_package(p, "arch-pkg", "1-0", "aarch64")
    add_package(p, "arch-pkg", "1-0", "src")

    add_package(p, "arch-pkg", "2-0", "x86_64")
    add_package(p, "arch-pkg", "2-0", "i586")
    add_package(p, "arch-pkg", "2-0", "aarch64")
    add_package(p, "arch-pkg", "2-0", "src")

    add_package(
        p, "example-release", "1-0", "x86_64",
        provides=[
            ("product-cpeid()", solv.REL_EQ, "cpe%3A/o%3Avendor%3Aproduct%3Aversion%3Aupdate"),
        ],
    )

    p.internalize()
    return p


def test_match_simple(pool):
    packages = pool.match("foo", arch="x86_64")
    assert len(packages) == 2
    assert packages[0].nevra == "foo-2-0.noarch"
    assert packages[1].nevra == "foo-1-0.noarch"


def test_match_flag(pool):
    packages = pool.match("foo > 1", arch="x86_64")
    assert len(packages) == 1
    assert packages[0].nevra == "foo-2-0.noarch"


def test_match_flag_without_spaces(pool):
    packages = pool.match("foo>1", arch="x86_64")
    assert len(packages) == 1
    assert packages[0].nevra == "foo-2-0.noarch"


def test_match_invalid_characters(pool):
    with pytest.raises(ValueError):
        packages = pool.match("/foo", arch="x86_64")


def test_match_latest(pool):
    packages = pool.match("foo", arch="x86_64", latest=True)
    assert len(packages) == 1
    assert packages[0].nevra == "foo-2-0.noarch"


def test_match_nosrc(pool):
    packages = pool.match("foo = 1-0", arch="src")
    assert len(packages) == 1
    assert packages[0].nevra == "foo-1-0.nosrc"


def test_match_src(pool):
    packages = pool.match("foo = 2-0", arch="src")
    assert len(packages) == 1
    assert packages[0].nevra == "foo-2-0.src"


def test_match_arch_pkg_latest(pool):
    packages = pool.match("arch-pkg", arch="x86_64", latest=True)
    assert len(packages) == 1
    assert packages[0].nevra == "arch-pkg-2-0.x86_64"


def test_match_arch_pkg_flag_latest(pool):
    packages = pool.match("arch-pkg < 2", arch="x86_64", latest=True)
    assert len(packages) == 1
    assert packages[0].nevra == "arch-pkg-1-0.x86_64"


def test_match_arch_pkg_flag_latest_arch_None(pool):
    packages = pool.match("arch-pkg < 2", arch=None, latest=True)
    assert len(packages) == 3
    assert packages[0].nevra == "arch-pkg-1-0.x86_64"
    assert packages[1].nevra == "arch-pkg-1-0.i586"
    assert packages[2].nevra == "arch-pkg-1-0.aarch64"


def test_match_glob(pool):
    packages = pool.match("fo*", arch="x86_64", latest=True)
    assert len(packages) == 1
    assert packages[0].nevra == "foo-2-0.noarch"


def test_product_cpeid(pool):
    packages = pool.match("*-release", arch="x86_64")
    assert len(packages) == 1
    assert packages[0].nevra == "example-release-1-0.x86_64"
    assert packages[0].product_cpeid == "cpe:/o:vendor:product:version:update"


def test_package_cmp(pool):
    p1 = pool.match("foo = 1-0", arch="x86_64")[0]
    p2 = pool.match("foo = 2-0", arch="x86_64")[0]
    assert p1 < p2
    assert p1 != p2
