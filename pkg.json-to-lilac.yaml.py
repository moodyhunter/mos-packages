#!/usr/bin/env python3

import json
import os


def json_to_lilac(pkg_json, pkgname):
    with open(pkg_json) as f:
        data = json.load(f)

    has_deps = "deps" in data
    has_makedeps = "makedeps" in data
    deps_prefix = ''
    makedeps_prefix = ''

    deps = []
    makedeps = []

    if has_deps:
        deps = data["deps"]
        deps_prefix = '\n\nrepo_depends:\n'

    if has_makedeps:
        makedeps = data["makedeps"]
        makedeps_prefix = '\n\nrepo_makedepends:\n'

    deps_str = "\n".join(f"  - {dep}" for dep in deps)
    makedeps_str = "\n".join(f"  - {dep}" for dep in makedeps)

    return f"""# converted by pkg.json-to-lilac.py for {pkgname}

maintainers:
  - github: moodyhunter

build_prefix: mos-x86_64{deps_prefix}{deps_str}{makedeps_prefix}{makedeps_str}

post_build: git_pkgbuild_commit

update_on:
  - source: archpkg
    archpkg: {pkgname}
"""


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} pkg.json [pkg.json ...]")
        sys.exit(1)

    for pkg_json in sys.argv[1:]:
        file = os.path.basename(pkg_json)
        dirname = os.path.dirname(pkg_json)

        pkgname = os.path.basename(dirname).removeprefix("x86_64-mos-")

        yamlpath = dirname + f"/lilac.yaml"
        yaml = json_to_lilac(pkg_json, pkgname)

        with open(yamlpath, 'w') as f:
            f.write(yaml)
