import pytest
from productcomposer.core.Updateinfo import Updateinfo

def test_updateinfo_missing_file():
    location = "./tests/assets/updateinfox.xml"
    with pytest.raises(FileNotFoundError):
        ui = Updateinfo(location)

def test_updateinfo_ok():
    location = "./tests/assets/updateinfo.xml"
    ui = Updateinfo(location)
    found = False
    for update in ui.root.findall('update'):
        update_id = update.find('id')
        if update_id is not None and update_id.text == "openSUSE-2024-153":
            found = True
    assert found