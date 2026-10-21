#!/bin/sh
# Database per Service sobre una sola instancia de PostgreSQL: una base y un
# usuario por servicio. Cada usuario es dueño solo de su base y no puede
# conectarse a las demás. Lo ejecuta la imagen oficial en el primer arranque.
set -eu

for servicio in identidad cursos certificados notificaciones; do
  variable="CLAVE_DB_$(echo "$servicio" | tr '[:lower:]' '[:upper:]')"
  eval clave="\${$variable}"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<SQL
CREATE ROLE $servicio LOGIN PASSWORD '$clave';
CREATE DATABASE $servicio OWNER $servicio;
REVOKE CONNECT ON DATABASE $servicio FROM PUBLIC;
GRANT CONNECT ON DATABASE $servicio TO $servicio;
SQL
done
