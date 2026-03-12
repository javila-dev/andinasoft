#!/usr/bin/env bash
set -euo pipefail

cd /code

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: no se encontró el comando '$cmd'." >&2
    echo "Instala el cliente MySQL y vuelve a ejecutar este script." >&2
    echo "Debian/Ubuntu: apt-get update && apt-get install -y default-mysql-client" >&2
    exit 127
  fi
}

require_cmd mysql
require_cmd mysqldump

get_env_value() {
  local key="$1"
  sed -n "s/^${key}=//p" /code/.env | head -n 1
}

DB_HOST="$(get_env_value DB_HOST)"
DB_USER="$(get_env_value DB_USER)"
DB_PASSWORD="$(get_env_value DB_PASSWORD)"
DB_PORT="$(get_env_value DB_PORT)"
DB_CASASVERANO="$(get_env_value DB_CASASVERANO)"

: "${DB_HOST:?No se encontró DB_HOST en /code/.env}"
: "${DB_USER:?No se encontró DB_USER en /code/.env}"
: "${DB_PASSWORD:?No se encontró DB_PASSWORD en /code/.env}"
: "${DB_CASASVERANO:?No se encontró DB_CASASVERANO en /code/.env}"

export MYSQL_PWD="$DB_PASSWORD"

DEST_DB="developer_oasis"

mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" \
  -e "CREATE DATABASE IF NOT EXISTS \`$DEST_DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;"

mysqldump_opts=(
  -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER"
  --no-data
  --default-character-set=utf8mb4
  --single-transaction
)

if mysqldump --help 2>/dev/null | grep -q -- "--set-gtid-purged"; then
  mysqldump_opts+=(--set-gtid-purged=OFF)
fi

run_dump_import() {
  local -a extra_opts=("$@")
  mysqldump "${mysqldump_opts[@]}" "${extra_opts[@]}" "$DB_CASASVERANO" \
  | sed -E 's#/\*![0-9]{5} DEFINER=[^*]*\*/##g; s/DEFINER=`[^`]+`@`[^`]+`//g' \
  | mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" "$DEST_DB"
}

if ! run_dump_import --routines --triggers --events; then
  echo "Aviso: no fue posible exportar routines/triggers/events con el usuario actual. Reintentando sin routines..." >&2
  if ! run_dump_import --triggers --events; then
    echo "Aviso: no fue posible exportar triggers/events. Reintentando solo tablas y vistas..." >&2
    run_dump_import
  fi
fi

SOURCE_ROUTINES="$(mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -Nse "
SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema = '$DB_CASASVERANO';
")"

DEST_ROUTINES="$(mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -Nse "
SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema = '$DEST_DB';
")"

if [ "${DEST_ROUTINES:-0}" -lt "${SOURCE_ROUTINES:-0}" ]; then
  echo "Aviso: faltan routines en '$DEST_DB' (${DEST_ROUTINES:-0}/${SOURCE_ROUTINES:-0})." >&2
  echo "Necesitas privilegio SHOW_ROUTINE para poder exportarlas con mysqldump." >&2
  echo "GRANT sugerido (ejecutar con un usuario administrador):" >&2
  echo "  GRANT SHOW_ROUTINE ON *.* TO '$DB_USER'@'%';" >&2
  echo "Luego ejecuta nuevamente este script." >&2
fi

mysql -h "$DB_HOST" -P "${DB_PORT:-3306}" -u "$DB_USER" -D "$DEST_DB" -e "
SELECT 'tables' AS obj, COUNT(*) AS total FROM information_schema.tables WHERE table_schema = '$DEST_DB' AND table_type = 'BASE TABLE'
UNION ALL
SELECT 'views' AS obj, COUNT(*) AS total FROM information_schema.tables WHERE table_schema = '$DEST_DB' AND table_type = 'VIEW'
UNION ALL
SELECT 'routines' AS obj, COUNT(*) AS total FROM information_schema.routines WHERE routine_schema = '$DEST_DB'
UNION ALL
SELECT 'triggers' AS obj, COUNT(*) AS total FROM information_schema.triggers WHERE trigger_schema = '$DEST_DB'
UNION ALL
SELECT 'events' AS obj, COUNT(*) AS total FROM information_schema.events WHERE event_schema = '$DEST_DB';
"
