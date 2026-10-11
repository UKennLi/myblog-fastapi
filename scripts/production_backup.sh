#!/usr/bin/env bash
# Run manually on the production host; default is a read-only preview.
set -euo pipefail
umask 077
execute=false
if [[ "${1:-}" == --execute ]]; then execute=true; shift; fi
if [[ $# != 3 ]]; then
  echo 'Usage: production_backup.sh [--execute] PROJECT_ROOT BACKUP_ROOT MYSQL_CLIENT_CNF' >&2
  exit 2
fi
project=$(realpath -e -- "$1")
backup=$(realpath -m -- "$2")
cnf=$(realpath -e -- "$3")
[[ -d "$project/uploads" && -f "$cnf" ]] || { echo 'Missing uploads or client config' >&2; exit 1; }
[[ "$backup" != "$project" && "$backup" != "$project/"* ]] || { echo 'Backups must be outside the checkout' >&2; exit 1; }
[[ "$(stat -c '%a' -- "$cnf")" == 600 || "$(stat -c '%a' -- "$cnf")" == 400 ]] || { echo 'MySQL config must have mode 600 or 400' >&2; exit 1; }
if ! $execute; then
  echo 'Preview only: export eight tables as data-only SQL, archive uploads and copy private configuration.'
  echo 'Pause application writes first for a database/uploads consistent snapshot; rerun with --execute after approval.'
  exit 0
fi
command -v mysqldump >/dev/null
mkdir -p -- "$backup"
chmod 700 -- "$backup"
destination=$(mktemp -d "$backup/$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
# --defaults-extra-file must be the first option. Password stays off argv/logs.
mysqldump --defaults-extra-file="$cnf" --single-transaction --skip-lock-tables \
  --no-tablespaces --set-gtid-purged=OFF --no-create-info --skip-add-drop-table \
  --skip-triggers --skip-disable-keys --skip-add-locks --complete-insert --hex-blob --default-character-set=utf8mb4 \
  myblog_db t_user t_category t_post t_tag t_post_tag t_comment t_option t_link \
  > "$destination/data.sql"
[[ -s "$destination/data.sql" ]] || { echo 'Empty database dump; backup incomplete' >&2; exit 1; }
tar -czf "$destination/uploads.tar.gz" -C "$project" uploads
if [[ -f "$project/.env" ]]; then cp -- "$project/.env" "$destination/private.env"; fi
git -C "$project" rev-parse HEAD > "$destination/commit.txt"
(cd "$destination" && sha256sum data.sql uploads.tar.gz commit.txt > SHA256SUMS &&
 if [[ -f private.env ]]; then sha256sum private.env >> SHA256SUMS; fi)
echo "Backup completed: $destination"
echo 'Backup contains private data. Encrypt and copy off-host; never commit it.'
