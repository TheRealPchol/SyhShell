#!/usr/bin/env bash

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1

VERSION="2.1"
GOSS_VERSION=$(cat ./root/data/version)
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
        exit 0
    else
        err "Build exited with error. Code: $ret"
        exit $ret
    fi

    info "Build was ended"
    exit 0
}

run(){
    go run .
    exit $?
}

version(){
    echo "GoSS tools version $VERSION"
    echo "GoSS version: $GOSS_VERSION"
    echo
}

case "$1" in
    build|run|version)
        "$1" "$2" "$3" "$4"
        ;;
    "")
        version
        echo "usage: $0 {run|build|version}"
        exit 1
        ;;
    *)
        version
        err "unknown command: $1"
        echo "usage: $0 {run|build|version}"
        exit 1
        ;;
esac
