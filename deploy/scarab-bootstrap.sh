#!/usr/bin/env bash

set -Eeuo pipefail

readonly REPOSITORY_URL="https://github.com/InovaFiscaliza/Scarab.git"
readonly LATEST_RELEASE_URL="https://github.com/InovaFiscaliza/Scarab/releases/latest"
readonly RELEASE_TAG_URL_PREFIX="https://github.com/InovaFiscaliza/Scarab/releases/tag/"

usage() {
    cat <<'EOF'
Usage:
  scarab-bootstrap.sh [--branch BRANCH] [--instance NAME]
      [--environment test|production] [--service-user USER]
    [--app-image IMAGE] [--db-image IMAGE]
    [--db-bind-address IPV4] [--db-port PORT]

Options and defaults:
  No mandatory arguments in the default test mode. The bootstrap detects a
      single usable non-loopback IPv4 address automatically. When multiple
      addresses are available, --db-bind-address is required.
  --branch BRANCH
      Clone a specific branch instead of the latest published GitHub release.
  --instance NAME
      Pass the instance to scarab-deploy. Omitted by default, so scarab-deploy
      uses its own default instance (scarab).
  --environment test|production
      Deployment environment (default: test).
  --service-user USER
      Rootless service account (default: invoking user, or SUDO_USER when root).
  --app-image IMAGE, --db-image IMAGE
      Optional immutable images. Both are required for production.
  --db-bind-address IPV4
      Optional non-loopback unicast IPv4 address assigned to this host. If
      omitted, a single such address is detected automatically; multiple
      addresses require this option.
  --db-port PORT
      Host port published to PostgreSQL container port 5432 (default: 5432).
  --check
      Run all prerequisite, access, clone, and source checks without installing.
  -h, --help
      Show this help text.

The selected source is cloned into a temporary directory under the service
user's home. A checkout used for local test builds is retained because later
scarab-deploy update commands need it; immutable-image checkouts are removed.
EOF
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

resolve_latest_release_url() {
    if command -v curl >/dev/null 2>&1; then
        curl --fail --silent --show-error --location --output /dev/null \
            --write-out '%{url_effective}' "$LATEST_RELEASE_URL"
    elif command -v python3 >/dev/null 2>&1; then
        python3 - "$LATEST_RELEASE_URL" <<'PY'
import sys
import urllib.request

request = urllib.request.Request(
    sys.argv[1],
    headers={"User-Agent": "Scarab bootstrap"},
)
with urllib.request.urlopen(request, timeout=30) as response:
    print(response.geturl())
PY
    elif command -v wget >/dev/null 2>&1; then
        wget --quiet --server-response --spider "$LATEST_RELEASE_URL" 2>&1 |
            awk 'tolower($1) == "location:" { url = $2 } END { sub(/\r$/, "", url); print url }'
    else
        die "Resolving the latest release requires curl, python3, or wget."
    fi
}

validate_value() {
    local label="$1"
    local value="$2"
    [[ -n "$value" && "$value" != -* && "$value" != *$'\n'* && "$value" != *$'\r'* ]] ||
        die "$label must be a non-empty single-line value that does not begin with '-'."
}

validate_ipv4_address() {
    local address="$1"
    local -a octets
    [[ "$address" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
        die "Database bind address must be an IPv4 literal: $address"
    IFS=. read -r -a octets <<<"$address"
    local octet
    for octet in "${octets[@]}"; do
        ((10#$octet <= 255)) || die "Invalid IPv4 address: $address"
    done
    ((10#${octets[0]} != 0 && 10#${octets[0]} != 127 && 10#${octets[0]} < 224)) ||
        die "Database bind address must be a non-loopback unicast IPv4 address: $address"
}

validate_port() {
    local port="$1"
    [[ "$port" =~ ^[0-9]+$ ]] || die "Database port must be numeric: $port"
    ((10#$port >= 1 && 10#$port <= 65535)) ||
        die "Database port must be between 1 and 65535: $port"
}

resolve_db_bind_address() {
    if [[ -z "$db_bind_address" ]]; then
        local -a addresses
        mapfile -t addresses < <(
            ip -4 -o addr show scope global |
                awk '{split($4, address, "/"); print address[1]}' |
                sort -u
        )
        case "${#addresses[@]}" in
            0)
                die "No non-loopback unicast IPv4 address is assigned to this host."
                ;;
            1)
                db_bind_address="${addresses[0]}"
                printf 'Automatically selected database bind address: %s\n' \
                    "$db_bind_address"
                ;;
            *)
                die "Multiple non-loopback unicast IPv4 addresses are assigned; pass --db-bind-address explicitly: ${addresses[*]}"
                ;;
        esac
    fi

    validate_ipv4_address "$db_bind_address"
    ip -4 -o addr show scope global |
        awk -v expected="$db_bind_address" \
            '{split($4, address, "/"); if (address[1] == expected) found=1} END {exit !found}' ||
        die "Database bind address is not assigned to this host: $db_bind_address"
}

branch=""
instance=""
environment_name="test"
service_user=""
app_image=""
db_image=""
check_only=false
db_bind_address=""
db_port="5432"

while (($#)); do
    case "$1" in
        --branch)
            (($# >= 2)) || die "--branch requires a value."
            branch="$2"
            shift 2
            ;;
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
        --check)
            check_only=true
            shift
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

[[ "$(uname -s)" == "Linux" ]] || die "This bootstrap must run on a Linux host."
[[ "$environment_name" == "test" || "$environment_name" == "production" ]] ||
    die "--environment must be test or production."
validate_port "$db_port"
if [[ -n "$branch" ]]; then
    validate_value "Branch" "$branch"
fi
if [[ -n "$instance" ]]; then
    [[ "$instance" =~ ^[a-z][a-z0-9-]*$ ]] ||
        die "Instance must match ^[a-z][a-z0-9-]*$: $instance"
fi
if [[ -n "$app_image" || -n "$db_image" ]]; then
    [[ -n "$app_image" && -n "$db_image" ]] ||
        die "Provide both --app-image and --db-image, or neither."
    validate_value "Application image" "$app_image"
    validate_value "Database image" "$db_image"
fi
if [[ "$environment_name" == "production" ]]; then
    [[ -n "$app_image" && -n "$db_image" ]] ||
        die "--app-image and --db-image are required for production."
fi

require_command bash
require_command env
require_command git
require_command getent
require_command id
require_command ip
require_command loginctl
require_command mktemp
require_command podman
require_command rm
require_command runuser
require_command systemctl
resolve_db_bind_address
ip -4 -o address show | grep -Fq " $db_bind_address/" ||
    die "Database bind address is not assigned to this host: $db_bind_address"

operator_uid="$(id -u)"
if [[ -z "$service_user" ]]; then
    if [[ "$operator_uid" -eq 0 ]]; then
        [[ -n "${SUDO_USER:-}" ]] ||
            die "--service-user is required when the bootstrap is run directly as root."
        service_user="$SUDO_USER"
    else
        service_user="$(id -un)"
    fi
fi
validate_value "Service user" "$service_user"
id "$service_user" >/dev/null 2>&1 || die "Service user does not exist: $service_user"

service_uid="$(id -u "$service_user")"
[[ "$service_uid" -ne 0 ]] || die "The rootless service user cannot be root."
service_home="$(getent passwd "$service_user" | cut -d: -f6)"
[[ -n "$service_home" && -d "$service_home" ]] ||
    die "Cannot find a home directory for $service_user."

if [[ "$operator_uid" -ne 0 ]]; then
    require_command sudo
    sudo -v || die "The invoking user requires sudo access to install Scarab."
    sudo -n true || die "Unable to confirm cached sudo access."
elif [[ "$operator_uid" != "$service_uid" ]]; then
    require_command runuser
fi

run_as_root() {
    if [[ "$operator_uid" -eq 0 ]]; then
        "$@"
    else
        sudo -- "$@"
    fi
}

run_as_service_user() {
    if [[ "$operator_uid" == "$service_uid" ]]; then
        "$@"
    elif [[ "$operator_uid" -eq 0 ]]; then
        runuser --user "$service_user" -- \
            env "HOME=$service_home" "USER=$service_user" "LOGNAME=$service_user" "$@"
    else
        sudo -u "$service_user" -H -- "$@"
    fi
}

run_as_service_user test -w "$service_home" ||
    die "Service user cannot write to its home directory: $service_home"
run_as_service_user sh -c 'command -v git >/dev/null 2>&1' ||
    die "git is not available to the service user."
run_as_service_user sh -c 'command -v podman >/dev/null 2>&1' ||
    die "podman is not available to the service user."
run_as_service_user podman info >/dev/null ||
    die "Rootless Podman is not usable by $service_user."
run_as_service_user podman compose version >/dev/null ||
    die "A working podman compose provider is required for $service_user."

selected_ref="$branch"
using_latest_release=false
if [[ -z "$selected_ref" ]]; then
    using_latest_release=true
    effective_url="$(resolve_latest_release_url)" ||
        die "Unable to resolve the latest GitHub release."
    [[ "$effective_url" == "$RELEASE_TAG_URL_PREFIX"* ]] ||
        die "Unexpected latest-release URL returned by GitHub: $effective_url"
    selected_ref="${effective_url#"$RELEASE_TAG_URL_PREFIX"}"
    validate_value "Release tag" "$selected_ref"
fi
git check-ref-format --branch "$selected_ref" >/dev/null 2>&1 ||
    die "Invalid Git branch or release tag: $selected_ref"

staging_dir="$(run_as_service_user mktemp -d "$service_home/.scarab-bootstrap.XXXXXX")"
[[ "$staging_dir" == "$service_home/.scarab-bootstrap."* ]] ||
    die "Unexpected staging directory: $staging_dir"
checkout_dir="$staging_dir/repository"
retain_checkout=false

cleanup() {
    local status=$?
    trap - EXIT
    if [[ -n "${staging_dir:-}" && -d "$staging_dir" ]]; then
        if [[ "$status" -ne 0 || "$retain_checkout" != true ]]; then
            if ! run_as_service_user rm -rf -- "$staging_dir"; then
                printf 'WARNING: Could not remove staging directory: %s\n' "$staging_dir" >&2
            fi
        fi
    fi
    exit "$status"
}
trap cleanup EXIT

printf 'Cloning Scarab ref %s into %s\n' "$selected_ref" "$checkout_dir"
run_as_service_user env GIT_TERMINAL_PROMPT=0 \
    git clone --depth 1 --single-branch --branch "$selected_ref" \
    "$REPOSITORY_URL" "$checkout_dir"

required_paths=(
    deploy/scarab-deploy.sh
    deploy/scarab-ops.sh
    deploy/lib/scarab-runtime.sh
    deploy/mount-host-volumes.sh
    deploy/podman-compose.yml
    deploy/podman-compose.build.yml
    deploy/Containerfile.app
    deploy/Containerfile.db
    deploy/scarab.env.example
    config/default_config.json
)
for required_path in "${required_paths[@]}"; do
    if [[ ! -f "$checkout_dir/$required_path" ]]; then
        if [[ "$using_latest_release" == true ]]; then
            die "Latest release $selected_ref lacks $required_path; use --branch for a compatible ref."
        fi
        die "Selected branch $selected_ref lacks required deployment file: $required_path"
    fi
done

if [[ "$check_only" == true ]]; then
    printf 'Bootstrap checks passed for Scarab ref %s and service user %s.\n' \
        "$selected_ref" "$service_user"
    exit 0
fi

deploy_arguments=(
    install
    --environment "$environment_name"
    --service-user "$service_user"
    --source "$checkout_dir"
    --db-bind-address "$db_bind_address"
    --db-port "$db_port"
)
if [[ -n "$instance" ]]; then
    deploy_arguments+=(--instance "$instance")
fi
if [[ -n "$app_image" ]]; then
    deploy_arguments+=(--app-image "$app_image" --db-image "$db_image")
fi

run_as_root bash "$checkout_dir/deploy/scarab-deploy.sh" "${deploy_arguments[@]}"

printf 'Scarab source ref %s was installed successfully.\n' "$selected_ref"
if [[ "$environment_name" == "test" && -z "$app_image" ]]; then
    retain_checkout=true
    printf 'Retained local-build source at %s\n' "$checkout_dir"
    printf 'Run as %s: scarab-deploy update' "$service_user"
    if [[ -n "$instance" ]]; then
        printf ' --instance %s' "$instance"
    fi
    printf '\n'
fi