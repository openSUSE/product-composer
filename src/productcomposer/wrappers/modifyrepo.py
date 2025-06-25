from pydantic import Field
from pydantic.types import DirectoryPath
from pydantic.types import FilePath

from .common import BaseWrapper

from .. import defaults


class ModifyrepoWrapper(BaseWrapper):
    file: FilePath = Field()
    directory: DirectoryPath = Field()
    checksum_type: str = Field(default=defaults.CREATEREPO_CHECKSUM_TYPE)
    compress: bool = Field(default=True)
    compress_type: str = Field(default=defaults.CREATEREPO_GENERAL_COMPRESS_TYPE)
    mdtype: str | None = Field(default=None)

    def get_cmd(self):
        cmd = ["modifyrepo", self.file, self.directory]

        cmd.append("--unique-md-filenames")
        cmd.append(f"--checksum={self.checksum_type}")

        if self.compress:
            cmd.append("--compress")
        else:
            cmd.append("--no-compress")

        cmd.append(f"--compress-type={self.compress_type}")

        if self.mdtype:
            cmd.append(f"--mdtype={self.mdtype}")

        return cmd
