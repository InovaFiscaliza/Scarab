#!/usr/bin/env bash

set -Eeuo pipefail

readonly INSTALL_PATH="/usr/local/sbin/scarab-deploy"

usage() {
    cat <<'EOF'
Usage:
  scarab-deploy.sh install --environment test|production --service-user USER
      [--instance NAME] [--source PATH] [--app-image IMAGE] [--db-image IMAGE]
  scarab-deploy update [--instance NAME] [--build-source PATH] [--no-pull]
  scarab-deploy validate|start|stop|status|logs|backup|test [--instance NAME]

Options and defaults:
  --environment test|production
      Required for install; no default.
  --service-user USER
      Required for install; no default.
  --instance NAME
      Instance and filesystem namespace (default: scarab).
  --source PATH
      Installation source (default: tree containing this script, when available).
  --app-image IMAGE, --db-image IMAGE
      Test defaults when both are omitted: localhost/scarab-app:INSTANCE and
      localhost/scarab-db:INSTANCE. Both options are required in production.
  --build-source PATH
      Update source (default: configured installation source for local builds).
  --no-pull
      Skip image pulls (pulling is enabled by default for immutable images).

Examples:
  sudo ./containers/scarab-deploy.sh install \
      --environment test --instance scarab-test --service-user lobao --source "$PWD"
  sudo -iu lobao scarab-deploy update --instance scarab-test
  sudo -iu lobao scarab-deploy test --instance scarab-test

  sudo ./containers/scarab-deploy.sh install \
      --environment production --instance scarab --service-user scarab \
      --app-image registry.example/scarab/app:1.0.0 \
      --db-image registry.example/scarab/db:1.0.0
  sudo -iu scarab scarab-deploy update --instance scarab
EOF
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

validate_instance() {
    [[ "$1" =~ ^[a-z][a-z0-9-]*$ ]] ||
        die "Instance must match ^[a-z][a-z0-9-]*$: $1"
}

validate_value() {
    local label="$1"
    local value="$2"
    [[ -n "$value" && "$value" != *$'\n'* && "$value" != *' '* ]] ||
        die "$label must be a non-empty value without spaces or newlines."
}

random_secret() {
    od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

write_root_file() {
    local target="$1"
    local mode="$2"
    local group="$3"
    local temporary
    temporary="$(mktemp)"
    cat >"$temporary"
    install -o root -g "$group" -m "$mode" "$temporary" "$target"
    rm -f "$temporary"
}

instance="scarab"
environment_name=""
service_user=""
source_root=""
app_image=""
db_image=""
build_source=""
pull_images=true

command_name="${1:-}"
if [[ -z "$command_name" || "$command_name" == "help" || "$command_name" == "--help" ]]; then
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
        --environment)
            (($# >= 2)) || die "--environment requires a value."
            environment_name="$2"
            shift 2
            ;;
        --service-user)
            (($# >= 2)) || die "--service-user requires a value."
            service_user="$2"
            shift 2
            ;;
        --source)
            (($# >= 2)) || die "--source requires a value."
            source_root="$2"
            shift 2
            ;;
        --app-image)
            (($# >= 2)) || die "--app-image requires a value."
            app_image="$2"
            shift 2
            ;;
        --db-image)
            (($# >= 2)) || die "--db-image requires a value."
            db_image="$2"
            shift 2
            ;;
        --build-source)
            (($# >= 2)) || die "--build-source requires a value."
            build_source="$2"
            shift 2
            ;;
        --no-pull)
            pull_images=false
            shift
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

validate_instance "$instance"

etc_dir="/etc/$instance"
config_dir="$etc_dir/config"
compose_env="$etc_dir/compose.env"
compose_file="$etc_dir/compose.yml"
build_file="$etc_dir/compose.build.yml"
runtime_env="$etc_dir/scarab.env"
postgres_dir="/var/lib/$instance/postgresql"
share_root="/srv/$instance"
share01_dir="$share_root/share01"
share02_dir="$share_root/share02"
fixtures_dir="$share_root/fixtures"
log_dir="/var/log/$instance"
backup_dir="/var/backups/$instance"

install_instance() {
    [[ "$(id -u)" -eq 0 ]] || die "The install command must run as root."
    [[ "$environment_name" == "test" || "$environment_name" == "production" ]] ||
        die "--environment must be test or production."
    [[ -n "$service_user" ]] || die "--service-user is required."
    id "$service_user" >/dev/null 2>&1 || die "Service user does not exist: $service_user"

    if [[ -z "$source_root" ]]; then
        local candidate
        candidate="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
        [[ -f "$candidate/config/default_config.json" ]] ||
            die "--source is required when the installer is not run from a source checkout."
        source_root="$candidate"
    fi
    source_root="$(cd "$source_root" && pwd)"

    [[ -f "$source_root/containers/podman-compose.yml" ]] || die "Invalid source tree: $source_root"
    [[ -f "$source_root/containers/podman-compose.build.yml" ]] || die "Build Compose file is missing."
    [[ -f "$source_root/containers/scarab.env.example" ]] || die "Environment template is missing."
    [[ -f "$source_root/config/default_config.json" ]] || die "Default configuration is missing."

    local service_group service_home
    service_group="$(id -gn "$service_user")"
    service_home="$(getent passwd "$service_user" | cut -d: -f6)"
    [[ -n "$service_home" ]] || die "Cannot determine home directory for $service_user."

    local build_local=false
    if [[ "$environment_name" == "test" ]]; then
        if [[ -n "$app_image" || -n "$db_image" ]]; then
            [[ -n "$app_image" && -n "$db_image" ]] ||
                die "Provide both --app-image and --db-image, or neither."
        else
            app_image="localhost/scarab-app:$instance"
            db_image="localhost/scarab-db:$instance"
            build_local=true
        fi
    else
        [[ -n "$app_image" ]] || die "--app-image is required for production."
        [[ -n "$db_image" ]] || die "--db-image is required for production."
    fi
    validate_value "Application image" "$app_image"
    validate_value "Database image" "$db_image"

    install -d -o root -g "$service_group" -m 0750 "$etc_dir" "$config_dir"
    install -d -o "$service_user" -g "$service_group" -m 0700 "$postgres_dir" "$backup_dir"
    install -d -o "$service_user" -g "$service_group" -m 0750 \
        "$share_root" "$share01_dir" "$share01_dir/post" "$share01_dir/trash" \
        "$share02_dir" "$share02_dir/media" "$fixtures_dir" "$log_dir"

    install -o root -g "$service_group" -m 0640 \
        "$source_root/containers/podman-compose.yml" "$compose_file"
    install -o root -g "$service_group" -m 0640 \
        "$source_root/containers/podman-compose.build.yml" "$build_file"
    install -o root -g root -m 0755 "$source_root/containers/scarab-deploy.sh" "$INSTALL_PATH"
    install -o root -g "$service_group" -m 0640 \
        "$source_root/config/default_config.json" "$config_dir/default_config.json"

    if [[ "$environment_name" == "test" && ! -e "$config_dir/config.json" ]]; then
        install -o root -g "$service_group" -m 0640 \
            "$source_root/examples/sandbox/config.json" "$config_dir/config.json"
    fi

    write_root_file "$compose_env" 0640 "$service_group" <<EOF
SCARAB_ENVIRONMENT=$environment_name
SCARAB_ENV_FILE=$runtime_env
SCARAB_CONFIG_DIR=$config_dir
SCARAB_POSTGRES_DIR=$postgres_dir
SCARAB_SHARE01_DIR=$share01_dir
SCARAB_SHARE02_DIR=$share02_dir
SCARAB_LOG_DIR=$log_dir
SCARAB_APP_IMAGE=$app_image
SCARAB_DB_IMAGE=$db_image
SCARAB_BUILD_LOCAL=$build_local
SCARAB_SOURCE_DIR=$source_root
EOF

    if [[ "$environment_name" == "test" && ! -e "$runtime_env" ]]; then
        local admin_password app_password
        admin_password="$(random_secret)"
        app_password="$(random_secret)"
        write_root_file "$runtime_env" 0640 "$service_group" <<EOF
POSTGRES_USER=scarab_admin
POSTGRES_PASSWORD=$admin_password
POSTGRES_DB=scarab
SCARAB_DB_PASSWORD=$app_password
EOF
        unset admin_password app_password
    elif [[ "$environment_name" == "production" && ! -e "$runtime_env.example" ]]; then
        install -o root -g "$service_group" -m 0640 \
            "$source_root/containers/scarab.env.example" "$runtime_env.example"
    fi

    if [[ "$environment_name" == "test" ]]; then
        local extraction_dir
        extraction_dir="$(mktemp -d)"
        tar -xzf "$source_root/examples/store/test_01.tgz" -C "$extraction_dir"
        find "$fixtures_dir" -mindepth 1 -delete
        cp "$extraction_dir"/sandbox/store/*.json "$fixtures_dir/"
        chown -R "$service_user:$service_group" "$fixtures_dir"
        chmod 0640 "$fixtures_dir"/*.json
        rm -rf "$extraction_dir"
    fi

    local unit_dir unit_file
    unit_dir="$service_home/.config/systemd/user"
    unit_file="$unit_dir/$instance.service"
    install -d -o "$service_user" -g "$service_group" -m 0750 "$unit_dir"
    local unit_temporary
    unit_temporary="$(mktemp)"
    cat >"$unit_temporary" <<EOF
[Unit]
Description=Scarab container stack ($instance)
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=$INSTALL_PATH start --instance $instance
ExecStop=$INSTALL_PATH stop --instance $instance
RemainAfterExit=yes
TimeoutStartSec=180

[Install]
WantedBy=default.target
EOF
    install -o "$service_user" -g "$service_group" -m 0644 "$unit_temporary" "$unit_file"
    rm -f "$unit_temporary"

    if command -v loginctl >/dev/null 2>&1; then
        if ! loginctl enable-linger "$service_user"; then
            printf 'WARNING: enable linger manually for %s before relying on boot startup.\n' \
                "$service_user" >&2
        fi
    fi

    printf 'Installed %s environment "%s".\n' "$instance" "$environment_name"
    if [[ "$environment_name" == "production" && ! -e "$runtime_env" ]]; then
        printf 'Create %s from %s and replace every CHANGE_ME value.\n' \
            "$runtime_env" "$runtime_env.example"
    fi
    printf 'Next, run as %s: %s update --instance %s\n' \
        "$service_user" "$INSTALL_PATH" "$instance"
    printf 'Optional systemd activation: systemctl --user enable --now %s.service\n' "$instance"
}

load_instance() {
    [[ "$(id -u)" -ne 0 ]] || die "Run lifecycle commands as the rootless service user, not root."
    [[ -r "$compose_env" ]] || die "Compose environment not readable: $compose_env"
    [[ -r "$compose_file" ]] || die "Compose file not readable: $compose_file"

    set -a
    # The file is generated by the root-only install command from validated values.
    # shellcheck disable=SC1090
    source "$compose_env"
    set +a

    local required_variable
    for required_variable in \
        SCARAB_ENVIRONMENT SCARAB_ENV_FILE SCARAB_CONFIG_DIR SCARAB_POSTGRES_DIR \
        SCARAB_SHARE01_DIR SCARAB_SHARE02_DIR SCARAB_LOG_DIR SCARAB_APP_IMAGE SCARAB_DB_IMAGE \
        SCARAB_BUILD_LOCAL; do
        [[ -n "${!required_variable:-}" ]] || die "$required_variable is missing from $compose_env"
    done

    [[ -r "$SCARAB_ENV_FILE" ]] || die "Runtime environment not readable: $SCARAB_ENV_FILE"
    [[ -r "$SCARAB_CONFIG_DIR/default_config.json" ]] || die "Default configuration is missing."
    grep -q '^POSTGRES_USER=' "$SCARAB_ENV_FILE" || die "POSTGRES_USER is missing."
    grep -q '^POSTGRES_PASSWORD=' "$SCARAB_ENV_FILE" || die "POSTGRES_PASSWORD is missing."
    grep -q '^POSTGRES_DB=' "$SCARAB_ENV_FILE" || die "POSTGRES_DB is missing."
    grep -q '^SCARAB_DB_PASSWORD=' "$SCARAB_ENV_FILE" || die "SCARAB_DB_PASSWORD is missing."
    ! grep -q 'CHANGE_ME' "$SCARAB_ENV_FILE" || die "Replace all CHANGE_ME values in $SCARAB_ENV_FILE"

    local postgres_user
    postgres_user="$(grep -m1 '^POSTGRES_USER=' "$SCARAB_ENV_FILE" | cut -d= -f2-)"
    postgres_user="${postgres_user%$'\r'}"
    postgres_user="${postgres_user#\"}"
    postgres_user="${postgres_user%\"}"
    postgres_user="${postgres_user#\'}"
    postgres_user="${postgres_user%\'}"
    [[ "$postgres_user" != "scarab_app" ]] ||
        die "POSTGRES_USER must be an administrative role distinct from scarab_app."

    local data_owner
    data_owner="$(stat -c '%U' "$SCARAB_POSTGRES_DIR")"
    [[ "$data_owner" == "$(id -un)" ]] ||
        die "$SCARAB_POSTGRES_DIR must be owned by $(id -un), currently $data_owner."
}

compose() {
    PODMAN_COMPOSE_WARNING_LOGS=false \
        podman compose --env-file "$compose_env" -p "$instance" -f "$compose_file" "$@"
}

compose_with_build() {
    local source="$1"
    shift
    [[ -r "$build_file" ]] || die "Build Compose file not readable: $build_file"
    PODMAN_COMPOSE_WARNING_LOGS=false SCARAB_SOURCE_DIR="$source" podman compose \
        --env-file "$compose_env" -p "$instance" \
        -f "$compose_file" -f "$build_file" "$@"
}

container_id_for_service() {
    podman ps -a \
        --filter "label=com.docker.compose.project=$instance" \
        --filter "label=com.docker.compose.service=$1" \
        --format '{{.ID}}' | head -n 1
}

wait_for_database() {
    local attempt container_id health
    for ((attempt = 1; attempt <= 60; attempt++)); do
        container_id="$(container_id_for_service db)"
        if [[ -n "$container_id" ]]; then
            health="$(podman inspect --format '{{.State.Health.Status}}' "$container_id" 2>/dev/null || true)"
            [[ "$health" == "healthy" ]] && return 0
            [[ "$health" == "unhealthy" ]] && die "Database healthcheck failed."
        fi
        sleep 2
    done
    die "Database did not become healthy within 120 seconds."
}

provision_application_role() {
    compose exec -T db /usr/local/sbin/scarab-provision-app-role
}

wait_for_application() {
    local attempt container_id status
    for ((attempt = 1; attempt <= 30; attempt++)); do
        container_id="$(container_id_for_service app)"
        if [[ -n "$container_id" ]]; then
            status="$(podman inspect --format '{{.State.Status}}' "$container_id" 2>/dev/null || true)"
            [[ "$status" == "running" ]] && return 0
        fi
        sleep 1
    done
    die "Application did not reach the running state within 30 seconds."
}

start_stack() {
    compose config >/dev/null

    local db_container app_container
    db_container="$(container_id_for_service db)"
    app_container="$(container_id_for_service app)"
    if [[ -n "$db_container" && -n "$app_container" ]]; then
        podman start "$db_container" >/dev/null
    else
        if [[ -n "$db_container" || -n "$app_container" ]]; then
            compose down
        fi
        compose up -d
    fi

    wait_for_database
    provision_application_role
    wait_for_application
    compose ps
}

update_stack() {
    local selected_source="$build_source"
    if [[ -n "$selected_source" && "$SCARAB_BUILD_LOCAL" != "true" ]]; then
        die "--build-source is disabled for instances configured with immutable images."
    fi
    if [[ -z "$selected_source" && "$SCARAB_BUILD_LOCAL" == "true" ]]; then
        selected_source="${SCARAB_SOURCE_DIR:-}"
    fi

    if [[ -n "$selected_source" ]]; then
        selected_source="$(cd "$selected_source" && pwd)"
        [[ -f "$selected_source/containers/Containerfile.app" ]] ||
            die "Invalid build source: $selected_source"
        compose_with_build "$selected_source" build
    elif [[ "$pull_images" == true ]]; then
        compose pull
    fi

    compose down
    start_stack
}

stop_stack() {
    compose down
}

backup_database() {
    local timestamp target temporary
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    target="$backup_dir/scarab-$timestamp.dump"
    temporary="$target.tmp"
    umask 077
    # Variables in this command are expanded by the shell inside the db container.
    # shellcheck disable=SC2016
    compose exec -T db sh -c \
        'exec pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' \
        >"$temporary"
    mv "$temporary" "$target"
    printf 'Created backup: %s\n' "$target"
}

reset_test_data() {
    [[ "$SCARAB_ENVIRONMENT" == "test" ]] || die "The test command is disabled outside test environments."
    compose down
    find "$SCARAB_POSTGRES_DIR" -mindepth 1 -delete
    find "$SCARAB_SHARE01_DIR/post" -mindepth 1 -delete
    find "$SCARAB_SHARE01_DIR/trash" -mindepth 1 -delete
    find "$SCARAB_SHARE02_DIR/media" -mindepth 1 -delete
}

run_functional_test() {
    reset_test_data
    start_stack

    local fixture_count
    fixture_count="$(find "$fixtures_dir" -maxdepth 1 -type f -name '*.json' | wc -l)"
    [[ "$fixture_count" -eq 6 ]] || die "Expected 6 JSON fixtures, found $fixture_count."
    cp "$fixtures_dir"/*.json "$SCARAB_SHARE01_DIR/post/"

    local attempt remaining
    for ((attempt = 1; attempt <= 60; attempt++)); do
        remaining="$(find "$SCARAB_SHARE01_DIR/post" -maxdepth 1 -type f | wc -l)"
        [[ "$remaining" -eq 0 ]] && break
        sleep 2
    done
    [[ "$remaining" -eq 0 ]] || die "Functional descriptors were not consumed within 120 seconds."

    local clients history successes
    clients="$(compose exec -T db psql -U scarab_app -d scarab -Atc 'SELECT count(*) FROM clientes_docs;')"
    history="$(compose exec -T db psql -U scarab_app -d scarab -Atc 'SELECT count(*) FROM carga_historico;')"
    successes="$(compose exec -T db psql -U scarab_app -d scarab -Atc \
        "SELECT count(*) FROM carga_historico WHERE status = 'SUCESSO';")"

    [[ "$clients" == "2" ]] || die "Expected 2 final clients, found $clients."
    [[ "$history" == "6" ]] || die "Expected 6 history rows, found $history."
    [[ "$successes" == "6" ]] || die "Expected 6 successful rows, found $successes."
    [[ -z "$(find "$SCARAB_SHARE01_DIR/trash" -mindepth 1 -print -quit)" ]] ||
        die "Trash is not empty after the functional test."

    printf 'Functional test passed: 2 clients, 6 successful history rows.\n'
}

case "$command_name" in
    install)
        require_command install
        require_command getent
        require_command tar
        require_command od
        install_instance
        ;;
    update)
        require_command podman
        load_instance
        update_stack
        ;;
    validate)
        require_command podman
        load_instance
        compose config >/dev/null
        printf 'Deployment configuration is valid for %s.\n' "$instance"
        ;;
    start)
        require_command podman
        load_instance
        start_stack
        ;;
    stop)
        require_command podman
        load_instance
        stop_stack
        ;;
    status)
        require_command podman
        load_instance
        compose ps
        ;;
    logs)
        require_command podman
        load_instance
        compose logs --tail=200 app db
        ;;
    backup)
        require_command podman
        load_instance
        backup_database
        ;;
    test)
        require_command podman
        load_instance
        run_functional_test
        ;;
    *)
        die "Unknown command: $command_name"
        ;;
esac