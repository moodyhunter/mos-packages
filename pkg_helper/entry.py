#!/usr/bin/python

import argparse
import difflib
import os
import shutil
import sys
from glob import glob
from pathlib import Path

from termcolor import cprint

from pkg_helper import (PACKAGES, Package, PackageNotFoundError, SolidPackage,
                        UnsupportedTargetError, initialise, porting,
                        sanitise_triple)

SKIPPED_FILE_EXT = [
    (".pkg.tar.zst", "package"),
    (".log", "log"),
    (".pkg.tar.zst.sig", "signature"),
]


def try_find_package(hint: str, *, target: str = "") -> str | list[str]:
    # try to find the package with the exact name
    package = os.path.join("packages", hint)
    if package and os.path.isdir(package):
        return Path(package).name

    # if still not found, try globbing
    candidates = glob(f"packages/{target}*{hint}*/")
    candidates = [Path(candidate).name for candidate in candidates]
    return candidates[0] if len(candidates) == 1 else candidates


def yes_or_no(question: str, default: str = "") -> bool:
    while True:
        cprint(question, "yellow", attrs=["bold"], end="")
        yn = " [Y/n]" if default == "y" else " [y/N]" if default == "n" else " [y/n]"
        answer = input(f" {yn} ").lower().strip() or default
        if answer in ["y", "yes"]:
            return True
        elif answer in ["n", "no"]:
            return False
        else:
            cprint("Please answer with 'y' or 'n'", "red", attrs=["bold"])


def do_search(hint: str, target: str = ""):
    result = try_find_package(hint, target=target)
    if isinstance(result, list):
        if len(result) == 0:
            cprint(f"No package found for hint: {hint}", "red", attrs=["bold"])
        else:
            print(f"Multiple packages found:")
            for r in result:
                cprint(f'  {r}', "green", attrs=["bold"])
    else:
        cprint(result, "green", attrs=["bold"])


def do_info(name: str, target: str = "", full_names: bool = False):
    target = sanitise_triple(target)

    if name not in PACKAGES:
        cprint(f"No package found for '{name}'", "red", attrs=["bold"])
        sys.exit(1)

    p = PACKAGES[name]

    if target and target not in p.triples:
        cprint(f"Package {p.basename} does not support '{target}'", "red", attrs=["bold"])
        sys.exit(1)

    p.print_info(selected_target=target, has_deps=True, has_makedeps=True, has_rebuild=True, full_names=full_names)


def do_list(target: str, has_deps: bool = False, has_makedeps: bool = False, has_rebuild: bool = False, full_names: bool = False):
    target = sanitise_triple(target)

    for _, p in sorted(PACKAGES.items()):
        p.print_info(selected_target=target, has_deps=has_deps, has_makedeps=has_makedeps, has_rebuild=has_rebuild, full_names=full_names)


def do_diff_package(p: Package, triple1: str, triple2: str):
    triple1 = sanitise_triple(triple1)
    triple2 = sanitise_triple(triple2)

    if triple1 == triple2:
        cprint("The two targets are the same", "red", attrs=["bold"])
        sys.exit(1)

    p1 = SolidPackage(p, triple1)
    p2 = SolidPackage(p, triple2)

    print(f"diffing {p1.pkgbuild_path} and {p2.pkgbuild_path}")

    differences = difflib.unified_diff(
        open(p1.pkgbuild_path).readlines(),
        open(p2.pkgbuild_path).readlines(),
        fromfile=f"{p.basename}-{triple1}",
        tofile=f"{p.basename}-{triple2}",
    )

    for line in differences:
        if line.startswith('@@'):
            cprint(line, "yellow", attrs=["bold"], end="")
        elif line.startswith('+'):
            cprint(line, "green", attrs=["bold"], end="")
        elif line.startswith('-'):
            cprint(line, "red", attrs=["bold"], end="")
        else:
            print(line, end="")


