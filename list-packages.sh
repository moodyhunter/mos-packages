#!/usr/bin/env bash

set -e
shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized
. $shell_dir/scripts/common.sh

usage() {
    pattern=") #"
    echo "Usage:"
    echo "  $0 <package> [options]"
    echo "Options:"
    grep " .$pattern" $0 | sed -e "s/$pattern/:/g"
}

while getopts "vhp:" arg; do
    case $arg in
    v) # Verbose
        verbose=1
        echo "Will use verbose mode."
        shift
        ;;
    h) # Help
        usage
        exit 0
        ;;
    p) # show specific package info
        package=$OPTARG
        shift
        ;;
    *)
        usage
        exit 1
        ;;
    esac
done

if [ -z "$package" ]; then
    categories=$(find $shell_dir/packages/*/ -maxdepth 0 -type d -exec basename {} \;)

    for category in $categories; do
        echo "==> $category"
        packages=$(find $shell_dir/packages/$category/*/ -maxdepth 0 -type d -exec basename {} \;)

        if [ -z "$packages" ]; then
            echo "No packages found in $category"
            continue
        fi

        for package in $packages; do
            echo "- $package"

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
