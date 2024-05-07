import os
from glob import glob
from pathlib import Path
from pprint import pprint

import yaml
from termcolor import colored, cprint
from termcolor._types import Color


class UnsupportedTargetError(Exception):
    def __init__(self, package: "Package", target: str):
        self.package = package
        super().__init__(f"Package {package.basename} does not support target {target}")


class InvalidTargetError(Exception):
    def __init__(self, target: str):
        self.target = target
        super().__init__(f"Invalid target triple: {target}")


class PackageNotFoundError(Exception):
    def __init__(self, package: str):
        self.package = package
        super().__init__(f"Package {package} not found.")


class Config:
    print_full_pkgname = False


CONFIG = Config()


def sanitise_triple(target: str) -> str:
    if target and target not in ALL_TARGET_TRIPLE and target in ALL_ARCH:
        cprint(f"'{target}' is not a valid target triple, assuming '{target}-mos'", "light_blue")
        target = f"{target}-mos"

    return target


def colored_list(l, color: Color | None):
    return [colored(e, color, attrs=['bold']) for e in l] if l else ["-"]


class YamlStore:
    def __init__(self):
        self.store = {}

    def get(self, path: str):
        if path not in self.store:
            self.store[path] = yaml.safe_load(open(path))
        return self.store[path]


def extract_package_info(pkgname: str) -> tuple[str, str]:
    """Extract the target triple and package base name from a package name.

    Args:
        pkgname (str): The package name, e.g. "x86_64-mos-foo".

    Returns:
        tuple[str, str]: A tuple containing (target_triple, package_basename)
    """
    for target in ALL_TARGET_TRIPLE:
        if pkgname.startswith(target + "-"):
            return target, pkgname[len(target) + 1:]
    return "any", pkgname


def get_solid_package_by_fullname(fullname: str) -> "SolidPackage":
    triple, basename = extract_package_info(fullname)
    for pkg in PACKAGES.values():
        if pkg.basename == basename:
            if triple in pkg.triples:
                return SolidPackage(pkg, triple)
            else:
                raise UnsupportedTargetError(pkg, triple)

    raise PackageNotFoundError(fullname)


def try_find_package(hint: str, *, target: str = "") -> str | list[str]:
    # try to find the package with the exact name
    package = os.path.join("packages", hint)
    if package and os.path.isdir(package):
        return Path(package).name

    # if still not found, try globbing
    candidates = glob(f"packages/{target}*{hint}*/")
    candidates = [Path(candidate).name for candidate in candidates]
    return candidates[0] if len(candidates) == 1 else candidates


class SolidPackage:
    def __init__(self, package: "Package", target: str, *, allow_nonsupport=False):
        self.basepkg = package
        self.triple = target
        self._allow_nonsupport = allow_nonsupport
        if target not in package.triples and not allow_nonsupport:
            raise UnsupportedTargetError(package, target)

    def __repr__(self):
        return f"SolidPackage({self.basepkg.basename} for {self.triple})"

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, SolidPackage):
            return False
        return self.basepkg.basename == value.basepkg.basename and self.triple == value.triple

    def __hash__(self) -> int:
        return hash((self.basepkg.basename, self.triple))

    @property
    def pkgdir(self):
        return self.basepkg.pkgdir(self.triple, allow_nonsupport=self._allow_nonsupport)

    @property
    def basename(self):
        return self.basepkg.basename

    @property
    def fullname(self):
        return self.basepkg.target_fullname(self.triple)

    @property
    def depends(self):
        return self.basepkg.target_depends[self.triple]

    @property
    def makedepends(self):
        return self.basepkg.target_makedepends[self.triple]

    @property
    def rebuild(self):
        return self.basepkg.target_rebuild[self.triple]


