#!/usr/bin/env bash

set -e
shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized
. $shell_dir/scripts/common.sh

prepare_deps() {
    echo "==> Preparing dependencies for '$package'..."

    for dep in $(get_deps $package); do
        echo "-> Dependency '$dep' required by '$package'"
        fetch_package $dep
    done
}

usage() {
    echo "Usage:"
    echo "  $0 <package>"
}

[ $# -eq 0 ] && usage && exit

package=$1
package_dir=$(find $shell_dir/packages/*/ -type d -name "$package")
shift

prepare_deps

package_full="$package$ext"
mkdir -p $shell_dir/downloads/
echo "==> Downloading package '$package_full'..."
curl -sf -L -o $shell_dir/downloads/$package_full "$base_url/$package_full" || failed=1

if [ "$failed" ]; then
    echo "Package not found: $package"
    exit 1
else
    echo "Package downloaded: $package_full"
fi

$sudo pacman -U --noconfirm $shell_dir/downloads/$package_full
