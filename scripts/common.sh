set -e

repo="moodyhunter/mos-packages"
base_url="https://github.com/$repo/releases/download/artifact/"
ext=".pkg.tar.zst"

sudo="sudo"
if [ "$(whoami)" = "root" ]; then
    sudo=""
fi

# check if yq is installed
if test ! $(which yq 2>/dev/null); then
    echo "yq is required to parse yaml" >&2
    exit 1
fi

supported_archs=("x86_64")

try_find_package() {
    _package=$1

    # try to find the package with the exact name
    _package_dir=$(find $shell_dir/packages/ -maxdepth 1 -type d -name "$_package")

    # # if not found, try to find the package with the same name but different arch
    # if [ -z "$_package_dir" ]; then
    #     for arch in ${supported_archs[@]}; do
    #         _package_dir=$(find $shell_dir/packages/ -maxdepth 1 -type d -name "$arch-$_package")
    #         if [ ! -z "$_package_dir" ]; then
    #             break
    #         fi
    #     done
    # fi

    # if still not found, try globbing
    if [ -z "$_package_dir" ]; then
        _package_dir=$(find $shell_dir/packages/*/ -maxdepth 0 -type d -name "*$_package*")
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

find_package_dir() {
    _package_name=$1
    _packages=$(try_find_package "$_package_name")

    if [ -z "$_packages" ]; then
        exit 1 # try_find_package will print the error message and return nothing on error
    fi

    if [ ! "$_packages" = "$_package_name" ]; then
        # try_find_package returned a different package name
        echo "Package not found: '$_package_name', did you mean '$_packages'?" >&2
        exit 1
    fi

    echo "$shell_dir/packages/$_packages"
}

_do_get_deps() {
    _package=$1
    _dep_type=$2
    _package_dir=$(find_package_dir "$_package")

    if [ ! -f "$_package_dir/lilac.yaml" ]; then
        echo "Package yaml not found: $_package_dir/lilac.yaml" >&2
        exit 1
    fi

    yq -r ".$_dep_type[]" $_package_dir/lilac.yaml 2>/dev/null || true
}

get_deps() {
    _do_get_deps $1 "repo_depends"
}

get_makedeps() {
    _do_get_deps $1 "repo_makedepends"
}

fetch_package() {
    _package=$1
    pacman -Q $_package >/dev/null 2>&1 && echo " -> installed" && return
    echo " -> fetching..." && $shell_dir/fetch-package.sh $_package
}
