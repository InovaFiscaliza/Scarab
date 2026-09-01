#!/usr/bin/env bash

set -Eeuo pipefail

readonly INSTALL_PATH="/usr/local/sbin/scarab-deploy"
readonly OPS_INSTALL_PATH="/usr/local/sbin/scarab-ops"
readonly MOUNT_INSTALL_PATH="/usr/local/sbin/mount-host-volumes"
readonly RUNTIME_LIBRARY_PATH="/usr/local/lib/scarab/scarab-runtime.sh"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
runtime_library="$script_dir/lib/scarab-runtime.sh"
if [[ ! -r "$runtime_library" ]]; then
    runtime_library="$RUNTIME_LIBRARY_PATH"
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
  scarab-deploy.sh install --environment test|production --service-user USER
        [--db-bind-address IPV4] [--db-port PORT]
    [--instance NAME] [--source PATH] [--app-image IMAGE] [--db-image IMAGE]
  scarab-deploy update [--instance NAME] [--build-source PATH] [--no-pull]

Options and defaults:
    Mandatory for install:
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
  --db-bind-address IPV4
      Optional non-loopback unicast IPv4 address assigned to this host. If
      omitted, a single such address is detected automatically; multiple
      addresses require this option.
  --db-port PORT
      Host port published to PostgreSQL container port 5432 (default: 5432).
  --build-source PATH
      Update source (default: configured installation source for local builds).
  --no-pull
      Skip image pulls (pulling is enabled by default for immutable images).

Re-running install for an existing instance refreshes its installed files and
then updates the stack as the configured rootless service user.

Examples:
    sudo ./deploy/scarab-deploy.sh install \
    --environment test --instance scarab-test --service-user lobao \
    --db-bind-address 192.0.2.10 --source "$PWD"
  sudo -iu lobao scarab-deploy update --instance scarab-test

    sudo ./deploy/scarab-deploy.sh install \
      --environment production --instance scarab --service-user scarab \
            --db-bind-address 192.0.2.10 \
      --app-image registry.example/scarab/app:1.0.0 \
      --db-image registry.example/scarab/db:1.0.0
  sudo -iu scarab scarab-deploy update --instance scarab
