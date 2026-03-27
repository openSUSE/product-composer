import pytest
from productcomposer.core.Package import Package
from unittest.mock import patch, PropertyMock

def test_package_initpackage_ok():
    with patch.object(Package, '_read_rpm_header') as mock_read_header:
        with patch.object(Package, 'provides') as mock_provides:

            mock_provides.return_value = ['/bin/bash', '/bin/bash', 'bash = 5.2.37-20.1', 'bash(x86-64) = 5.2.37-20.1']

            mock_read_header.return_value = {
                'name': b'bash',
                'epoch': None,
                'version': b'5.2.37',
                'release': b'20.1',
                'arch': b'x86_64',
                'sourcerpm': b'bash-5.2.37-20.1.src.rpm',
                'buildtime': 1745180828,
                'disturl': b'obs://build.opensuse.org/openSUSE:Factory/standard/1fb106ca40a944ee9f172e627e3ef9a7-bash',
                'license': b'GPL-3.0-or-later',
                'filesizes': [0, 891944, 7244, 4, 604, 856, 0, 0, 540, 249, 331, 322, 1841, 219, 379, 459, 247, 1578, 107, 636, 337, 1127, 1103, 988, 264, 370, 1637, 989, 473, 6, 1198, 889, 252, 659, 141, 532, 75, 946, 305, 406, 378, 354, 1865, 208, 784, 601, 1373, 620, 776, 745, 1521, 452, 129, 1405, 926, 1341, 1002, 395, 2283, 85, 646, 337, 835, 4127, 232, 632, 433, 412, 3263, 163, 433, 174, 1498, 75, 1057, 95, 2010, 560, 175, 642, 254, 2752, 1213, 236, 0, 35147, 97386, 574, 984, 166],
                'filemodes': [16877, 33261, 33133, 41471, 33184, 33184, 16877, 16877, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 41471, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 16877, 33188, 33188, 33188, 33188, 33188],
                'filedevices': [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                'fileinodes': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90],
                'dirindexes': [0, 1, 1, 1, 2, 2, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 7, 8, 8, 8, 8],
                'basenames': ['bash_completion.d', 'bash', 'bashbug', 'rbash', '.bashrc', '.profile', 'bash', 'helpfiles', 'alias', 'arith', 'arith_for', 'bg', 'bind', 'break', 'builtin', 'caller', 'case', 'cd', 'colon', 'command', 'compgen', 'complete', 'compopt', 'conditional', 'continue', 'coproc', 'declare', 'dirs', 'disown', 'dot', 'echo', 'enable', 'eval', 'exec', 'exit', 'export', 'false', 'fc', 'fg', 'fg_percent', 'for', 'function', 'getopts', 'grouping_braces', 'hash', 'help', 'history', 'if', 'jobs', 'kill', 'let', 'local', 'logout', 'mapfile', 'popd', 'printf', 'pushd', 'pwd', 'read', 'readarray', 'readonly', 'return', 'select', 'set', 'shift', 'shopt', 'source', 'suspend', 'test', 'test_bracket', 'time', 'times', 'trap', 'true', 'type', 'typeset', 'ulimit', 'umask', 'unalias', 'unset', 'until', 'variable_help', 'wait', 'while', 'bash', 'COPYING', 'bash.1.gz', 'bash_builtins.1.gz', 'bashbug.1.gz', 'rbash.1.gz'],
                'dirnames': ['/etc/', '/usr/bin/', '/usr/etc/skel/', '/usr/share/', '/usr/share/bash/', \
                             '/usr/share/bash/helpfiles/', '/usr/share/licenses/', '/usr/share/licenses/bash/', \
                             '/usr/share/man/man1/'],
                'nosource': 0,
                'nopatch': 0,
            } 
            location = "./tests/assets/rpms/bash-5.2.37-20.1.x86_64.rpm"
            pkg = Package(location)
            assert pkg.arch == "x86_64"
            assert pkg.canonfilename == "bash-5.2.37-20.1.x86_64.rpm" 
            assert pkg.evr == "5.2.37-20.1"
            assert pkg.nevra == "bash-5.2.37-20.1.x86_64"
            assert pkg.product_cpeid == None
            assert pkg.get_src_package().canonfilename == "bash-5.2.37-20.1.src.rpm"
            dirs = pkg.get_directories()
            assert "bash.1.gz" in [entry[0] for entry in dirs["/usr/share/man/man1/"]]


