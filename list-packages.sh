#!/usr/bin/env bash

set -e
shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized
. $shell_dir/scripts/common.sh

usage() {
    pattern=") #"
    echo "Usage:"
    echo "  $0 [options] [package]"
    echo "Options:"
    grep " .$pattern" $0 | sed -e "s/$pattern/:/g"
}

while getopts "vhq" arg; do
    case $arg in
    v) # Verbose
        verbose=1
        shift
        ;;
    h) # Help
        usage
        exit 0
        ;;
    q) # quiet
        verbose=0
        quiet=1
        shift
        ;;
    *)
        usage
        exit 1
        ;;
    esac
done

package_count=$#
if [ $package_count -gt 1 ]; then
    echo "Too many arguments"
    usage
    exit 1
fi

package=$@

if [ -z "$package" ]; then
    categories=$(find $shell_dir/packages/*/ -maxdepth 0 -type d -exec basename {} \;)

    for category in $categories; do
        [ "$quiet" != "1" ] && echo "==> $category"

        packages=$(find $shell_dir/packages/$category/*/ -maxdepth 0 -type d -exec basename {} \;)

        if [ -z "$packages" ]; then
            echo "No packages found in $category"
            continue
        fi

        for package in $packages; do
            if [ "$quiet" != "1" ]; then
                echo "- $package"
            else
                echo "$package"
            fi

            if [ "$verbose" == "1" ]; then
                deps=$(get_deps $package)
                makedeps=$(get_makedeps $package)

                if [ ! -z "$deps" ]; then
                    echo "  depends:"
                    for dep in $deps; do
                        echo "    $dep"
                    done
                fi

                if [ ! -z "$makedeps" ]; then
                    echo "  makedepends:"
                    for makedep in $makedeps; do
                        echo "    $makedep"
                    done
                fi
                echo ""
            fi
        done
    done
else
    pkgname=$(try_find_package $package)
    if [ -z "$pkgname" ]; then
        echo "Package $arg1 not found"
        exit 1
    fi

    pkgdir=$(find_package_dir $pkgname)
    if [ -z "$pkgdir" ]; then
        echo "Package $pkgname not found"
        exit 1
    fi

    deps=$(get_deps $pkgname)
    makedeps=$(get_makedeps $pkgname)

    echo "$pkgname"
    echo "  pkgdir: $pkgdir"
    if [ ! -z "$deps" ]; then
        echo "  depends:"
        for dep in $deps; do
            echo "    $dep"
        done
    fi

    if [ ! -z "$makedeps" ]; then
        echo "  makedepends:"
        for makedep in $makedeps; do
            echo "    $makedep"
        done
    fi
fi
