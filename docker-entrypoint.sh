#!/bin/bash
# http://handynotes.ru/2010/02/umask.html
umask 0000
exec "$@"