def test_package_initpackage_ok_with_cpe():
    with patch.object(Package, '_read_rpm_header') as mock_read_header:
        with patch.object(Package, 'provides', new_callable=PropertyMock) as mock_provides:    

            mock_provides.return_value = ['product-cpeid() = cpe%3A%2Fo%3Aopensuse%3Aopensuse%3A20250305']
            mock_read_header.return_value = {
                'name': b'openSUSE-release',
                'epoch': None,
                'version': b'20250305',
                'release': b'3407.1',
                'arch': b'x86_64',
                'sourcerpm': b'openSUSE-release-20250305-3407.1.src.rpm',
                'buildtime': 1741246789,
                'disturl': b'obs://build.opensuse.org/openSUSE:Factory/standard/01b75de07490a704e14b09e711e2d509-000release-packages:openSUSE-release',
                'license': b'BSD-3-Clause',
                'filesizes': [],
                'filemodes': [],
                'filedevices': [],
                'fileinodes': [],
                'dirindexes': [],
                'basenames': [],
                'dirnames': [],
                'nosource': 0,
                'nopatch': 0,
            }            
            location = "./tests/assets/rpms/openSUSE-release-20250305-3407.1.x86_64.rpm"
            pkg = Package(location)
            #assert "openSUSE-release = 20250305-3407.1" in pkg.provides 
            assert pkg.product_cpeid == "cpe:/o:opensuse:opensuse:20250305"

def test_package_initpackage_missing_file():
    location = "./tests/assets/rpms/dummy-2.3.x86_64.rpm"
    with pytest.raises(FileNotFoundError):
        pkg = Package(location)

def test_package_inequality_packages():
    pkg1 = None
    pkg2 = None

    with patch.object(Package, '_read_rpm_header') as mock_read_header:
        mock_read_header.return_value = {
            'name': b'bash',
            'epoch': None,
            'version': b'5.2.37',
            'release': b'20.1',
            'arch': b'x86_64',
            'sourcerpm': b'bash-5.2.37-20.1.src.rpm',
            'buildtime': 1745180828,
            'disturl': b'obs://build.opensuse.org/openSUSE:Factory/standard/1fb106ca40a944ee9f172e627e3ef9a7-bash',
            'license': b'GPL-3.0-or-later',
            'filesizes': [0, 891944, 7244, 4, 604, 856, 0, 0, 540, 249, 331, 322, 1841, 219, 379, 459, 247, 1578, 107, 636, 337, 1127, 1103, 988, 264, 370, 1637, 989, 473, 6, 1198, 889, 252, 659, 141, 532, 75, 946, 305, 406, 378, 354, 1865, 208, 784, 601, 1373, 620, 776, 745, 1521, 452, 129, 1405, 926, 1341, 1002, 395, 2283, 85, 646, 337, 835, 4127, 232, 632, 433, 412, 3263, 163, 433, 174, 1498, 75, 1057, 95, 2010, 560, 175, 642, 254, 2752, 1213, 236, 0, 35147, 97386, 574, 984, 166],
            'filemodes': [16877, 33261, 33133, 41471, 33184, 33184, 16877, 16877, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 41471, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 16877, 33188, 33188, 33188, 33188, 33188],
            'filedevices': [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'fileinodes': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90],
            'dirindexes': [0, 1, 1, 1, 2, 2, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 7, 8, 8, 8, 8],
            'basenames': ['bash_completion.d', 'bash', 'bashbug', 'rbash', '.bashrc', '.profile', 'bash', 'helpfiles', 'alias', 'arith', 'arith_for', 'bg', 'bind', 'break', 'builtin', 'caller', 'case', 'cd', 'colon', 'command', 'compgen', 'complete', 'compopt', 'conditional', 'continue', 'coproc', 'declare', 'dirs', 'disown', 'dot', 'echo', 'enable', 'eval', 'exec', 'exit', 'export', 'false', 'fc', 'fg', 'fg_percent', 'for', 'function', 'getopts', 'grouping_braces', 'hash', 'help', 'history', 'if', 'jobs', 'kill', 'let', 'local', 'logout', 'mapfile', 'popd', 'printf', 'pushd', 'pwd', 'read', 'readarray', 'readonly', 'return', 'select', 'set', 'shift', 'shopt', 'source', 'suspend', 'test', 'test_bracket', 'time', 'times', 'trap', 'true', 'type', 'typeset', 'ulimit', 'umask', 'unalias', 'unset', 'until', 'variable_help', 'wait', 'while', 'bash', 'COPYING', 'bash.1.gz', 'bash_builtins.1.gz', 'bashbug.1.gz', 'rbash.1.gz'],
            'dirnames': ['/etc/', '/usr/bin/', '/usr/etc/skel/', '/usr/share/', '/usr/share/bash/', \
                            '/usr/share/bash/helpfiles/', '/usr/share/licenses/', '/usr/share/licenses/bash/', \
                            '/usr/share/man/man1/'],
            'nosource': 0,
            'nopatch': 0,
        }   
        location = "./tests/assets/rpms/bash-5.2.37-20.1.x86_64.rpm"
        pkg1 = Package(location)

    with patch.object(Package, '_read_rpm_header') as mock_read_header:
        mock_read_header.return_value = {
            'name': b'openSUSE-release',
            'epoch': None,
            'version': b'20250305',
            'release': b'3407.1',
            'arch': b'x86_64',
            'sourcerpm': b'openSUSE-release-20250305-3407.1.src.rpm',
            'buildtime': 1741246789,
            'disturl': b'obs://build.opensuse.org/openSUSE:Factory/standard/01b75de07490a704e14b09e711e2d509-000release-packages:openSUSE-release',
            'license': b'BSD-3-Clause',
            'filesizes': [],
            'filemodes': [],
            'filedevices': [],
            'fileinodes': [],
            'dirindexes': [],
            'basenames': [],
            'dirnames': [],
            'nosource': 0,
            'nopatch': 0,
        }
        location = "./tests/assets/rpms/openSUSE-release-20250305-3407.1.x86_64.rpm"
        pkg2 = Package(location)
    assert pkg1.name == "bash"
    assert pkg2.name == "openSUSE-release"
    assert pkg1 != pkg2

