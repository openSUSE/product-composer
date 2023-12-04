__all__ = (
    "BaseWrapper",
    "Field",
)


import os
import subprocess
from abc import ABC
from abc import abstractmethod

from pydantic import BaseModel
from pydantic import Field


class BaseWrapper(BaseModel, validate_assignment=True, extra="forbid"):
    @abstractmethod
    def get_cmd(self) -> list[str]:
        pass

    def run_cmd(self, check=True, stdout=None, stderr=None, cwd=None, env=None) -> subprocess.CompletedProcess:
        cmd = self.get_cmd()

        if env:
            # merge partial user-specified env with os.environ and pass it to the program call
            full_env = os.environ.copy()
            full_env.update(env)
            env = full_env

        return subprocess.run(
            cmd,
            check=check,
            stdout=stdout,
            stderr=stderr,
            cwd=cwd,
            env=env,
            encoding="utf-8",
        )
