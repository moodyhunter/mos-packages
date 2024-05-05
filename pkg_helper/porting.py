
from enum import Enum


class ActionType(Enum):
    MAKE_DIR = "Make-Package-Dir"
    COPY_FILE = "Copy-File"
    MODIFY_DEPS = "Modify-Deps"
    MODIFY_MAKEDEPS = "Modify-MakeDeps"
    MODIFY_REBUILD = "Modify-Rebuild"
    PATCH_FILE = "Patch-File"
    RENAME_FILE = "Rename-File"
    UPDPKGSUMS = "Update-PKGSUMS"


class Action:
    action: ActionType
    src: str
    dst: str

    def __init__(self, action: ActionType, src: str, dst: str, file: str = None):
        self.action = action
        self.src = src
        self.dst = dst
        self.file = file