def test_package_matches():
    with patch.object(Package, '_read_rpm_header') as mock_read_header:
        mock_read_header.return_value = {
            'name': b'bash',
            'epoch': None,
            'version': b'5.2.37',
            'release': b'20.1',
            'arch': b'x86_64',
            'sourcerpm': b'bash-5.2.37-20.1.src.rpm',
            'buildtime': 1745180828,
            'disturl': b'obs://build.opensuse.org/openSUSE:Factory/standard/1fb106ca40a944ee9f172e627e3ef9a7-bash',
            'license': b'GPL-3.0-or-later',
            'filesizes': [0, 891944, 7244, 4, 604, 856, 0, 0, 540, 249, 331, 322, 1841, 219, 379, 459, 247, 1578, 107, 636, 337, 1127, 1103, 988, 264, 370, 1637, 989, 473, 6, 1198, 889, 252, 659, 141, 532, 75, 946, 305, 406, 378, 354, 1865, 208, 784, 601, 1373, 620, 776, 745, 1521, 452, 129, 1405, 926, 1341, 1002, 395, 2283, 85, 646, 337, 835, 4127, 232, 632, 433, 412, 3263, 163, 433, 174, 1498, 75, 1057, 95, 2010, 560, 175, 642, 254, 2752, 1213, 236, 0, 35147, 97386, 574, 984, 166],
            'filemodes': [16877, 33261, 33133, 41471, 33184, 33184, 16877, 16877, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 41471, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 33188, 16877, 33188, 33188, 33188, 33188, 33188],
            'filedevices': [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            'fileinodes': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90],
            'dirindexes': [0, 1, 1, 1, 2, 2, 3, 4, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 6, 7, 8, 8, 8, 8],
            'basenames': ['bash_completion.d', 'bash', 'bashbug', 'rbash', '.bashrc', '.profile', 'bash', 'helpfiles', 'alias', 'arith', 'arith_for', 'bg', 'bind', 'break', 'builtin', 'caller', 'case', 'cd', 'colon', 'command', 'compgen', 'complete', 'compopt', 'conditional', 'continue', 'coproc', 'declare', 'dirs', 'disown', 'dot', 'echo', 'enable', 'eval', 'exec', 'exit', 'export', 'false', 'fc', 'fg', 'fg_percent', 'for', 'function', 'getopts', 'grouping_braces', 'hash', 'help', 'history', 'if', 'jobs', 'kill', 'let', 'local', 'logout', 'mapfile', 'popd', 'printf', 'pushd', 'pwd', 'read', 'readarray', 'readonly', 'return', 'select', 'set', 'shift', 'shopt', 'source', 'suspend', 'test', 'test_bracket', 'time', 'times', 'trap', 'true', 'type', 'typeset', 'ulimit', 'umask', 'unalias', 'unset', 'until', 'variable_help', 'wait', 'while', 'bash', 'COPYING', 'bash.1.gz', 'bash_builtins.1.gz', 'bashbug.1.gz', 'rbash.1.gz'],
            'dirnames': ['/etc/', '/usr/bin/', '/usr/etc/skel/', '/usr/share/', '/usr/share/bash/', \
                            '/usr/share/bash/helpfiles/', '/usr/share/licenses/', '/usr/share/licenses/bash/', \
                            '/usr/share/man/man1/'],
            'nosource': 0,
            'nopatch': 0,
        }     
        location = "./tests/assets/rpms/bash-5.2.37-20.1.x86_64.rpm"
        pkg = Package(location)
        assert pkg.matches("x86_64", None, None, None, None, None)
        assert not pkg.matches("aarch64", None, None, None, None, None)
        assert pkg.matches("x86_64", "bash", None, None, None, None)
        assert pkg.matches("x86_64", "bash", '=', None, "5.2.37", "20.1")
        assert pkg.matches("x86_64", "bash", ['=','>'], None, "5.2.37", "20.1")
        assert pkg.matches("x86_64", "bash", '<', None, "5.3.48", "30.1")
        assert not pkg.matches("x86_64", "bash", '>', None, "5.3.48", "30.1")


