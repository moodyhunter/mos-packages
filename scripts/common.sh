set -e

repo="moodyhunter/mos-packages"
base_url="https://github.com/$repo/releases/download/artifact/"
ext=".pkg.tar.zst"

sudo="sudo"
if [ "$(whoami)" = "root" ]; then
    sudo=""
fi

_do_get_deps() {
    _package=$1
    _dep_type=$2
    _package_dir=$(find $shell_dir/packages/*/ -type d -name "$_package")
    if [ -z "$_package_dir" ]; then
        echo "Package not found: $_package"
        exit 1
    fi

    if [ ! -f $_package_dir/pkg.json ]; then
        return
    fi

    _package_json=$(cat $_package_dir/pkg.json)
    _package_deps=$(echo $_package_json | jq -r ".$_dep_type[]" 2>/dev/null)
    echo $_package_deps
}

get_deps() {
    _do_get_deps $1 "deps"
}

get_makedeps() {
    _do_get_deps $1 "makedeps"
}

fetch_package() {
    _package=$1
    pacman -Q $_package >/dev/null 2>&1 && return # skip if already installed
    $shell_dir/fetch-package.sh $_package
}
