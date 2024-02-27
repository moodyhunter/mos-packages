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

prepare_deps() {
    echo "==> Preparing dependencies..."

    for dep in $(get_deps $package); do
        echo -n "-> Dependency '$dep' required by '$package'"
        fetch_package $dep
    done

    for makedep in $(get_makedeps $package); do
        echo -n "-> Make dependency '$makedep' required by '$package'"
        fetch_package $makedep
    done
}

finalize() {
    echo "==> Finalizing..."
    mkdir -p $shell_dir/output/
    package_output=$(makepkg --packagelist)
    package_output_num=$(echo "$package_output" | wc -l)
    if [ "$package_output_num" -gt 1 ]; then
        for pkg in $package_output; do
            if ! [[ -f $pkg ]]; then
                echo " -> Package file '$pkg' not found."
                continue
            fi
            # strip the version number
            _filename=$(basename $pkg | sed -e 's/-[0-9].*//g')
            _tail=$(basename $pkg | sed -e 's/.*-//g')
            mv -v $pkg $shell_dir/output/$_filename-$_tail
        done
    else
        cp -v $package_output $shell_dir/output/$package.pkg.tar.zst
    fi
}

shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized

[ $# -eq 0 ] && usage && exit

cd $shell_dir

extra_makepkg_args=(-s -c --noconfirm)

while getopts "idj:p:h" arg; do
    case $arg in
    i) # Install package after build.
        echo "Will install the package after build."
        extra_makepkg_args+=(-i)
        shift
        ;;
    d) # Debug this script.
        set -x
        shift
        ;;
    h) # Display this help.
        usage
        exit 0
        ;;
    p) # Use specified PKGBUILD file.
        extra_makepkg_args+=(-p $OPTARG)
        echo "Will use '$OPTARG' as PKGBUILD file."
        shift
        ;;
    j) # Use specified number of jobs.
        MAKEFLAGS="-j$OPTARG"
        echo "Will use '$OPTARG' as number of jobs."
        shift
        ;;
    esac
done

package=$1
package_dir=$(find_package_dir "$package")
shift

if [ -z "$package_dir" ]; then
    echo "Package '$package' not found."
    exit 1
fi

extra_makepkg_args+=("$@")

cd "$package_dir"

prepare_deps

echo "::group::Invoke 'makepkg ${extra_makepkg_args[@]}' for '$package'"
makepkg "${extra_makepkg_args[@]}"
echo "::endgroup::"

finalize
echo "==> Done building '$package'."