def do_port_package(pkg: Package, src_triple: str, dst_triple: str, verbose: bool = False, landing: bool = False, force: bool = False):
    src_triple = sanitise_triple(src_triple)
    dst_triple = sanitise_triple(dst_triple)

    if dst_triple in pkg.triples:
        cprint(f"'{pkg.basename}' already supports '{dst_triple}'", "red", attrs=["bold"])
        if not force:
            return False

    cprint(f"Porting package {pkg.basename} from {src_triple} to {dst_triple}", "green", attrs=["bold"])

    src = SolidPackage(pkg, src_triple)
    driver = porting.PortDriver(src, dst_triple)
    dst = driver.context.dstpkg

    deplist = driver.check_package_deps()
    if deplist.is_empty():
        cprint(f'  dependency check for {pkg.basename} passed', 'green')
    else:
        cprint(f"Cannot port package {pkg.basename} to {dst_triple}: the following dependencies are not met", "red", attrs=["bold"])

        deplist_reasons = {dep.basename: ", ".join(
            (["dep"] if dep in deplist.depends else []) +
            (["makedep"] if dep in deplist.makedepends else []) +
            (["rebuild"] if dep in deplist.rebuild_by else [])
        ) for dep in set([dep for dep in deplist.depends + deplist.makedepends + deplist.rebuild_by])}

        for dep, reason in sorted(deplist_reasons.items()):
            cprint(f"  {dep} ({reason})", "red")

        return False

    src_filelist = os.listdir(src.pkgdir)

    files_changed = False

    for f in src_filelist:
        should_skip = False
        for ending, desc in SKIPPED_FILE_EXT:
            if f.endswith(ending):
                if verbose:
                    cprint(f"  skipping '{f}' as it is a {desc}", "yellow", attrs=["bold"])
                should_skip = True
                break  # skip the rest of the endings

        if not os.path.isfile(os.path.join(src.pkgdir, f)):
            if verbose:
                cprint(f"  skipping '{f}/' as it is not a file", "yellow")
            should_skip = True

        if should_skip:
            continue

        driver.add_step(porting.Action.COPY_FILE, os.path.join(src.pkgdir, f), os.path.join(dst.pkgdir, f))

        if src_triple not in f:
            if verbose:
                cprint(f"  no need to rename '{f}': file name doesn't contain {src_triple}", "yellow")
            continue

        # also detect if it contains the triple in the content
        with open(os.path.join(src.pkgdir, f), "r") as file:
            content = file.read()
            if src_triple in content:
                driver.add_step(porting.Action.PATCH_FILE, src_triple, dst_triple, os.path.join(dst.pkgdir, f))
                files_changed |= True
            elif verbose:
                cprint(f"  no need to patch '{f}': file content doesn't contain {src_triple}", "yellow")

        # this file is a target-specific file, rename it
        driver.add_step(porting.Action.RENAME_FILE, os.path.join(dst.pkgdir, f), os.path.join(dst.pkgdir, f.replace(src_triple, dst_triple)))

    src_arch = src_triple.split("-")[0]
    dst_arch = dst_triple.split("-")[0]

    driver.add_step(porting.Action.PATCH_FILE, src_arch, dst_arch, os.path.join(dst.pkgdir, "PKGBUILD"))
    if files_changed:
        driver.add_step(porting.Action.UPDPKGSUMS, "", "")

    driver.add_step(porting.Action.PATCH_FILE, src_arch, dst_arch, os.path.join(dst.pkgdir, "lilac.yaml"))

    driver.add_step(porting.Action.PATCH_FILE, f"build_prefix: mos-{src_arch}", f"build_prefix: mos-{dst_arch}", os.path.join(dst.pkgdir, "lilac.yaml"))
    driver.print_steps()

    if landing:
        if force and dst_triple in pkg.triples:
            answer = yes_or_no(f"Do you want to clear '{dst.pkgdir}'?", default='y')
            if answer:
                try:
                    shutil.rmtree(dst.pkgdir)
                except FileNotFoundError:
                    pass
                print(f"Directory '{dst.pkgdir}' removed")

        result = driver.execute()
        cprint(f"Porting {'succeeded' if result else 'failed'}", "green" if result else "red", attrs=["bold"])

        if not result:
            answer = yes_or_no(f"Do you want to clear '{dst.pkgdir}'?", default='y')
            if answer:
                try:
                    shutil.rmtree(dst.pkgdir)
                except FileNotFoundError:
                    pass
                print(f"Directory '{dst.pkgdir}' removed")
    else:
        print("Dry-run, no changes made")
        print("To actually port the package, use the -y option")


