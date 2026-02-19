""" Package selector specification

"""

import re
import rpm


class PkgSelect:
    def __init__(self, spec, supportstatus=None, ignore_binaries_newer_than=None):
        self.supportstatus = supportstatus
        self.ignore_binaries_newer_than = ignore_binaries_newer_than
        match = re.match(r'([^><=]*)([><=]=?)(.*)', spec.replace(' ', ''))
        if match:
            self.name = match.group(1)
            self.op = match.group(2)
            epoch = '0'
            version = match.group(3)
            release = None
            if ':' in version:
                (epoch, version) = version.split(':', 2)
            if '-' in version:
                (version, release) = version.rsplit('-', 2)
            self.epoch = epoch
            self.version = version
            self.release = release
        else:
            self.name = spec
            self.op = None
            self.epoch = None
            self.version = None
            self.release = None

    def matchespkg(self, arch, pkg):
        return pkg.matches(arch, self.name, self.op, self.epoch, self.version, self.release, ignore_binaries_newer_than=self.ignore_binaries_newer_than)

    @staticmethod
    def _sub_ops(op1, op2):
        if '>' in op2:
            op1 = re.sub(r'>', '', op1)
        if '<' in op2:
            op1 = re.sub(r'<', '', op1)
        if '=' in op2:
            op1 = re.sub(r'=', '', op1)
        return op1

    @staticmethod
    def _intersect_ops(op1, op2):
        outop = ''
        if '<' in op1 and '<' in op2:
            outop = outop + '<'
        if '>' in op1 and '>' in op2:
            outop = outop + '>'
        if '=' in op1 and '=' in op2:
            outop = outop + '='
        return outop

    def _cmp_evr(self, other):
        release1 = self.release if self.release is not None else other.release
        release2 = other.release if other.release is not None else self.release
        return rpm.labelCompare((self.epoch, self.version, release1), (other.epoch, other.version, release2))

    def _throw_unsupported_sub(self, other):
        raise RuntimeError(f"unsupported sub operation: {self}, {other}")

    def _throw_unsupported_intersect(self, other):
        raise RuntimeError(f"unsupported intersect operation: {self}, {other}")

    def sub(self, other):
        if self.name != other.name:
            return self
        if other.op is None:
            return None
        if self.op is None:
            out = self.copy()
            out.op = PkgSelect._sub_ops('<=>', other.op)
            return out
        cmp = self._cmp_evr(other)
        if cmp == 0:
            if (self.release is not None and other.release is None) or (other.release is not None and self.release is None):
                self._throw_unsupported_sub(other)
            out = self.copy()
            out.op = PkgSelect._sub_ops(self.op, other.op)
            return out if out.op != '' else None
        elif cmp < 0:
            if '>' in self.op:
                self._throw_unsupported_sub(other)
            return None if '<' in other.op else self
        elif cmp > 0:
            if '<' in self.op:
                self._throw_unsupported_sub(other)
            return None if '>' in other.op else self
        self._throw_unsupported_sub(other)

    def intersect(self, other):
        if self.name != other.name:
            return None
        if other.op is None:
            return self
        if self.op is None:
            return other
        cmp = self._cmp_evr(other)
        if cmp == 0:
            if self.release is not None or other.release is None:
                out = self.copy()
            else:
                out = other.copy()
            out.op = PkgSelect._intersect_ops(self.op, other.op)
            if out.op == '':
                if (self.release is not None and other.release is None) or (other.release is not None and self.release is None):
                    self._throw_unsupported_intersect(other)
                return None
            return out
        elif cmp < 0:
            if '>' in self.op and '<' not in other.op:
                return other
            if '<' in other.op and '>' not in self.op:
                return self
            if '<' not in other.op and '>' not in self.op:
                return None
        elif cmp > 0:
            if '>' in other.op and '<' not in self.op:
                return self
            if '<' in self.op and '>' not in other.op:
                return other
            if '<' not in self.op and '>' not in other.op:
                return None
        self._throw_unsupported_intersect(other)

    def copy(self):
        out = PkgSelect(self.name)
        out.op = self.op
        out.epoch = self.epoch
        out.version = self.version
        out.release = self.release
        out.supportstatus = self.supportstatus
        out.ignore_binaries_newer_than = self.ignore_binaries_newer_than
        return out

    def __str__(self):
        if self.op is None:
            return self.name
        evr = self.version
        if self.release is not None:
            evr = evr + '-' + self.release
        if self.epoch and self.epoch != '0':
            evr = self.epoch + ':' + evr
        return self.name + ' ' + self.op + ' ' + evr

    def __hash__(self):
        if self.op:
            return hash((self.name, self.op, self.epoch, self.version, self.release, self.ignore_binaries_newer_than))
        return hash((self.name, self.ignore_binaries_newer_than))

    def __eq__(self, other):
        if self.name != other.name:
            return False
        return str(self) == str(other)

# vim: sw=4 et
