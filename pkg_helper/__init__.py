import os
from typing import Any

import yaml
from termcolor import colored, cprint
from termcolor._types import Color


class UnsupportedTargetError(Exception):
    def __init__(self, package: "Package", target: str):
        self.package = package
        super().__init__(f"Package '{package.basename}' does not support target '{target}'")


class InvalidTargetError(Exception):
    def __init__(self, target: str):
        self.target = target
        super().__init__(f"Invalid target triple: {target}")


class PackageNotFoundError(Exception):
    def __init__(self, package: str):
        self.package = package
        super().__init__(f"Package {package} not found.")


def sanitise_triple(target: str) -> str:
    if target and target not in ALL_TARGET_TRIPLE and target in ALL_ARCH:
        cprint(f"'{target}' is not a valid target triple, assuming '{target}-mos'", "light_blue")
        target = f"{target}-mos"

    return target


def colored_list(l: list[str], color: Color | None):
    return [colored(e, color, attrs=['bold']) for e in l]


class YamlStore:
    def __init__(self):
        self.store: dict[str, dict[str, Any]] = {}

    def get(self, path: str) -> dict[str, Any]:
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


class DependencyList:
    def __init__(self, depends: list["SolidPackage"], makedepends: list["SolidPackage"], rebuild: list["SolidPackage"]):
        self.depends = depends
        self.makedepends = makedepends
        self.rebuild_by = rebuild

    def is_empty(self):
        return not self.depends and not self.makedepends and not self.rebuild_by

    def to_dict(self, package: "SolidPackage", *, has_deps: bool = True, has_makedeps: bool = True, has_rebuild: bool = True, full_names: bool = False):
        return {
            "depends": package.basepkg.get_friend_names(self.depends, package.triple, full_names) if has_deps else [],
            "makedepends": package.basepkg.get_friend_names(self.makedepends, package.triple, full_names) if has_makedeps else [],
            "rebuild_by": package.basepkg.get_friend_names(self.rebuild_by, package.triple, full_names) if has_rebuild else [],
        }


