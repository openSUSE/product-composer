import importlib
import pkgutil
import sys

COMMANDS = {}

def register(name):
    def decorator(cls):
        COMMANDS[name] = cls
        return cls
    return decorator

def _load_all_commands():
    package = sys.modules[__name__]
    for _, module_name, _ in pkgutil.iter_modules(package.__path__):
        importlib.import_module(f"{__name__}.{module_name}")

_load_all_commands()