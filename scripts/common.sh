set -e

repo="moodyhunter/mos-packages"
base_url="https://github.com/$repo/releases/download/artifact/"
ext=".pkg.tar.zst"

sudo="sudo"
if [ "$(whoami)" = "root" ]; then
    sudo=""
fi

# check if jq is installed
if test ! $(which jq 2>/dev/null); then
    echo "jq is required to parse json" >&2
    exit 1
fi

supported_archs=("x86_64")

find_package_dir() {
    _package=$1
    _package_dir=$(find $shell_dir/packages/*/ -maxdepth 1 -type d -name "$_package")
    if [ -z "$_package_dir" ]; then
        echo "Package not found: $_package" >&2
        exit 1
    fi
    echo $_package_dir
}

try_find_package() {
    _package=$1

    # try to find the package with the exact name
    _package_dir=$(find $shell_dir/packages/*/ -maxdepth 1 -type d -name "$_package")

    # if not found, try to find the package with the same name but different arch
    if [ -z "$_package_dir" ]; then
        for arch in ${supported_archs[@]}; do
            _package_dir=$(find $shell_dir/packages/*/ -maxdepth 1 -type d -name "$arch-$_package")
            if [ ! -z "$_package_dir" ]; then
                break
            fi
        done
    fi

    # if still not found, try globbing
    if [ -z "$_package_dir" ]; then
        _package_dir=$(find $shell_dir/packages/*/ -maxdepth 1 -type d -name "*$_package*")
    fi

    # make sure there is only one result
    if [ ! -z "$_package_dir" ]; then
        _package_dir_count=$(echo "$_package_dir" | wc -l)
        if [ $_package_dir_count -gt 1 ]; then
            echo "Multiple packages found: " >&2
            for _package_dir_item in $_package_dir; do
                echo "  $(basename "$_package_dir_item")" >&2
            done
            exit 1
        fi
    fi

    # return the full package name, or empty string if not found
    echo $(basename "$_package_dir")
}

_do_get_deps() {
    _package=$1
    _dep_type=$2
    _package_dir=$(find_package_dir "$_package")
    if [ -z "$_package_dir" ]; then
        echo "Package not found: $_package" >&2
        exit 1
    fi

    if [ ! -f "$_package_dir/pkg.json" ]; then
        echo "Package json not found: $_package_dir/pkg.json" >&2
        exit 1
    fi

    _package_json=$(cat $_package_dir/pkg.json)
    _package_deps=$(echo $_package_json | jq -r ".$_dep_type[]" 2>/dev/null || true)
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
    pacman -Q $_package >/dev/null 2>&1 && echo " -> installed" && return
    echo " -> fetching..." && $shell_dir/fetch-package.sh $_package
}
