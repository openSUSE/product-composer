from .common import *
from .. import defaults


class CreaterepoWrapper(BaseWrapper):
    directory: str = Field()
    baseurl: str | None = Field(default=None)
    checksum_type: str = Field(default=defaults.CREATEREPO_CHECKSUM_TYPE)
    content: list[str] | None = Field(default=None)
    cpeid: str | None = Field(default=None)
    distro: str | None = Field(default=None)
    repos: list[str] | None = Field(default=None)
    excludes: list[str] | None = Field(default=None)
    general_compress_type: str = Field(default=defaults.CREATEREPO_GENERAL_COMPRESS_TYPE)
    split: bool = Field(default=False)
    arch_specific_repodata: str | None = Field(default=None)
    complete_arch_list: list[str] | None = Field(default=None)

    def get_cmd(self):
        cmd = ["createrepo", self.directory]

        cmd.append("--no-database")
        cmd.append("--unique-md-filenames")
        cmd.append(f"--checksum={self.checksum_type}")
        cmd.append(f"--general-compress-type={self.general_compress_type}")

        if self.baseurl:
            cmd.append(f"--baseurl={self.baseurl}")

        if self.content:
            for i in self.content:
                cmd.append(f"--content={i}")

        if self.distro:
            if self.cpeid:
                cmd.append(f"--distro={self.cpeid},{self.distro}")
            else:
                cmd.append(f"--distro={self.distro}")

        if self.excludes:
            for i in self.excludes:
                cmd.append(f"--excludes={i}")

        if self.repos:
            for i in self.repos:
                cmd.append(f"--repo={i}")

        if self.split:
            cmd.append("--split")

        if self.arch_specific_repodata:
            cmd.append("--location-prefix=../")
            cmd.append(f"--outputdir={self.arch_specific_repodata}")
            for exclude in self.complete_arch_list:
                cmd.append(f"--excludes=*.{exclude}.rpm$")

        return cmd
