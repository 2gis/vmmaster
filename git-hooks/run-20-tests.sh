#!/usr/bin/env bash

echo ""
echo -en "\033[36m"
echo "running tests with coverage!"
echo -en "\033[0m"

make clean
make ctest
RESULT=$?

if [ $RESULT -ne 0 ]
then
    echo -en "\033[41m"
    echo -en "Иди тесты чини!"
    echo -e "\033[0m"
    exit $RESULT
else
    echo -en "\033[42m"
    echo -en "Молодец, $(whoami), тесты проходят!"
    echo -e "\033[0m"
    exit 0
fi
