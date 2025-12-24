from .Package import Package
from ..utils.loggerutils import note


class Filter:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def validate(self, package: Package):
        return NotImplementedError("Filter should implement its own validate method")

    def filter_matches(self, package: Package):
        if self.enabled:
            return self.validate(package)

        return True
