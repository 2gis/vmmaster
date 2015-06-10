#!/usr/bin/env bash

echo ""
echo -en "\033[36m"
echo "running flake8!"
echo -en "\033[0m"

git diff --cached --name-only --diff-filter=AM | egrep '^.*\.py$' | xargs flake8
RESULT=$?

if [ $RESULT -ne 0 ]
then
    echo -en "\033[41m"
    echo -en "Воу воу воу! Перед коммитом поправь стиль!"
    echo -e "\033[0m"
    exit $RESULT
else
    echo -en "\033[42m"
    echo -en "$(whoami), ты лучше всех!"
    echo -e "\033[0m"
    exit 0
fi
