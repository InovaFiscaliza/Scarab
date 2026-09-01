#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage:
  mount-sandbox.sh --instance NAME --server HOST --share NAME
      --username USER --service-user USER [--domain DOMAIN]
      [--cifs-version VERSION] --confirm-mount NAME

Installs an encrypted-credential systemd service that mounts the Windows
sandbox share over /srv/INSTANCE. Stop the Scarab instance before changing an
existing mount. The SMB password is read from the terminal and is never stored
as plaintext.
EOF
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

instance=""
server=""
share_name=""
username=""
service_user=""
domain=""
cifs_version="3.1.1"
confirm_mount=""

while (($#)); do
    case "$1" in
        --instance)
            (($# >= 2)) || die "--instance requires a value."
            instance="$2"
            shift 2
            ;;
        --server)
            (($# >= 2)) || die "--server requires a value."
            server="$2"
            shift 2
            ;;
        --share)
            (($# >= 2)) || die "--share requires a value."
            share_name="$2"
            shift 2
            ;;
        --username)
            (($# >= 2)) || die "--username requires a value."
            username="$2"
            shift 2
            ;;
        --service-user)
            (($# >= 2)) || die "--service-user requires a value."
            service_user="$2"
            shift 2
            ;;
        --domain)
            (($# >= 2)) || die "--domain requires a value."
            domain="$2"
            shift 2
            ;;
        --cifs-version)
            (($# >= 2)) || die "--cifs-version requires a value."
            cifs_version="$2"
            shift 2
            ;;
        --confirm-mount)
            (($# >= 2)) || die "--confirm-mount requires a value."
            confirm_mount="$2"
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

[[ "$(id -u)" -eq 0 ]] || die "Run this script as root."
[[ -n "$instance" && "$instance" =~ ^[a-z][a-z0-9-]*$ ]] || die "Invalid instance."
[[ "$confirm_mount" == "$instance" ]] || die "Pass --confirm-mount $instance to continue."
[[ -n "$server" && "$server" =~ ^[A-Za-z0-9._-]+$ ]] || die "Invalid SMB server."
[[ -n "$share_name" && "$share_name" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || die "Invalid SMB share."
[[ -n "$username" && "$username" != *$'\n'* && "$username" != *$'\r'* ]] || die "Invalid SMB username."
[[ "$service_user" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || die "Invalid service user."
[[ -z "$domain" || "$domain" =~ ^[A-Za-z0-9._-]+$ ]] || die "Invalid SMB domain."
[[ "$cifs_version" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] || die "Invalid CIFS version."

for command in getent install mount mountpoint runuser systemctl systemd-creds umount; do
    require_command "$command"
done
command -v mount.cifs >/dev/null 2>&1 ||
    die "mount.cifs is required; install the cifs-utils package first."
id "$service_user" >/dev/null 2>&1 || die "Service user does not exist: $service_user"

service_uid="$(id -u "$service_user")"
service_gid="$(id -g "$service_user")"
storage_root="/srv/$instance"
etc_dir="/etc/$instance"
unit_name="$instance-sandbox.service"
unit_path="/etc/systemd/system/$unit_name"
credential_dir="/etc/credstore.encrypted"
credential_encrypted="$credential_dir/scarab-$instance-cifs.cred"
credential_reference='${CREDENTIALS_DIRECTORY}/cifs'

[[ -d "$etc_dir" ]] || die "Scarab instance is not installed: $instance"
install -d -o "$service_user" -g "$(id -gn "$service_user")" -m 0750 "$storage_root"

mount_active=false
if mountpoint -q "$storage_root"; then
    systemctl is-active --quiet "$unit_name" ||
        die "$storage_root is mounted by an unmanaged source; unmount it manually first."
    mount_active=true
elif find "$storage_root" -mindepth 1 ! -type d -print -quit | grep -q .; then
    die "$storage_root contains files; move or remove them before mounting the sandbox."
fi

if [[ -x /usr/local/sbin/scarab-ops && -r "$etc_dir/compose.env" ]]; then
    service_home="$(getent passwd "$service_user" | cut -d: -f6)"
    runuser --user "$service_user" -- \
        env "HOME=$service_home" "USER=$service_user" "LOGNAME=$service_user" \
        "XDG_RUNTIME_DIR=/run/user/$service_uid" \
        /usr/local/sbin/scarab-ops stop --instance "$instance"
fi
if [[ "$mount_active" == true ]]; then
    systemctl stop "$unit_name"
fi
if find "$storage_root" -mindepth 1 ! -type d -print -quit | grep -q .; then
    die "$storage_root contains files below the previous mount; move or remove them before continuing."
fi

[[ -t 0 ]] || die "An interactive terminal is required to read the SMB password."
IFS= read -r -s -p "SMB password for $username: " smb_password
printf '\n'
[[ -n "$smb_password" ]] || die "SMB password cannot be empty."

credential_plaintext="$(mktemp)"
unit_temporary="$(mktemp)"
cleanup() {
    local status=$?
    trap - EXIT
    rm -f -- "$credential_plaintext" "$unit_temporary"
    unset smb_password
    exit "$status"
}
trap cleanup EXIT
chmod 0600 "$credential_plaintext"
{
    printf 'username=%s\n' "$username"
    printf 'password=%s\n' "$smb_password"
    if [[ -n "$domain" ]]; then
        printf 'domain=%s\n' "$domain"
    fi
} >"$credential_plaintext"
unset smb_password

install -d -o root -g root -m 0700 "$credential_dir"
rm -f -- "$credential_encrypted"
systemd-creds setup
systemd-creds encrypt --with-key=host --name=cifs \
    "$credential_plaintext" "$credential_encrypted"
chmod 0600 "$credential_encrypted"

mount_command="$(command -v mount)"
umount_command="$(command -v umount)"
cat >"$unit_temporary" <<EOF
[Unit]
Description=Scarab sandbox CIFS mount ($instance)
Wants=network-online.target
After=network-online.target
Before=user@$service_uid.service

[Service]
Type=oneshot
RemainAfterExit=yes
LoadCredentialEncrypted=cifs:$credential_encrypted
ExecStart=$mount_command -t cifs //$server/$share_name $storage_root -o credentials=$credential_reference,uid=$service_uid,gid=$service_gid,forceuid,forcegid,file_mode=0660,dir_mode=0770,nosuid,nodev,noexec,vers=$cifs_version
ExecStop=$umount_command $storage_root
TimeoutStartSec=60
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
install -o root -g root -m 0644 "$unit_temporary" "$unit_path"

systemctl daemon-reload
systemctl enable --now "$unit_name"
for required_directory in post get store trash; do
    [[ -d "$storage_root/$required_directory" ]] ||
        die "Mounted share lacks required directory: $required_directory"
done
printf '%s\n' "$storage_root" >"$etc_dir/storage-mount"
chmod 0644 "$etc_dir/storage-mount"

printf 'Mounted //%s/%s at %s with encrypted systemd credentials.\n' \
    "$server" "$share_name" "$storage_root"
printf 'Start the instance with: sudo -iu %s scarab-ops start --instance %s\n' \
    "$service_user" "$instance"