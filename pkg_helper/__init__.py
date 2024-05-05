import os
from glob import glob
from pathlib import Path

import yaml
from termcolor import colored, cprint


class Config:
    print_full_pkgname = False


CONFIG = Config()


def try_find_package(hint: str, *, arch=None) -> str | list[str]:
    # try to find the package with the exact name
    package = os.path.join("packages", hint)
    if package and os.path.isdir(package):
        return Path(package).name

    # if still not found, try globbing
    candidates = glob(f"packages/{arch or ""}*{hint}*/")
    candidates = [Path(candidate).name for candidate in candidates]
    return candidates[0] if len(candidates) == 1 else candidates


def sanitise_triple(target: str) -> str:
    if target and target not in ALL_TARGET_TRIPLE and target in ALL_ARCH:
        cprint(f"'{target}' is not a valid target triple, assuming '{target}-mos'", "light_blue")
        target = f"{target}-mos"

    return target


def colored_list(l, color: str):
    return [colored(e, color, attrs=['bold']) for e in l] if l else ["-"]


class YamlStore:
    def __init__(self):
        self.store = {}

    def get(self, path: str):
        if path not in self.store:
            self.store[path] = yaml.safe_load(open(path))
        return self.store[path]


class Package:
    def __init__(self, name):
        self._fullname = name
        self.basename = name
        self.triples = set()
        for target in ALL_TARGET_TRIPLE:
            prefix = target + "-"
            if name.startswith(prefix):
                self.triples.add(target)
                self.basename = name[len(prefix):]
                break
        else:
            self.triples = ANY_TARGET_TRIPLE

        self.yamlstore = {}

    def _do_check_triple(self, triple: str):
        if triple not in ALL_TARGET_TRIPLE:
            raise ValueError(f"Invalid target triple: {triple}")

        if triple not in self.triples:
            raise ValueError(f"Package {self.basename} does not support target {triple}")

    def _do_get_filepath(self, filename: str, triple: str, allow_nonsupport=False):
        if self.triples == ANY_TARGET_TRIPLE:
            return f"packages/{self.basename}/{filename}"

        if not allow_nonsupport:
            self._do_check_triple(triple)
        return f"packages/{triple}-{self.basename}/{filename}"

    def get_package_dir(self, triple: str, allow_nonsupport=False):
        return self._do_get_filepath("", triple, allow_nonsupport)

    def get_yaml_path(self, triple: str, allow_nonsupport=False):
        return self._do_get_filepath("lilac.yaml", triple, allow_nonsupport)

    def get_pkgbuild_path(self, triple: str, allow_nonsupport=False):
        return self._do_get_filepath("PKGBUILD", triple, allow_nonsupport)

    def get_friends_name(self, friend: "Package", triple: str, full_name=False):
        if CONFIG.print_full_pkgname or full_name:
            return friend._fullname
        else:
            return friend.basename if (triple in friend.triples) else f"{friend.basename} " + colored("(any)", "yellow")

    def get_friend_names(self, friends: list["Package"], triple: str, full_name=False):
        return [self.get_friends_name(friend, triple, full_name) for friend in friends]

    def get_depends(self, triple=None, full_name=False):
        yaml_data = YAML_STORE.get(self.get_yaml_path(triple))
        depends = self.get_friend_names([Package(dep) for dep in yaml_data.get("repo_depends", [])], triple, full_name)
        return depends

    def get_makedepends(self, triple=None, full_name=False):
        yaml_data = YAML_STORE.get(self.get_yaml_path(triple))
        makedepends = self.get_friend_names([Package(dep) for dep in yaml_data.get("repo_makedepends", [])], triple, full_name)
        return makedepends

    def get_rebuild(self, triple=None, full_name=False):
        yaml_data = YAML_STORE.get(self.get_yaml_path(triple))
        rebuilds = [self.get_friends_name(Package(e.get("pkgbase")), triple, full_name) for e in yaml_data.get("update_on_build", [])]
        return rebuilds

    def print_info(self, *, selected_target=None, has_deps=False, has_makedeps=False, has_rebuild=False):
        cprint(self.basename, "green", attrs=["bold"], end=" ")

        if selected_target:
            cprint(f"({selected_target})", "yellow", attrs=["bold"])
        else:
            cprint(f"({', '.join(self.triples)})", "yellow", attrs=["bold"])

        for triple in self.triples:
            if selected_target and triple != selected_target:
                continue

            deps = self.get_depends(triple) if has_deps else None
            makedeps = self.get_makedepends(triple) if has_makedeps else None
            rebuild_by = self.get_rebuild(triple) if has_rebuild else None

            if not (deps or makedeps or rebuild_by):
                continue

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
ALL_TARGET_TRIPLE = [f"{arch}-mos" for arch in ALL_ARCH] + [f"{arch}-elf" for arch in ALL_ARCH]
ANY_TARGET_TRIPLE = set(['any'])

PACKAGES: dict[str, Package] = {}

YAML_STORE = YamlStore()


def initialise():
    PACKAGES.clear()
    CONFIG.print_full_pkgname = False

    names = [dir for dir in os.listdir("packages") if os.path.isdir("packages/" + dir)]
    names.sort()

    for pkgname in names:
        p = Package(pkgname)

        if p.basename in PACKAGES:
            assert PACKAGES[p.basename].triples != ANY_TARGET_TRIPLE
            PACKAGES[p.basename].triples |= p.triples
        else:
            PACKAGES[p.basename] = p
