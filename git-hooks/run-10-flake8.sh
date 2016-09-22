#!/usr/bin/env bash

echo ""
echo -en "\033[36m"
echo "running flake8!"
echo -en "\033[0m"

FILES=$(git diff --diff-filter=ACMRTUXB --name-only HEAD^ | egrep '^.*\.py$')
if [[ -n $FILES ]]; then
    flake8 --max-line-length=120 $FILES
    RESULT=$?
else
    echo "no files to check"
    RESULT=0
fi

if [ $RESULT -ne 0 ]
then
    echo -en "\033[41m"
    echo -en "Воу воу воу! Поправь стиль!"
    echo -e "\033[0m"
    exit $RESULT
else
    echo -en "\033[42m"
    echo -en "$(whoami), ты лучше всех!"
    echo -e "\033[0m"
    exit 0
fi
