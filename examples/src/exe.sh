#!/usr/bin/env bash

set -Eeuo pipefail

readonly RUNTIME_LIBRARY="/usr/local/lib/scarab/scarab-runtime.sh"
readonly OPS_PATH="/usr/local/sbin/scarab-ops"

usage() {
    cat <<'EOF'
Usage:
  exe.sh [--instance NAME] [--sandbox-dir PATH] --confirm-reset NAME

Destructively resets an installed test instance, applies sandbox/config.json,
and submits the six canonical JSON fixtures one at a time. This command cannot
run against a production instance.
EOF
}

instance="scarab-test"
sandbox_dir=""
confirm_reset=""

while (($#)); do
    case "$1" in
        --instance)
            (($# >= 2)) || { printf 'ERROR: --instance requires a value.\n' >&2; exit 1; }
            instance="$2"
            shift 2
            ;;
        --sandbox-dir)
            (($# >= 2)) || { printf 'ERROR: --sandbox-dir requires a value.\n' >&2; exit 1; }
            sandbox_dir="$2"
            shift 2
            ;;
        --confirm-reset)
            (($# >= 2)) || { printf 'ERROR: --confirm-reset requires a value.\n' >&2; exit 1; }
            confirm_reset="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf 'ERROR: Unknown option: %s\n' "$1" >&2
            exit 1
            ;;
    esac
done

[[ -r "$RUNTIME_LIBRARY" ]] || { printf 'ERROR: Runtime library not installed.\n' >&2; exit 1; }
[[ -x "$OPS_PATH" ]] || { printf 'ERROR: Operations script not installed.\n' >&2; exit 1; }
# shellcheck disable=SC1090
source "$RUNTIME_LIBRARY"

configure_instance_paths "$instance"
load_instance
[[ "$SCARAB_ENVIRONMENT" == "test" ]] || die "Scenario reset is disabled outside test environments."
[[ "$confirm_reset" == "$instance" ]] || die "Pass --confirm-reset $instance to authorize destructive reset."
[[ "$SCARAB_POSTGRES_DIR" == "$postgres_dir" ]] || die "Unexpected PostgreSQL data path."
[[ "$SCARAB_POST_DIR" == "$post_dir" ]] || die "Unexpected post path."
[[ "$SCARAB_GET_DIR" == "$get_dir" ]] || die "Unexpected get path."
[[ "$SCARAB_TRASH_DIR" == "$trash_dir" ]] || die "Unexpected trash path."

if [[ -z "$sandbox_dir" ]]; then
    sandbox_dir="$storage_root"
fi
[[ "$sandbox_dir" == /* && "$sandbox_dir" != *$'\n'* ]] || die "Sandbox path must be absolute."
[[ -f "$sandbox_dir/config.json" ]] || die "Sandbox config is missing: $sandbox_dir/config.json"
[[ -d "$sandbox_dir/store" ]] || die "Sandbox fixture directory is missing: $sandbox_dir/store"
[[ "$SCARAB_POST_DIR" == "$sandbox_dir/post" ]] || die "SCARAB_POST_DIR is not mapped to the sandbox."
[[ "$SCARAB_GET_DIR" == "$sandbox_dir/get" ]] || die "SCARAB_GET_DIR is not mapped to the sandbox."
[[ "$SCARAB_TRASH_DIR" == "$sandbox_dir/trash" ]] || die "SCARAB_TRASH_DIR is not mapped to the sandbox."
require_storage_mount

mapfile -d '' fixtures < <(find "$sandbox_dir/store" -maxdepth 1 -type f -name '*.json' -print0 | sort -z)
[[ "${#fixtures[@]}" -eq 6 ]] ||
    die "Expected 6 JSON fixtures in $sandbox_dir/store, found ${#fixtures[@]}. Restore test_01 first."

expected_counts() {
    case "$1" in
        01-insert-registro-001.json) printf '1|1|1\n' ;;
        02-insert-registro-002.json) printf '2|2|2\n' ;;
        03-insert-registro-003-com-email.json) printf '3|3|3\n' ;;
        04-update-registro-001-com-email.json) printf '3|4|4\n' ;;
        05-update-registro-002-com-email.json) printf '3|5|5\n' ;;
        06-delete-registro-002.json) printf '2|6|6\n' ;;
        *) die "No expected result is defined for fixture: $1" ;;
    esac
}

query_counts() {
    compose exec -T db psql -U scarab_app -d scarab -AtF '|' -c \
        "SELECT (SELECT count(*) FROM clientes_docs),
                (SELECT count(*) FROM carga_historico),
                (SELECT count(*) FROM carga_historico WHERE status = 'SUCESSO');"
}

show_audit_diagnostics() {
    printf 'Recent audit rows:\n' >&2
    compose exec -T db psql -U scarab_app -d scarab -P pager=off -c \
        "SELECT id, nome_original_arquivo, status, mensagem_erro
           FROM carga_historico
          ORDER BY id DESC
          LIMIT 6;" >&2 || true
}

for command in basename cp find install mv sort sudo systemctl; do
    require_command "$command"
done
sudo -v
systemctl --user stop "$instance.service" || true
"$OPS_PATH" stop --instance "$instance"

find -- "$SCARAB_POSTGRES_DIR" -mindepth 1 -delete
find -- "$SCARAB_POST_DIR" -mindepth 1 -delete
find -- "$SCARAB_GET_DIR" -mindepth 1 -delete
find -- "$SCARAB_TRASH_DIR" -mindepth 1 -delete

config_group="$(stat -c '%G' "$SCARAB_CONFIG_DIR")"
sudo install -o root -g "$config_group" -m 0640 \
    "$sandbox_dir/config.json" "$SCARAB_CONFIG_DIR/config.json"

systemctl --user reset-failed "$instance.service" || true
systemctl --user start "$instance.service"

initial_counts="$(query_counts)"
initial_counts="${initial_counts//$'\r'/}"
[[ "$initial_counts" == "0|0|0" ]] || {
    show_audit_diagnostics
    die "Reset did not produce an empty database (received $initial_counts)."
}

for fixture in "${fixtures[@]}"; do
    filename="$(basename "$fixture")"
    expected="$(expected_counts "$filename")"
    temporary="$sandbox_dir/.$filename.uploading"
    cp -- "$fixture" "$temporary"
    mv -- "$temporary" "$SCARAB_POST_DIR/$filename"

    consumed=false
    for ((attempt = 1; attempt <= 60; attempt++)); do
        if [[ ! -e "$SCARAB_POST_DIR/$filename" ]]; then
            consumed=true
            break
        fi
        sleep 2
    done
    [[ "$consumed" == true ]] || die "Fixture was not consumed within 120 seconds: $filename"

    actual="$(query_counts)"
    actual="${actual//$'\r'/}"
    if [[ "$actual" != "$expected" ]]; then
        show_audit_diagnostics
        die "Divergence after $filename: expected $expected (clients|history|successes), received $actual."
    fi
    printf 'Processed %s: %s (clients|history|successes)\n' "$filename" "$actual"
done

[[ -z "$(find "$SCARAB_TRASH_DIR" -mindepth 1 -print -quit)" ]] ||
    die "Trash is not empty after the scenario."
[[ -z "$(find "$SCARAB_GET_DIR" -mindepth 1 -print -quit)" ]] ||
    die "Get is not empty even though this scenario contains no media."

printf 'Scenario passed: 6 files processed, 2 final clients, 6 successful audit rows.\n'