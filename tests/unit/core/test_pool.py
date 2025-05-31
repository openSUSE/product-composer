import pytest
from productcomposer.core.Pool import Pool

#todo: lookup_all_updateinfos not tested
# drpm files not managed
# no error if scanning wrong repo path

def test_pool_scan_ok():
        pool = Pool()
        reposdir = "./tests/assets/rpms/15.6_oss"
        pool.scan(reposdir)
        rpms = pool.lookup_all_rpms("x86_64","3omns")
        assert len(rpms) == 0
        rpms = pool.lookup_all_rpms("x86_64","patterns-base-apparmor")    
        assert len(rpms) == 1
        rpms = pool.lookup_all_rpms("s390x","patterns-base-apparmor")
        assert len(rpms) == 1
        rpms = pool.lookup_all_rpms("s390x","glow","=", None, "1.5.1", "lp156.2.3.1")
        assert len(rpms) == 1     
        rpms = pool.lookup_all_rpms("s390x","glow","=", None, "1.5.1", None)
        assert len(rpms) == 1     
        rpms = pool.lookup_all_rpms("s390x","glow","<", None, "1.5.2", None)
        assert len(rpms) == 1     
        rpms = pool.lookup_all_rpms("s390x","glow",">", None, "1.5.1", None)
        assert len(rpms) == 0 
        rpms = pool.lookup_all_rpms("x86_64","zypper")
        assert len(rpms) == 3   
        # lookup_rpm returns highest version    
        rpm = pool.lookup_rpm("x86_64","zypper")
        assert rpm.canonfilename == "zypper-1.14.89-1.1.x86_64.rpm"
        rpm = pool.lookup_rpm("x86_64","3omns")
        assert rpm == None
        rpm = pool.lookup_rpm("xZ4","3omns")
        assert rpm == None    
        pool.remove_rpms("x86_64", "zypper", "=", None, "1.14.89", "1.1")
        rpms = pool.lookup_all_rpms("x86_64","zypper")
        assert len(rpms) == 2  
        names = pool.names()
        assert "gtk3-branding-openSUSE" in names
        # noarch packages are not filted out
        names = pool.names("x86_64")
        assert "libgarcon-branding-openSUSE" in names
        assert not "perl-Mail-SPF_XS" in names
        names = pool.names("aarch64")
        assert "perl-Mail-SPF_XS" in names



