#!/usr/bin/env bash

set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime_library="$script_dir/lib/scarab-runtime.sh"
if [[ ! -r "$runtime_library" ]]; then
    runtime_library="/usr/local/lib/scarab/scarab-runtime.sh"
fi
[[ -r "$runtime_library" ]] || {
    printf 'ERROR: Scarab runtime library not found.\n' >&2
    exit 1
}
# shellcheck disable=SC1090
source "$runtime_library"

usage() {
    cat <<'EOF'
Usage:
  scarab-ops validate|start|stop|restart|status|logs|backup [--instance NAME]

Options:
  --instance NAME
      Installed instance to operate (default: scarab).
  -h, --help
      Show this help text.
EOF
}

instance="scarab"
command_name="${1:-}"
if [[ -z "$command_name" || "$command_name" == "help" || "$command_name" == "--help" || "$command_name" == "-h" ]]; then
    usage
    exit 0
fi
shift

while (($#)); do
    case "$1" in
        --instance)
            (($# >= 2)) || die "--instance requires a value."
            instance="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

configure_instance_paths "$instance"
require_command podman
load_instance

case "$command_name" in
    validate)
        require_storage_mount
        compose config >/dev/null
        db_container="$(container_id_for_service db)"
        app_container="$(container_id_for_service app)"
        if [[ -n "$db_container" || -n "$app_container" ]]; then
            [[ -n "$db_container" && -n "$app_container" ]] ||
                die "Only part of the installed stack exists."
            verify_stack
        fi
        printf 'Operational configuration is valid for %s.\n' "$instance"
        ;;
    start)
        start_stack
        ;;
    stop)
        stop_stack
        ;;
    restart)
        stop_stack
        start_stack
        ;;
    status)
        compose ps
        ;;
    logs)
        compose logs --tail=200 app db
        ;;
    backup)
        backup_database
        ;;
    *)
        die "Unknown operation: $command_name"
        ;;
esac