import pytest
from unittest.mock import patch, MagicMock
from productcomposer.utils.runcreaterepo import run_createrepo
from productcomposer.wrappers.createrepo import CreaterepoWrapper


@pytest.mark.parametrize(
    'yml, expected_cpeid',
    [
        (
            {
                'product_type': 'base',
                'vendor': 'SUSE',
                'name': 'TestProduct',
                'version': '1.0',
                'cpe': 'cpe:/o:suse:testproduct:2.0:another:SuFFIX',
                'architectures': ['x86_64'],
                'repodata': None,
            },
            'cpe:/o:suse:testproduct:2.0:another:SuFFIX',
        ),
        (
            {
                'product_type': 'base',
                'vendor': 'SUSE',
                'name': 'TestProduct',
                'version': '1.0',
                'architectures': ['x86_64'],
                'repodata': None,
            },
            'cpe:/o:SUSE:TestProduct:1.0',
        ),
        (
            {
                'product_type': 'base',
                'vendor': 'SUSE',
                'name': 'TestProduct',
                'version': '1.0',
                'cpe': '',
                'architectures': ['x86_64'],
                'repodata': None,
            },
            'cpe:/o:SUSE:TestProduct:1.0',
        ),
    ],
    ids=['hardcoded_cpe', 'autogenerate_cpe', 'empty_cpe_fallback'],
)
def test_run_createrepo_cpe_logic(yml, expected_cpeid: str):
    with patch('productcomposer.utils.runcreaterepo.CreaterepoWrapper') as mock_cr_class:
        mock_cr = MagicMock(spec=CreaterepoWrapper)
        mock_cr_class.return_value = mock_cr
        assert not hasattr(mock_cr, "cpeid")
        run_createrepo('/tmp', yml)
        assert mock_cr.cpeid == expected_cpeid
