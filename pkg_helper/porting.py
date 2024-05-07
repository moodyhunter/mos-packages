
from abc import ABC, abstractmethod
from enum import Enum
import os
import random
import shutil
from time import sleep

from termcolor import colored, cprint

from pkg_helper import PACKAGES, DependencyList, Package, PackageNotFoundError, SolidPackage


class ExecutionError(Exception):
    def __init__(self, message: str):
        self.message = message


class AlternativeWorkDir:
    def __init__(self, path: str):
        self.saved = os.getcwd()
        os.chdir(path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # type: ignore
        os.chdir(self.saved)


class PortingExecutionContext:
    def __init__(self, srcpkg: SolidPackage, target_triple: str):
        self.srcpkg = srcpkg
        self.dstpkg = SolidPackage(srcpkg.basepkg, target_triple, allow_nonsupport=True)
        self._basepkg = srcpkg.basepkg
        self.source_triple = self.srcpkg.triple
        self.target_triple = self.dstpkg.triple

    @property
    def basename(self):
        return self._basepkg.basename


class BaseAction(ABC):
    def __init__(self, src: str, dst: str, file: str = ""):
        self.src = src
        self.dst = dst
        self.file = file

    def __repr__(self):
        return f"{self.__class__.__name__}({self.src!r}, {self.dst!r}, {self.file!r})"

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, BaseAction):
            return False
        return self.src == value.src and self.dst == value.dst and self.file == value.file

    def __hash__(self) -> int:
        return hash((self.src, self.dst, self.file))

    @abstractmethod
    def execute(self, ctx: PortingExecutionContext) -> bool:
        raise NotImplementedError


class MakeDirAction(BaseAction):
    def execute(self, ctx: PortingExecutionContext):
        pkgdir = ctx.dstpkg.pkgdir
        try:
            os.mkdir(pkgdir)
        except FileExistsError:
            dircontent = os.listdir(pkgdir)
            if dircontent:
                cprint(f"Directory '{pkgdir}' already exists and is not empty", "red")
                for item in dircontent:
                    print(f"  {item}")
                return False
            else:
                pass  # Directory is empty, we can continue

        return True


class CopyFileAction(BaseAction):
    def execute(self, ctx: PortingExecutionContext):
        try:
            shutil.copyfile(self.src, self.dst)
        except Exception as e:
            raise ExecutionError(f"Error copying '{self.src}' to '{self.dst}': {e}")

        return True


class PatchFileAction(BaseAction):
    def execute(self, ctx: PortingExecutionContext):
        try:
            with open(self.file, "r") as f:
                content = f.read()
            content = content.replace(self.src, self.dst)
            with open(self.file, "w") as f:
                f.write(content)
        except Exception as e:
            raise ExecutionError(f"Error patching '{self.src}' to '{self.dst}': {e}")

        return True


class RenameFileAction(BaseAction):
    def execute(self, ctx: PortingExecutionContext):
        try:
            os.rename(self.src, self.dst)
        except Exception as e:
            cprint(f"Error renaming '{self.src}' to '{self.dst}': {e}", "red")
            return False

        return True


class UpdPkgSumsAction(BaseAction):
    def execute(self, ctx: PortingExecutionContext):
        with AlternativeWorkDir(f"packages/{ctx.dstpkg.fullname}/"):
            result = os.system("updpkgsums 2>/dev/null")

        if result != 0:
            cprint(f"Error running 'updpkgsums' for '{ctx.dstpkg.fullname}': command returned {result}", "red")
            return False

        return True


class Action(Enum):
    MAKE_DIR = MakeDirAction
    COPY_FILE = CopyFileAction
    PATCH_FILE = PatchFileAction
    RENAME_FILE = RenameFileAction
    UPDPKGSUMS = UpdPkgSumsAction


class PortDriver:
    def __init__(self, source_pkg: SolidPackage, target_triple: str) -> None:
        self.actions: list[BaseAction] = []
        self.context = PortingExecutionContext(source_pkg, target_triple)
        self.add_step(Action.MAKE_DIR, "", "", self.context.dstpkg.pkgdir)

    def add_step(self, action: Action, src: str, dst: str, file: str = ""):
        self.actions.append(action.value(src, dst, file))

    def print_steps(self):
        cprint("The following actions will be taken:", "green", attrs=["bold"])

        for action in self.actions:
            self.print_single_step(action)

    def print_single_step(self, action: BaseAction):
        print(f" {self.actions.index(action) + 1:3}: {colored(action.__class__.__name__.removesuffix("Action"), "yellow", attrs=["bold"])}", end=" ")

        if action.src != "" and action.dst != "":
            print(f"{colored(action.src, "red")} -> {colored(action.dst, "green")}", end=" ")

        if action.file:
            print(f"(in {colored(action.file, "blue")})", end=" ")

        print()

    def check_package_deps(self) -> DependencyList:
        """
        Check if all dependencies of a package are available for the target triple.
        """

        def _do_check(dep: Package):
            if dep.basename not in PACKAGES:
                raise PackageNotFoundError(dep.basename)

            if PACKAGES[dep.basename].isany():
                return True  # Any package can be used for any target

            if self.context.target_triple not in PACKAGES[dep.basename].triples:
                return False

            return True

        deplist = DependencyList([], [], [])

        for dep in self.context.srcpkg.depends:
            if not _do_check(dep.basepkg):
                deplist.depends.append(dep)

        for dep in self.context.srcpkg.makedepends:
            if not _do_check(dep.basepkg):
                deplist.makedepends.append(dep)

        for dep in self.context.srcpkg.rebuild_by:
            if not _do_check(dep.basepkg):
                deplist.rebuild_by.append(dep)

        return deplist

    def execute(self):
        print()
        print("Now executing the porting steps:")

        result = True
        source_dir = self.context.srcpkg.pkgdir

        def log_success():
            cprint(f"OK  ", 'green', attrs=['bold'], end=' ', flush=True)

        def log_failure():
            cprint(f"FAIL", 'red', attrs=['bold', 'blink'], end=' ', flush=True)

        # ensure we are in the correct directory
        if not os.path.isdir(source_dir):
            raise Exception(f"Directory '{source_dir}' does not exist, sanity check failed")

        cprint("Steps:  ", 'blue', attrs=['bold'], end="")
        cprint("".join([f"{i+1:<5}" for i in range(len(self.actions))]), "green", attrs=["bold"])
        cprint("Result: ", "blue", attrs=['bold'], end="")

        for action in self.actions:
            sleep(random.uniform(0.01, 0.1))

            try:
                if action.execute(self.context):
                    log_success()
                else:
                    raise ExecutionError("Action failed for unknown reason")
            except ExecutionError as e:
                result = False
                log_failure()
                print("\n")
                cprint(f"Step #{self.actions.index(action)+1} Failed: {action}", 'red', attrs=['bold'])
                cprint(e.message, 'red', attrs=['bold'])
                break

        print()
        return result
