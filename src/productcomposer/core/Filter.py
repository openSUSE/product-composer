import datetime

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


class DateFilter(Filter):
    def __init__(self, filter_datetime: datetime.datetime, **kwargs):
        super().__init__(**kwargs)
        self._filter_datetime = filter_datetime

        # We can cache the timestamp and its string representation, as
        # those are static.
        self._timestamp = self._filter_datetime.timestamp()
        self._time_str = self._filter_datetime.strftime("%Y-%m-%d %H:%M:%S")

    def validate(self, package: Package):
        if not hasattr(package, "buildtime"):
            return True

        result = package.buildtime <= self._timestamp
        if not result:
            note(
                f"DateFilter: skipping package {package.name} {package.evr} due to buildtime over {self._time_str}"
            )

        return result

    @classmethod
    def from_date_str(cls, date_str: str, **kwargs):
        # YYYY-MM-DD for now, would be nice being more flexible
        return cls(datetime.datetime.strptime(date_str, "%Y-%m-%d"), **kwargs)
