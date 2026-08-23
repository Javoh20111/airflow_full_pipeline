/*
==============================================
Create Database and Schema
==============================================
Script Purpose:
    This script creates a new database named 'airflow_apartments_db' after
    checking if it already exists. If the database exists, it is dropped
    and recreated from scratch. Additionally, the script sets up three
    schemas within the database: 'bronze', 'silver', and 'gold',
    representing the layers of the medallion architecture.

WARNING:
    Running this script will drop the entire 'airflow_apartments_db' database
    if it exists. ALL data in the database will be permanently deleted.
    Proceed with caution and ensure you have proper backups before running
    this script in any environment that matters.
*/

DROP DATABASE IF EXISTS airflow_apartments_db;

CREATE DATABASE airflow_apartments_db;

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;