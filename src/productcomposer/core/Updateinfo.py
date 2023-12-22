""" Updateinfo base class

"""
import functools

from xml.etree import ElementTree as ET

@functools.total_ordering
class Updateinfo:
    def __init__(self, location=None):
        if location is None:
            return
        self.root = ET.parse(location).getroot()
        self.location = location

    def __eq__(self, other):
        return self.location == other.location

    def __lt__(self, other):
        return self.location < other.location

# vim: sw=4 et
