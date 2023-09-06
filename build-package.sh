#!/usr/bin/env bash

set -e

shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized

usage() {
    pattern=") #"
    echo "Usage:"
    echo "  $0 <package> [options]"
    echo "Options:"
    grep " .$pattern" $0 | sed -e "s/$pattern/:/g"
}

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

echo "==> Building '$package'..."
pushd $package_dir >/dev/null 2>&1

if [ -f "build.sh" ]; then
    echo "  -> Lunching custom build script..."
    exec ./build.sh
fi

echo "  -> Lunching makepkg with args: '${extra_makepkg_args[@]}'"
makepkg "${extra_makepkg_args[@]}"
