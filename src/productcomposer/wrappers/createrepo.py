from .common import *
from .. import defaults


class CreaterepoWrapper(BaseWrapper):
    directory: str = Field()
    baseurl: str | None = Field()
    checksum_type: str = Field(default=defaults.CREATEREPO_CHECKSUM_TYPE)
    content: list[str] | None = Field()
    distro: str | None = Field()
    excludes: list[str] | None = Field()
    general_compress_type: str = Field(default=defaults.CREATEREPO_GENERAL_COMPRESS_TYPE)
    split: bool = Field(default=False)

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
            cmd.append(f"--distro={self.distro}")

        if self.excludes:
            for i in self.excludes:
                cmd.append(f"--excludes={i}")

        if self.split:
            cmd.append("--split")

        return cmd
