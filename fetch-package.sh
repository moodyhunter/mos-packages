#!/usr/bin/env bash

set -e

repo="moodyhunter/mos-packages"
base_url="https://github.com/$repo/releases/download/artifact/"
ext=".pkg.tar.zst"

shell_dir=$(cd "$(dirname "$0")" && pwd) # absolutized and normalized

usage() {
    echo "Usage:"
    echo "  $0 <package>"
}

[ $# -eq 0 ] && usage && exit

package=$1
package_full="$package$ext"
mkdir -p downloads
curl -f -L -o $shell_dir/downloads/$package_full "$base_url/$package_full" || failed=1
curl_exit_code=$?

if [ "$failed" ]; then
    echo "Package not found: $package"
    exit 1
else
    echo "Package downloaded: $package_full"
fi
