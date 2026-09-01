#!/usr/bin/env bash

set -Eeuo pipefail

usage() {
    cat <<'EOF'
Usage:
    mount-host-volumes.sh --instance NAME --server HOST --share NAME
      --username USER --service-user USER --confirm-mount NAME
      [--domain DOMAIN] [--legacy]

Mandatory arguments:
  --instance NAME
      Installed Scarab instance whose /srv/NAME directory will be mounted.
  --server HOST
      Windows SMB server hostname or IP address.
  --share NAME
      SMB share containing config.json and post/get/store/trash directories.
  --username USER
      Windows account allowed to access the share.
  --service-user USER
      Rootless Linux account that owns the Scarab instance.
  --confirm-mount NAME
      Must exactly match --instance to authorize replacing its storage mount.

Optional arguments:
  --domain DOMAIN
      Windows domain for the SMB account.
  --legacy
      Store CIFS credentials in /etc/NAME/.credentials/.cifs with root-only
      permissions. Use this on systemd older than 250, including RHEL 8.
      Without this flag, encrypted systemd credentials are required.
  -h, --help
      Show this help text.

The installed mount negotiates the SMB dialect automatically. The script
detects and reports the installed mount.cifs version. The SMB password is read
directly from the terminal. Modern mode stores only encrypted credentials;
legacy mode stores a protected plaintext credential file for compatibility.
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
confirm_mount=""
legacy_mode=false

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
        --confirm-mount)
            (($# >= 2)) || die "--confirm-mount requires a value."
            confirm_mount="$2"
            shift 2
            ;;
        --legacy)
            legacy_mode=true
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

[[ "$(id -u)" -eq 0 ]] || die "Run this script as root."
[[ -n "$instance" && "$instance" =~ ^[a-z][a-z0-9-]*$ ]] || die "Invalid instance."
[[ "$confirm_mount" == "$instance" ]] || die "Pass --confirm-mount $instance to continue."
[[ -n "$server" && "$server" =~ ^[A-Za-z0-9._-]+$ ]] || die "Invalid SMB server."
[[ -n "$share_name" && "$share_name" =~ ^[A-Za-z][A-Za-z0-9_-]*$ ]] || die "Invalid SMB share."
[[ -n "$username" && "$username" != *$'\n'* && "$username" != *$'\r'* ]] || die "Invalid SMB username."
[[ "$service_user" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || die "Invalid service user."
[[ -z "$domain" || "$domain" =~ ^[A-Za-z0-9._-]+$ ]] || die "Invalid SMB domain."

for command in getent install mount mountpoint runuser systemctl umount; do
    require_command "$command"
done
command -v mount.cifs >/dev/null 2>&1 ||
    die "mount.cifs is required; install the cifs-utils package first."
cifs_client_version="$(mount.cifs -V 2>&1)" ||
    die "Could not determine the installed mount.cifs version."
cifs_client_version="${cifs_client_version%%$'\n'*}"
[[ -n "$cifs_client_version" ]] || die "mount.cifs returned an empty version."
printf 'Detected CIFS client: %s. SMB dialect will be negotiated automatically.\n' \
    "$cifs_client_version"

systemd_version_output="$(systemctl --version 2>/dev/null)" ||
    die "Could not determine the installed systemd version."
systemd_version_line="${systemd_version_output%%$'\n'*}"
if [[ "$systemd_version_line" =~ ^systemd[[:space:]]+([0-9]+) ]]; then
    systemd_version="${BASH_REMATCH[1]}"
else
    die "Could not parse the installed systemd version: $systemd_version_line"
fi
if [[ "$legacy_mode" == false && "$systemd_version" -lt 250 ]]; then
    die "Encrypted credentials require systemd 250 or newer (detected $systemd_version). Re-run with --legacy to use a root-only credential file."
fi
if [[ "$legacy_mode" == false ]] && ! command -v systemd-creds >/dev/null 2>&1; then
    die "systemd-creds is required for encrypted credentials. Re-run with --legacy to use a root-only credential file."
fi
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
legacy_credential_dir="$etc_dir/.credentials"
legacy_credential_file="$legacy_credential_dir/.cifs"

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
credential_ciphertext=""
cleanup() {
    local status=$?
    trap - EXIT
    rm -f -- "$credential_plaintext" "$unit_temporary"
    if [[ -n "$credential_ciphertext" ]]; then
        rm -f -- "$credential_ciphertext"
    fi
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

credential_directive=""
credential_mode_description=""
if [[ "$legacy_mode" == true ]]; then
    install -d -o root -g root -m 0700 "$legacy_credential_dir"
    install -o root -g root -m 0600 \
        "$credential_plaintext" "$legacy_credential_file"
    credential_reference="$legacy_credential_file"
    credential_mode_description="protected legacy credentials at $legacy_credential_file"
else
    install -d -o root -g root -m 0700 "$credential_dir"
    credential_ciphertext="$(mktemp)"
    systemd-creds setup
    systemd-creds encrypt --with-key=host --name=cifs \
        "$credential_plaintext" - >"$credential_ciphertext"
    install -o root -g root -m 0600 \
        "$credential_ciphertext" "$credential_encrypted"
    rm -f -- "$credential_ciphertext"
    credential_ciphertext=""
    credential_directive="LoadCredentialEncrypted=cifs:$credential_encrypted"
    credential_mode_description="encrypted systemd credentials"
fi

mount_command="$(command -v mount)"
umount_command="$(command -v umount)"
{
cat <<EOF
[Unit]
Description=Scarab sandbox CIFS mount ($instance)
Wants=network-online.target
After=network-online.target
Before=user@$service_uid.service

[Service]
Type=oneshot
RemainAfterExit=yes
EOF
if [[ -n "$credential_directive" ]]; then
    printf '%s\n' "$credential_directive"
fi
cat <<EOF
ExecStart=$mount_command -t cifs //$server/$share_name $storage_root -o credentials=$credential_reference,uid=$service_uid,gid=$service_gid,forceuid,forcegid,file_mode=0660,dir_mode=0770,nosuid,nodev,noexec
ExecStop=$umount_command $storage_root
TimeoutStartSec=60
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
} >"$unit_temporary"
install -o root -g root -m 0644 "$unit_temporary" "$unit_path"

systemctl daemon-reload
systemctl enable --now "$unit_name"
for required_directory in post get store trash; do
    [[ -d "$storage_root/$required_directory" ]] ||
        die "Mounted share lacks required directory: $required_directory"
done
printf '%s\n' "$storage_root" >"$etc_dir/storage-mount"
chmod 0644 "$etc_dir/storage-mount"
if [[ "$legacy_mode" == true ]]; then
    rm -f -- "$credential_encrypted"
else
    rm -f -- "$legacy_credential_file"
    rmdir "$legacy_credential_dir" 2>/dev/null || true
fi

printf 'Mounted //%s/%s at %s using %s.\n' \
    "$server" "$share_name" "$storage_root" "$credential_mode_description"
printf 'Start the instance with: sudo -iu %s scarab-ops start --instance %s\n' \
    "$service_user" "$instance"