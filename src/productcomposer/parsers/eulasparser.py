import os
from ..utils.loggerutils import note

def parse_eulas(euladir, eulas):
    note(f"Reading eula data from {euladir}")
    for dirpath, _, files in os.walk(euladir):
        for filename in files:
            if filename.startswith('.'):
                continue
            pkgname = filename.removesuffix('.en')
            eulas[pkgname] = (Path(dirpath) / filename).read_text(encoding='utf-8')
