#!/usr/bin/env bash

cd "$(dirname "$0")" || exit 1

VERSION="GoSS tools version 1"
GOSS_VERSION=$(cat ./data/version)
BUILDS_DIR=./builds/

COLOR_RED="\033[31m"
COLOR_GREEN="\033[32m"
COLOR_G="\033[96m"
COLOR_RESET="\033[0m"

info() { echo -e "$COLOR_G[INFO]$COLOR_RESET $*"; }
ok()   { echo -e "$COLOR_GREEN[OK]$COLOR_RESET $*"; }
err()  { echo -e "$COLOR_RED[ERROR]$COLOR_RESET $*"; }

build() {
    info "Start building into '$BUILDS_DIR$GOSS_VERSION/goss'"
    mkdir -p "$BUILDS_DIR$GOSS_VERSION/"
    rm -f "$BUILDS_DIR$GOSS_VERSION"/* 2> /dev/null
    go build -o "$BUILDS_DIR$GOSS_VERSION/goss" .
    ret=$?
    if [ $ret -eq 0 ]; then
        ok "Build completed successfully"
    else
        err "Build exited with error. Code: $ret"
        exit $ret
    fi

    info "Build was ended"
    exit 0
}

run(){
    go run .
}

version(){
    echo "$VERSION"
}

case "$1" in
    build|run|version)
        "$1" "$2" "$3" "$4"
        ;;
    "")
        echo "usage: $0 {run|build|version}"
        exit 1
        ;;
    *)
        err "unknown command: $1"
        echo "usage: $0 {run|build|version}"
        exit 1
        ;;
esac