EOF
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
db_bind_address=""
db_port="5432"

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
        --db-bind-address)
            (($# >= 2)) || die "--db-bind-address requires a value."
            db_bind_address="$2"
            shift 2
            ;;
        --db-port)
            (($# >= 2)) || die "--db-port requires a value."
            db_port="$2"
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

configure_instance_paths "$instance"

install_instance() {
    [[ "$(id -u)" -eq 0 ]] || die "The install command must run as root."
    [[ "$environment_name" == "test" || "$environment_name" == "production" ]] ||
        die "--environment must be test or production."
    [[ "$service_user" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] ||
        die "--service-user must be a valid Linux account name."
    service_uid="$(id -u "$service_user" 2>/dev/null || true)"
    [[ -n "$service_uid" && "$service_uid" -ne 0 ]] ||
        die "The rootless service user cannot be root."
    if [[ -z "$db_bind_address" && -r "$compose_env" ]]; then
        db_bind_address="$(grep -m1 '^SCARAB_DB_BIND_ADDRESS=' "$compose_env" | cut -d= -f2- || true)"
    fi
    resolve_db_bind_address
    validate_port "$db_port"
    id "$service_user" >/dev/null 2>&1 || die "Service user does not exist: $service_user"

    require_command env
    require_command loginctl
    require_command runuser
    require_command systemctl

    if [[ -z "$source_root" ]]; then
        local candidate
        candidate="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
        [[ -f "$candidate/config/default_config.json" ]] ||
            die "--source is required when the installer is not run from a source checkout."
        source_root="$candidate"
    fi
    source_root="$(cd "$source_root" && pwd)"

    [[ -f "$source_root/deploy/podman-compose.yml" ]] || die "Invalid source tree: $source_root"
    [[ -f "$source_root/deploy/podman-compose.build.yml" ]] || die "Build Compose file is missing."
    [[ -f "$source_root/deploy/scarab-ops.sh" ]] || die "Operations script is missing."
    [[ -f "$source_root/deploy/lib/scarab-runtime.sh" ]] || die "Runtime library is missing."
    [[ -f "$source_root/deploy/mount-host-volumes.sh" ]] || die "Host volume setup script is missing."
    [[ -f "$source_root/deploy/scarab.env.example" ]] || die "Environment template is missing."
    [[ -f "$source_root/config/default_config.json" ]] || die "Default configuration is missing."

    local service_group service_home
    service_group="$(id -gn "$service_user")"
    service_home="$(getent passwd "$service_user" | cut -d: -f6)"
    [[ -n "$service_home" ]] || die "Cannot determine home directory for $service_user."

    local instance_installed=false installed_environment installed_owner
    if [[ -e "$compose_env" ]]; then
        [[ -r "$compose_env" && -r "$compose_file" && -d "$postgres_dir" ]] ||
            die "Instance $instance has an incomplete installation under $etc_dir."
        installed_environment="$(
            grep -m1 '^SCARAB_ENVIRONMENT=' "$compose_env" | cut -d= -f2- || true
        )"
        [[ -n "$installed_environment" ]] ||
            die "SCARAB_ENVIRONMENT is missing from $compose_env"
        [[ "$installed_environment" == "$environment_name" ]] ||
            die "Instance $instance is installed as $installed_environment, not $environment_name."
        installed_owner="$(stat -c '%U' "$postgres_dir")"
        [[ "$installed_owner" == "$service_user" ]] ||
            die "Instance $instance belongs to $installed_owner, not $service_user."
        instance_installed=true
    fi

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
    install -d -o root -g root -m 0755 "$(dirname "$RUNTIME_LIBRARY_PATH")"
    install -d -o "$service_user" -g "$service_group" -m 0700 "$postgres_dir" "$backup_dir"
    install -d -o "$service_user" -g "$service_group" -m 0750 \
        "$storage_root" "$post_dir" "$get_dir" "$trash_dir" "$log_dir"

    install -o root -g "$service_group" -m 0640 \
        "$source_root/deploy/podman-compose.yml" "$compose_file"
    install -o root -g "$service_group" -m 0640 \
        "$source_root/deploy/podman-compose.build.yml" "$build_file"
    install -o root -g root -m 0755 "$source_root/deploy/scarab-deploy.sh" "$INSTALL_PATH"
    install -o root -g root -m 0755 "$source_root/deploy/scarab-ops.sh" "$OPS_INSTALL_PATH"
    install -o root -g root -m 0755 \
        "$source_root/deploy/mount-host-volumes.sh" "$MOUNT_INSTALL_PATH"
    install -o root -g root -m 0644 \
        "$source_root/deploy/lib/scarab-runtime.sh" "$RUNTIME_LIBRARY_PATH"
    install -o root -g "$service_group" -m 0640 \
        "$source_root/config/default_config.json" "$config_dir/default_config.json"

    write_root_file "$compose_env" 0640 "$service_group" <<EOF
SCARAB_ENVIRONMENT=$environment_name
SCARAB_ENV_FILE=$runtime_env
SCARAB_CONFIG_DIR=$config_dir
SCARAB_POSTGRES_DIR=$postgres_dir
SCARAB_POST_DIR=$post_dir
SCARAB_GET_DIR=$get_dir
SCARAB_TRASH_DIR=$trash_dir
SCARAB_LOG_DIR=$log_dir
SCARAB_DB_BIND_ADDRESS=$db_bind_address
SCARAB_DB_PORT=$db_port
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
            "$source_root/deploy/scarab.env.example" "$runtime_env.example"
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
StartLimitIntervalSec=5min
StartLimitBurst=5

[Service]
Type=oneshot
ExecStart=$OPS_INSTALL_PATH start --instance $instance
ExecStop=$OPS_INSTALL_PATH stop --instance $instance
RemainAfterExit=yes
Restart=on-failure
RestartSec=15s
TimeoutStartSec=180

[Install]
WantedBy=default.target
EOF
    install -o "$service_user" -g "$service_group" -m 0644 "$unit_temporary" "$unit_file"
    rm -f "$unit_temporary"

    local service_uid service_runtime_dir
    service_uid="$(id -u "$service_user")"
    loginctl enable-linger "$service_user" ||
        die "Failed to enable linger for $service_user."
    systemctl start "user@$service_uid.service" ||
        die "Failed to start the systemd user manager for $service_user."
    service_runtime_dir="/run/user/$service_uid"
    [[ -S "$service_runtime_dir/bus" ]] ||
        die "The systemd user bus is unavailable for $service_user."

    local -a service_environment=(
        env "HOME=$service_home" "USER=$service_user" "LOGNAME=$service_user"
        "XDG_RUNTIME_DIR=$service_runtime_dir"
        "DBUS_SESSION_BUS_ADDRESS=unix:path=$service_runtime_dir/bus"
    )
    runuser --user "$service_user" -- \
        "${service_environment[@]}" systemctl --user daemon-reload ||
        die "Failed to reload the systemd user manager for $service_user."
    runuser --user "$service_user" -- \
        "${service_environment[@]}" systemctl --user enable "$instance.service" ||
        die "Failed to enable $instance.service for $service_user."

    if [[ "$instance_installed" == true ]]; then
        local -a update_command=("$INSTALL_PATH" update --instance "$instance")
        if [[ "$build_local" == true ]]; then
            update_command+=(--build-source "$source_root")
        elif [[ "$pull_images" == false ]]; then
            update_command+=(--no-pull)
        fi

        printf 'Refreshed installed files for %s; updating the stack.\n' "$instance"
        runuser --user "$service_user" -- \
            "${service_environment[@]}" "${update_command[@]}"
        printf 'Updated %s environment "%s".\n' "$instance" "$environment_name"
        return
    fi

    printf 'Installed %s environment "%s".\n' "$instance" "$environment_name"
    if [[ "$environment_name" == "production" && ! -e "$runtime_env" ]]; then
        printf 'Create %s from %s and replace every CHANGE_ME value.\n' \
            "$runtime_env" "$runtime_env.example"
    fi
    printf 'Next, run as %s: %s update --instance %s\n' \
        "$service_user" "$INSTALL_PATH" "$instance"
    printf 'Enabled %s.service for automatic startup at boot.\n' "$instance"
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
        [[ -f "$selected_source/deploy/Containerfile.app" ]] ||
            die "Invalid build source: $selected_source"
        compose_with_build "$selected_source" build
    elif [[ "$pull_images" == true ]]; then
        compose pull
    fi

    compose down
    start_stack
    systemctl --user reset-failed "$instance.service"
    systemctl --user start "$instance.service"
}

case "$command_name" in
    install)
        require_command install
        require_command getent
        require_command od
        install_instance
        ;;
    update)
        require_command podman
        require_command systemctl
        load_instance
        update_stack
        ;;
    *)
        die "Unknown command: $command_name"
        ;;
esac