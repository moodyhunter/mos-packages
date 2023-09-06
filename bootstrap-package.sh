#!/usr/bin/env bash

set -e

shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized

usage() {
    echo "Usage:"
    echo "  $0 <package>"
}

[ $# -eq 0 ] && usage && exit

package=$1
package_dir=$(find $shell_dir/packages/*/ -type d -name "$package")
shift

if [ -z "$package_dir" ]; then
    echo "Package '$package' not found."
    exit 1
fi

# first read the package's pkg.json, if it exists
if [ -f "$package_dir/pkg.json" ]; then
    pkg_json=$(cat $package_dir/pkg.json)
    pkg_deps=$(echo $pkg_json | jq -r '.deps[]')

    for dep in $pkg_deps; do
        echo "-> Found dependency '$dep' required by '$package'"
        $shell_dir/bootstrap-package.sh $dep -i -f
    done
fi

# then build the package, with any extra arguments
echo "-> Building package '$package'"
$shell_dir/build-package.sh $package $@