class Package:
    def __init__(self, basename: str, triples: set[str]):
        if "any" in triples:
            if len(triples) > 1:
                raise InvalidTargetError(f"{", ".join(triples)}")  # if 'any' is present, it should be the only element

        self.basename: str = basename
        self.triples: set[str] = triples
        self.target_depends: dict[str, list[SolidPackage]] = {}
        self.target_makedepends: dict[str, list[SolidPackage]] = {}
        self.target_rebuild: dict[str, list[SolidPackage]] = {}

    def __repr__(self):
        return f'Package({self.basename} for {", ".join(self.triples)})'

    def _do_resolve_all_depends(self):
        for triple in self.triples:
            yaml_data = YAML_STORE.get(self.get_yaml_path(triple))

            # resolve depends
            self.target_depends[triple] = [get_solid_package_by_fullname(d) for d in yaml_data.get("repo_depends", [])]
            self.target_makedepends[triple] = [get_solid_package_by_fullname(d) for d in yaml_data.get("repo_makedepends", [])]
            self.target_rebuild[triple] = [get_solid_package_by_fullname(e.get("pkgbase")) for e in yaml_data.get("update_on_build", [])]

    def _do_check_triple(self, triple: str):
        if triple not in ALL_TARGET_TRIPLE:
            raise InvalidTargetError(triple)

        if triple not in self.triples:
            raise UnsupportedTargetError(self, triple)

    def _do_get_filepath(self, filename: str, triple: str, allow_nonsupport=False):
        if ANY_TARGET in self.triples:
            return f"packages/{self.basename}/{filename}"

        if not allow_nonsupport:
            self._do_check_triple(triple)
        return f"packages/{triple}-{self.basename}/{filename}"

    def isany(self):
        return ANY_TARGET in self.triples

    def target_fullname(self, target: str):
        if target == 'any':
            return self.basename
        return f"{target}-{self.basename}"

    def pkgdir(self, triple: str, allow_nonsupport=False):
        return self._do_get_filepath("", triple, allow_nonsupport)

    def get_yaml_path(self, triple: str, allow_nonsupport=False):
        return self._do_get_filepath("lilac.yaml", triple, allow_nonsupport)

    def get_pkgbuild_path(self, triple: str, allow_nonsupport=False):
        return self._do_get_filepath("PKGBUILD", triple, allow_nonsupport)

    def supports_target(self, triple: str):
        return triple in self.triples

    def get_friends_name(self, friend: SolidPackage, triple: str, full_name=False, pretty=True):
        if CONFIG.print_full_pkgname or full_name:
            return friend.basepkg.target_fullname(triple)

        if triple == friend.triple:
            return friend.basepkg.basename

        return friend.basepkg.basename + colored(f" ({friend.triple})", "red", attrs=["bold"])

    def get_friend_names(self, friends: list[SolidPackage], triple: str, full_name=False):
        return [self.get_friends_name(friend, triple, full_name) for friend in friends]

    def get_depends(self, triple: str) -> list[SolidPackage]:
        return self.target_depends[triple] or []

    def get_makedepends(self, triple: str) -> list[SolidPackage]:
        return self.target_makedepends[triple] or []

    def get_rebuild(self, triple: str) -> list[SolidPackage]:
        return self.target_rebuild[triple] or []

    def print_info(self, *, selected_target=None, has_deps=False, has_makedeps=False, has_rebuild=False):
        cprint(self.basename, "green", attrs=["bold"], end=" ")

        if selected_target:
            cprint(f"({selected_target})", "yellow", attrs=["bold"])
        else:
            cprint(f"({', '.join(self.triples)})", "yellow", attrs=["bold"])

        for triple in self.triples:
            if selected_target and triple != selected_target:
                continue

            deps = self.get_depends(triple) if has_deps else []
            makedeps = self.get_makedepends(triple) if has_makedeps else []
            rebuild_by = self.get_rebuild(triple) if has_rebuild else []

            if not (deps or makedeps or rebuild_by):
                continue

            deps = self.get_friend_names(deps, triple)
            makedeps = self.get_friend_names(makedeps, triple)
            rebuild_by = self.get_friend_names(rebuild_by, triple)

            # only need to print the target triple header if:
            # 1. the target is not 'any'
            # 2. the target is explicitly selected
            # 3. the package has multiple target triples
            need_target_header = triple != 'any' and selected_target is None and len(self.triples) > 1

            if need_target_header:
                cprint(f"  {triple}", "blue", attrs=["bold"])

            prefix = 4 if need_target_header else 2  # indent 4 spaces if target header is present

            if deps:
                print(f"{" " * prefix}deps: {", ".join(colored_list(deps, "light_cyan"))}")

            if makedeps:
                print(f"{" " * prefix}makedeps: {", ".join(colored_list(makedeps, "light_cyan"))}")

            if rebuild_by:
                print(f"{" " * prefix}rebuild: {", ".join(colored_list(rebuild_by, "light_cyan"))}")


ALL_ARCH = ["x86_64", "riscv64"]
ALL_TARGET_TRIPLE = [f"{arch}-mos" for arch in ALL_ARCH] + [f"{arch}-elf" for arch in ALL_ARCH] + ["any"]
ANY_TARGET = 'any'

PACKAGES: dict[str, Package] = {}

YAML_STORE = YamlStore()


def initialise():
    PACKAGES.clear()
    CONFIG.print_full_pkgname = False

    tmp_storage = {}
    for pkgname in sorted(os.listdir("packages")):
        if not os.path.isdir(f"packages/{pkgname}"):
            continue

        if not os.path.isfile(f"packages/{pkgname}/lilac.yaml") or not os.path.isfile(f"packages/{pkgname}/PKGBUILD"):
            cprint(f'missing lilac.yaml or PKGBUILD in {pkgname}, skipping', "yellow")
            continue

        triple, basename = extract_package_info(pkgname)
        tmp_storage[basename] = tmp_storage.get(basename, set()) | {triple}

    for basename, triples in tmp_storage.items():
        PACKAGES[basename] = Package(basename, triples)

    for basename in PACKAGES:
        PACKAGES[basename]._do_resolve_all_depends()