class SolidPackage:
    def __init__(self, package: "Package", target: str, *, allow_nonsupport: bool = False):
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
    def rebuild_by(self):
        return self.basepkg.target_rebuild[self.triple]

    @property
    def pkgbuild_path(self):
        return self.basepkg.get_pkgbuild_path(self.triple, allow_nonsupport=self._allow_nonsupport)

    @property
    def depends_list(self):
        return DependencyList(self.depends, self.makedepends, self.rebuild_by)

    def depends_dict(self, has_deps: bool = True, has_makedeps: bool = True, has_rebuild: bool = True, full_names: bool = False):
        return self.depends_list.to_dict(self, has_deps=has_deps, has_makedeps=has_makedeps, has_rebuild=has_rebuild, full_names=full_names)

    def print_info(self, *, has_deps: bool = False, has_makedeps: bool = False, has_rebuild: bool = False, full_names: bool = False):
        dep_dict = self.depends_list.to_dict(self, full_names=full_names)

        deps = dep_dict["depends"] if has_deps else []
        makedeps = dep_dict["makedepends"] if has_makedeps else []
        rebuild_by = dep_dict["rebuild_by"] if has_rebuild else []

        if not (deps or makedeps or rebuild_by):
            return

        # only need to print the target triple header if:
        # 1. the target is not 'any'
        # 2. the package has multiple target triples
        need_target_header = self.triple != 'any'

        if need_target_header:
            cprint(f"  {self.triple}", "blue", attrs=["bold"])

        prefix = 4 if need_target_header else 2  # indent 4 spaces if target header is present

        if deps:
            print(f"{" " * prefix}deps: {", ".join(colored_list(deps, "light_cyan"))}")
        if makedeps:
            print(f"{" " * prefix}makedeps: {", ".join(colored_list(makedeps, "light_cyan"))}")
        if rebuild_by:
            print(f"{" " * prefix}rebuild: {", ".join(colored_list(rebuild_by, "light_cyan"))}")


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

    def do_resolve_all_depends(self):
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

    def _do_get_filepath(self, filename: str, triple: str, allow_nonsupport: bool = False):
        if ANY_TARGET in self.triples:
            return f"packages/{self.basename}/{filename}"

        if not allow_nonsupport:
            self._do_check_triple(triple)
        return f"packages/{triple}-{self.basename}/{filename}"

    def isany(self):
        return ANY_TARGET in self.triples

    def target_fullname(self, target: str):
        if self.isany():
            return self.basename
        return f"{target}-{self.basename}"

    def pkgdir(self, triple: str, allow_nonsupport: bool = False):
        return self._do_get_filepath("", triple, allow_nonsupport)

    def get_yaml_path(self, triple: str, allow_nonsupport: bool = False):
        return self._do_get_filepath("lilac.yaml", triple, allow_nonsupport)

    def get_pkgbuild_path(self, triple: str, allow_nonsupport: bool = False):
        return self._do_get_filepath("PKGBUILD", triple, allow_nonsupport)

    def supports_target(self, triple: str):
        return triple in self.triples

    def get_friend_names(self, friends: list[SolidPackage], triple: str, full_name: bool = False):
        def do_get_name(friend: SolidPackage, triple: str, full_name: bool = False):
            if full_name:
                return friend.basepkg.target_fullname(triple)

            # not full name, first try to eliminate the same triple
            if triple == friend.triple:
                return friend.basepkg.basename

            # not full name, nor the same triple, print the triple (even if it's 'any')
            return friend.basepkg.basename + colored(f" ({friend.triple})", "red", attrs=["bold"])

        return [do_get_name(friend, triple, full_name) for friend in friends]

    def print_info(self, *, selected_target: str = "", has_deps: bool = False, has_makedeps: bool = False, has_rebuild: bool = False, full_names: bool = False):
        filtered_triples = set(self.triples) & set([selected_target] if selected_target else ALL_TARGET_TRIPLE)
        if not filtered_triples:
            return

        cprint(self.basename, "green", attrs=["bold"], end=" ")
        cprint(f"({', '.join(filtered_triples)})", "grey", attrs=["bold"])

        if not full_names:
            depends_dict = {triple: SolidPackage(self, triple).depends_dict(has_deps, has_makedeps, has_rebuild) for triple in filtered_triples}

            has_deps &= any(depends_dict[triple]["depends"] for triple in filtered_triples)
            has_makedeps &= any(depends_dict[triple]["makedepends"] for triple in filtered_triples)
            has_rebuild &= any(depends_dict[triple]["rebuild_by"] for triple in filtered_triples)

            # collect triples with the same dependencies
            pairs: list[tuple[list[str], dict[str, list[str]]]] = []  # [triples] -> {[depends, makedepends, rebuild_by]}
            for triple, dep_dict in depends_dict.items():
                for pair in pairs:
                    if pair[1] == dep_dict:
                        pair[0].append(triple)
                        break
                else:
                    pairs.append(([triple], dep_dict))

            if not (has_deps or has_makedeps or has_rebuild):
                return  # absolutely nothing to print

            for triples, depends_dict in pairs:
                cprint(f"  {', '.join(triples) if len(triples) != len(filtered_triples) else '<all targets>'}", "blue", attrs=["bold"])

                NONE = [colored("None", "light_red", attrs=["bold"])]

                if has_deps:
                    print(f"    deps: {", ".join(colored_list(depends_dict['depends'] or NONE, "light_cyan"))}")
                if has_makedeps:
                    print(f"    makedeps: {", ".join(colored_list(depends_dict['makedepends'] or NONE, "light_cyan"))}")
                if has_rebuild:
                    print(f"    rebuild: {", ".join(colored_list(depends_dict['rebuild_by'] or NONE, "light_cyan"))}")

        else:
            for triple in filtered_triples:
                if selected_target and triple != selected_target:
                    continue
                SolidPackage(self, triple).print_info(has_deps=has_deps, has_makedeps=has_makedeps, has_rebuild=has_rebuild, full_names=full_names)


ALL_ARCH = ["x86_64", "riscv64"]
ALL_TARGET_TRIPLE = [f"{arch}-mos" for arch in ALL_ARCH] + [f"{arch}-elf" for arch in ALL_ARCH] + ["any"]
ANY_TARGET = 'any'

PACKAGES: dict[str, Package] = {}

YAML_STORE = YamlStore()


def initialise():
    PACKAGES.clear()

    tmp_storage: dict[str, set[str]] = {}
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
        PACKAGES[basename].do_resolve_all_depends()
