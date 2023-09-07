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
        echo "-> Dependency '$dep' required by '$package'"
        fetch_package $dep
    done

    for makedep in $(get_makedeps $package); do
        echo "-> Make dependency '$makedep' required by '$package'"
        fetch_package $makedep
    done
}

finalize() {
    echo "==> Finalizing..."
    package_output=$(makepkg --packagelist)
    package_output_num=$(echo "$package_output" | wc -l)
    if [ "$package_output_num" -gt 1 ]; then
        echo "  -> Multiple packages found. This is not supported yet."
        exit 1
    fi

    mkdir -p $shell_dir/output/
    cp -v $package_output $shell_dir/output/$package.pkg.tar.zst
}

shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized

[ $# -eq 0 ] && usage && exit

cd $shell_dir

package=$1
package_dir=$(find $shell_dir/packages/*/ -type d -name "$package")
shift

if [ -z "$package_dir" ]; then
    echo "Package '$package' not found."
    exit 1
fi

extra_makepkg_args=(-s -c --noconfirm)

while getopts "idp:h" arg; do
    case $arg in
    i) # Install package after build.
        echo "Will install '$package' after build."
        extra_makepkg_args+=(-i)
        ;;
    d) # Debug this script.
        set -x
        ;;
    h) # Display this help.
        usage
        exit 0
        ;;
    p) # Use specified PKGBUILD file.
        extra_makepkg_args+=(-p $OPTARG)
        echo "Will use '$OPTARG' as PKGBUILD file."
        ;;
    esac
done

extra_makepkg_args+=("$@")

cd $package_dir

prepare_deps

echo "::group::Invoke 'makepkg ${extra_makepkg_args[@]}' for '$package'"
makepkg "${extra_makepkg_args[@]}"
echo "::endgroup::"

finalize
echo "==> Done building '$package'."
