#!/usr/bin/env bash

set -e
shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized
. $shell_dir/scripts/common.sh

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
for dep in $(get_deps $package); do
    echo "-> Found dependency '$dep' required by '$package'"
    $shell_dir/bootstrap-package.sh $dep -i -f
done

# then build the package, with any extra arguments
echo "-> Building package '$package'"
$shell_dir/build-package.sh $package $@
