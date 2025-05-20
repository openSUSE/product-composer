import os
from ..utils.loggerutils import note

def parse_eulas(euladir, eulas):
    note(f"Reading eula data from {euladir}")
    for dirpath, dirs, files in os.walk(euladir):
        for filename in files:
            if filename.startswith('.'):
                continue
            pkgname = filename.removesuffix('.en')
            with open(os.path.join(dirpath, filename), encoding="utf-8") as f:
                eulas[pkgname] = f.read()