def do_version_package(pkg: Package, version: str | None = None):
    cprint(f"Changing version of package {pkg.basename} to {version}", "green", attrs=["bold"])
    pass


def do_initpkg(name: str, target: str):
    target = sanitise_triple(target)

    dirpath = os.path.join("packages", f"{target}-{name}")
    if os.path.exists(dirpath):
        cprint(f"Package {name} already exists at {dirpath}", "red", attrs=["bold"])
        sys.exit(1)

    cprint(f"Initializing package {name} for target {target}", "green", attrs=["bold"])

    # run `pkgctl repo clone [package]`
    with porting.AlternativeWorkDir('packages'):
        result = os.system(f"pkgctl repo clone {name}")
        if result != 0:
            cprint(f"Failed to clone package {name}", "red", attrs=["bold"])
            sys.exit(1)

        # remove .SRCINFO
        if os.path.exists(f"{name}/.SRCINFO"):
            os.remove(f"{name}/.SRCINFO")

        # remove the .git directory
        shutil.rmtree(f"{name}/.git")

        # move {package} to {target}-{package}
        shutil.move(name, f"{target}-{name}")

    build_prefix = f"mos-{target.split('-')[0]}"  # e.g. mos-x86_64

    with open(f"packages/{target}-{name}/lilac.yaml", "w") as lilac_yaml:  # create lilac.yaml
        def do_write(line: str):
            lilac_yaml.write(line + '\n')
            lilac_yaml.flush()
        do_write(f"# created by 'pkg {' '.join(sys.argv[1:])}`")
        do_write(f"")
        do_write(f"maintainers:")
        do_write(f"  - github: moodyhunter")
        do_write(f"")
        do_write(f"build_prefix: {build_prefix}")
        do_write(f"")
        do_write(f"repo_depends:")
        do_write(f"  - {target}-mlibc")  # default dependency
        do_write(f"")
        do_write(f"repo_makedepends:")
        do_write(f"  - {target}-gcc")  # default makedependency
        do_write(f"")
        do_write(f"pre_build_script: update_pkgver_and_pkgrel(_G.newver, updpkgsums=True)")
        do_write(f"post_build: git_pkgbuild_commit")
        do_write(f"")
        do_write(f"update_on:")
        do_write(f"  - source: alpm")
        do_write(f"    alpm: {name}")
        do_write(f"    strip_release: true")
        do_write(f"")
        do_write(f"update_on_build:")
        do_write(f"  - pkgbase: {target}-mlibc")  # default dependency
        do_write(f"  - pkgbase: {target}-gcc")  # default makedependency
        lilac_yaml.flush()

    pass


