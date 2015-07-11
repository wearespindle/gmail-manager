#!/bin/bash

echo "Grant gmailmanager access from all IPs."
echo "host all gmailmanager 0.0.0.0/0 trust" >> /var/lib/postgresql/data/pg_hba.conf

echo "Create a user and database."
gosu postgres postgres --single <<- EOSQL
    CREATE USER gmailmanager;
    CREATE DATABASE gmailmanager;
    GRANT ALL PRIVILEGES ON DATABASE gmailmanager TO gmailmanager;
    ALTER USER gmailmanager CREATEDB;
EOSQL

echo "Done initializing."
