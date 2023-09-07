#!/usr/bin/env bash

set -e

repo="moodyhunter/mos-packages"
base_url="https://github.com/$repo/releases/download/artifact/"
ext=".pkg.tar.zst"

sudo="sudo"
if [ "$(whoami)" = "root" ]; then
    sudo=""
fi

prepare_deps() {
    echo "==> Preparing dependencies for '$package'..."

    if [ ! -f $package_dir/pkg.json ]; then
        echo "  -> No dependencies found."
        return
    fi

    pkg_json=$(cat $package_dir/pkg.json)
    pkg_deps=$(echo $pkg_json | jq -r '.deps[]')

    for dep in $pkg_deps; do
        echo "-> Dependency '$dep' required by '$package'"
        pacman -Q $dep >/dev/null 2>&1 && continue # skip if already installed
        $shell_dir/fetch-package.sh $dep
        $sudo pacman -U --noconfirm $shell_dir/downloads/$dep.pkg.tar.zst
    done
}

shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized

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
curl -f -L -o $shell_dir/downloads/$package_full "$base_url/$package_full" || failed=1

if [ "$failed" ]; then
    echo "Package not found: $package"
    exit 1
else
    echo "Package downloaded: $package_full"
fi
