import filecmp
import json
import os
import sys
import textwrap
from enum import Enum
from hashlib import sha1
from pathlib import Path
from typing import Mapping, Optional, Tuple, Union, cast

from pexpect.popen_spawn import PopenSpawn
from plumbum import local
from prompt_toolkit.input.ansi_escape_sequences import REVERSE_ANSI_SEQUENCES
from prompt_toolkit.keys import Keys

import copier
from copier.types import OptStr, StrOrPath

# HACK https://github.com/python/mypy/issues/8520#issuecomment-772081075
if sys.version_info >= (3, 8):
    from typing import Protocol
else:
    from typing_extensions import Protocol

PROJECT_TEMPLATE = Path(__file__).parent / "demo"

DATA = {
    "py3": True,
    "make_secret": lambda: sha1(os.urandom(48)).hexdigest(),
    "myvar": "awesome",
    "what": "world",
    "project_name": "Copier",
    "version": "2.0.0",
    "description": "A library for rendering projects templates",
}

COPIER_CMD = local.get(
    # Allow debugging in VSCode
    # HACK https://github.com/microsoft/vscode-python/issues/14222
    str(Path(sys.executable).parent / "copier.cmd"),
    str(Path(sys.executable).parent / "copier"),
    # Poetry installs the executable as copier.cmd in Windows
    "copier.cmd",
    "copier",
)

# Executing copier this way allows to debug subprocesses using debugpy
# See https://github.com/microsoft/debugpy/issues/596#issuecomment-824643237
COPIER_PATH = (sys.executable, "-m", "copier")

# Helpers to use with tests designed for old copier bracket envops defaults
BRACKET_ENVOPS = {
    "autoescape": False,
    "block_end_string": "%]",
    "block_start_string": "[%",
    "comment_end_string": "#]",
    "comment_start_string": "[#",
    "keep_trailing_newline": True,
    "variable_end_string": "]]",
    "variable_start_string": "[[",
}
BRACKET_ENVOPS_JSON = json.dumps(BRACKET_ENVOPS)
SUFFIX_TMPL = ".tmpl"


class Spawn(Protocol):
    def __call__(self, cmd: Tuple[str, ...], *, timeout: Optional[int]) -> PopenSpawn:
        ...


class Keyboard(str, Enum):
    ControlH = REVERSE_ANSI_SEQUENCES[Keys.ControlH]
    ControlC = REVERSE_ANSI_SEQUENCES[Keys.ControlC]
    Enter = "\r"
    Esc = REVERSE_ANSI_SEQUENCES[Keys.Escape]

    Home = REVERSE_ANSI_SEQUENCES[Keys.Home]
    End = REVERSE_ANSI_SEQUENCES[Keys.End]

    Up = REVERSE_ANSI_SEQUENCES[Keys.Up]
    Down = REVERSE_ANSI_SEQUENCES[Keys.Down]
    Right = REVERSE_ANSI_SEQUENCES[Keys.Right]
    Left = REVERSE_ANSI_SEQUENCES[Keys.Left]

    # Equivalent keystrokes in terminals; see python-prompt-toolkit for
    # further explanations
    Alt = Esc
    Backspace = ControlH


def render(tmp_path: Path, **kwargs) -> None:
    kwargs.setdefault("quiet", True)
    copier.copy(str(PROJECT_TEMPLATE), tmp_path, data=DATA, **kwargs)


def assert_file(tmp_path: Path, *path: str) -> None:
    p1 = tmp_path.joinpath(*path)
    p2 = PROJECT_TEMPLATE.joinpath(*path)
    assert filecmp.cmp(p1, p2)


def build_file_tree(
    spec: Mapping[StrOrPath, Union[str, bytes]], dedent: bool = True
) -> None:
    """Builds a file tree based on the received spec."""
    for path, contents in spec.items():
        path = Path(path)
        binary = isinstance(contents, bytes)
        if not binary and dedent:
            contents = textwrap.dedent(cast(str, contents))
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "wb" if binary else "w"
        with path.open(mode) as fd:
            fd.write(contents)


def expect_prompt(
    tui: PopenSpawn, name: str, expected_type: str, help: OptStr = None
) -> None:
    """Check that we get a prompt in the standard form"""
    if help:
        tui.expect_exact(help)
    else:
        tui.expect_exact(name)
        if expected_type != "str":
            tui.expect_exact(f"({expected_type})")
