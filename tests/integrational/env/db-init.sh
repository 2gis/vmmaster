#!/usr/bin/env bash

export PGPASSWORD="$POSTGRES_USER"

psql -h 0.0.0.0 -p 5432 -U postgres -f /tmp/db-init.sql
