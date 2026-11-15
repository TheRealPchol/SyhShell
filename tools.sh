VERSION="GoSS tools version 1"
GOSS_VERSION=$(cat ./data/version)
BUILDS_DIR=./builds/

COLOR_RED="\033[31m"
COLOR_GREEN="\033[32m"
COLOR_G="\033[96m"
COLOR_RESET="\033[0m"

build() {
    echo "$COLOR_G[INFO]$COLOR_RESET Start building into '$BUILDS_DIR/goss'"
    mkdir -p $BUILDS_DIR/$GOSS_VERSION/
    rm  $BUILDS_DIR/$GOSS_VERSION/* 2> /dev/null
    go build -o $BUILDS_DIR/$GOSS_VERSION/goss .
    ret=$?
    if [ $ret -eq 0 ]; then
        echo "$COLOR_GREEN[OK]$COLOR_RESET Build completed successfully"
    elif [ $ret -ne 0 ]; then
        echo "$COLOR_RED[ERROR]$COLOR_RESET Build exited with error. Code: $ret"
        exit
    fi

    echo "$COLOR_G[INFO]$COLOR_RESET Build was ended"
    exit
}

run(){
    go run .

}

version(){
    echo $VERSION
}

$1 $2 $3 $4