def main_may_throw():
    parser = argparse.ArgumentParser(
        description='This script helps you to maintain packages in the MOS package repository',
        exit_on_error=True,
    )

    subparser = parser.add_subparsers(dest='command', help='Package lookup commands')

    # Package lookup subcommands
    base_subparser = argparse.ArgumentParser(add_help=False)
    base_subparser.add_argument('-v', '--verbose', action='store_true', help='Show more information')
    base_subparser.add_argument('-t', '--target', type=str, default="", help='The target triple of the package')
    base_subparser.add_argument('-f', '--full-names', action='store_true', help='Show full package names')

    list_parser = subparser.add_parser('list', help='List all packages in the repository', parents=[base_subparser], aliases=['ls'])
    list_parser.add_argument('--deps', action='store_true', help='Show package dependencies')
    list_parser.add_argument('--makedeps', action='store_true', help='Show package makedependencies')
    list_parser.add_argument('--rebuild', action='store_true', help='Show packages which triggers the rebuild of this package')

    search_parser = subparser.add_parser('search', help='Search for a package in the repository', parents=[base_subparser])
    search_parser.add_argument('hint', type=str, help='The (partial) name of the package to search')

    info_parser = subparser.add_parser('info', help='Show the information of a package', parents=[base_subparser], aliases=['show'])
    info_parser.add_argument('name', type=str, help='The name of the package to show')

    # Package maintenance subcommands
    initpkg_parser = subparser.add_parser('initpkg', help='Initialize a new package from Arch Linux package', aliases=['init'])
    initpkg_parser.add_argument('name', type=str, help='The name of the package to initialize')
    initpkg_parser.add_argument('-t', '--target', type=str, default="x86_64-mos", help='The target triple of the package')

    diffports_parser = subparser.add_parser('diff', help='Diff the ports of a package between two targets', parents=[base_subparser])
    diffports_parser.add_argument('triple1', type=str, help='The first target triple')
    diffports_parser.add_argument('triple2', type=str, help='The second target triple')
    diffports_parser.add_argument('name', type=str, help='The name of the package to diff')

    port_parser = subparser.add_parser('port', help='Port the package from one target to another')
    port_parser.add_argument('triple1', type=str, help='The source target triple')
    port_parser.add_argument('triple2', type=str, help='The destination target triple')
    port_parser.add_argument('name', type=str, help='The name of the package to port')
    port_parser.add_argument('-y', '--yes', action='store_true', help='Do not dry-run')
    port_parser.add_argument('--force', action='store_true', help='Force porting even if the package already supports the destination target')
    port_parser.add_argument('-v', '--verbose', action='store_true', help='Show more information')

    version_parser = subparser.add_parser('version', help='Show and modify the version of a package')
    version_parser.add_argument('name', type=str, help='The name of the package to show')
    version_parser.add_argument('-s', '--set', type=str, help='Set the version of a package')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    initialise()

    if args.command == "list" or args.command == "ls":
        if args.verbose:
            args.deps = args.makedeps = args.rebuild = True  # show all if verbose
        do_list(args.target, args.deps, args.makedeps, args.rebuild, args.full_names)
    elif args.command == "info" or args.command == "show":
        do_info(args.name, args.target, args.full_names)
    elif args.command == "search":
        do_search(args.hint, args.target)
    elif args.command == "diff":
        p = PACKAGES[args.name]
        do_diff_package(p, args.triple1, args.triple2)
    elif args.command == "port":
        p = PACKAGES[args.name]
        do_port_package(p, args.triple1, args.triple2, args.verbose, args.yes, args.force)
    elif args.command == "version":
        p = PACKAGES[args.name]
        version = args.set
        do_version_package(p, version)
    elif args.command == "initpkg" or args.command == "init":
        do_initpkg(args.name, args.target)


def main():
    try:
        main_may_throw()
        return 0
    except KeyError as e:
        cprint(f"KeyError: {e}, probably misspelled a package name?", "red", attrs=["bold"])
    except UnsupportedTargetError as e:
        cprint(f"Error: {e}", "red", attrs=["bold"])
    except PackageNotFoundError as e:
        cprint(f"Error: {e}", "red", attrs=["bold"])
    except ValueError as e:
        cprint(f"Error: {e}", "red", attrs=["bold"])
    except KeyboardInterrupt:
        cprint("Interrupted by user", "red", attrs=["bold"])
    except Exception as e:
        cprint(f"Error: {e}", "red", attrs=["bold"])
    finally:
        sys.exit(1)
