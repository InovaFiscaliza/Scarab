"""Tests for the deployment bootstrap entry points."""

from __future__ import annotations

import os
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_SCRIPT = REPOSITORY_ROOT / "deploy" / "scarab-bootstrap.sh"
DEPLOY_SCRIPT = REPOSITORY_ROOT / "deploy" / "scarab-deploy.sh"
OPS_SCRIPT = REPOSITORY_ROOT / "deploy" / "scarab-ops.sh"
RUNTIME_LIBRARY = REPOSITORY_ROOT / "deploy" / "lib" / "scarab-runtime.sh"
BATCH_SCRIPT = REPOSITORY_ROOT / "deploy" / "scarab-bootstrap.bat"
EXE_BATCH_SCRIPT = REPOSITORY_ROOT / "examples" / "src" / "exe.bat"
EXE_SHELL_SCRIPT = REPOSITORY_ROOT / "examples" / "src" / "exe.sh"
MOUNT_HOST_VOLUMES_SCRIPT = REPOSITORY_ROOT / "deploy" / "mount-host-volumes.sh"
SHARE_SANDBOX_SCRIPT = REPOSITORY_ROOT / "examples" / "src" / "share-sandbox.bat"
POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt",
    reason="fake POSIX command paths cannot be passed through the Windows WSL launcher",
)


def _write_executable(path: Path, contents: str) -> None:
    path.write_text(textwrap.dedent(contents).lstrip(), encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def bootstrap_environment(tmp_path: Path) -> dict[str, str]:
    """Provide deterministic stand-ins for host, privilege, and network tools."""
    fake_bin = tmp_path / "bin"
    fake_home = tmp_path / "home"
    fake_bin.mkdir()
    fake_home.mkdir()

    _write_executable(
        fake_bin / "uname",
        """
        #!/usr/bin/env bash
        printf 'Linux\n'
        """,
    )
    _write_executable(
        fake_bin / "id",
        """
        #!/usr/bin/env bash
        case "${1:-}" in
            -u) printf '1000\n' ;;
            -un) printf 'testuser\n' ;;
        esac
        """,
    )
    _write_executable(
        fake_bin / "getent",
        """
        #!/usr/bin/env bash
        printf 'testuser:x:1000:1000::%s:/bin/bash\n' "$FAKE_SERVICE_HOME"
        """,
    )
    _write_executable(
        fake_bin / "ip",
        """
        #!/usr/bin/env bash
        printf '2: eth0    inet 192.0.2.10/24 brd 192.0.2.255 scope global eth0\\n'
        """,
    )
    _write_executable(
        fake_bin / "sudo",
        """
        #!/usr/bin/env bash
        if [[ "${1:-}" == "-v" ]]; then
            [[ "${FAKE_SUDO_FAIL:-false}" != true ]]
            exit
        fi
        if [[ "${1:-}" == "-n" ]]; then
            shift
            exec "$@"
        fi
        if [[ "${1:-}" == "--" ]]; then
            shift
            exec "$@"
        fi
        printf 'Unexpected fake sudo arguments: %s\n' "$*" >&2
        exit 2
        """,
    )
    _write_executable(
        fake_bin / "podman",
        """
        #!/usr/bin/env bash
        exit 0
        """,
    )
    for command in ("loginctl", "runuser", "systemctl"):
        _write_executable(
            fake_bin / command,
            """
            #!/usr/bin/env bash
            exit 0
            """,
        )
    _write_executable(
        fake_bin / "curl",
        """
        #!/usr/bin/env bash
        printf '%s' "$FAKE_RELEASE_URL"
        """,
    )
    deploy_stub = tmp_path / "deploy-stub.sh"
    _write_executable(
        deploy_stub,
        """
        #!/usr/bin/env bash
        printf '%s\n' "$@" >"$FAKE_DEPLOY_CAPTURE"
        """,
    )
    _write_executable(
        fake_bin / "git",
        """
        #!/usr/bin/env bash
        if [[ "${1:-}" == "check-ref-format" ]]; then
            exit 0
        fi
        [[ "${1:-}" == "clone" ]] || exit 2
        printf '%s\n' "$@" >"$FAKE_GIT_CAPTURE"
        checkout="${!#}"
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
            mkdir -p "$checkout/$(dirname "$required_path")"
            : >"$checkout/$required_path"
        done
        cp "$FAKE_DEPLOY_STUB" "$checkout/deploy/scarab-deploy.sh"
        """,
    )

    environment = os.environ.copy()
    environment.update(
        {
            "FAKE_DEPLOY_CAPTURE": str(tmp_path / "deploy-arguments.txt"),
            "FAKE_DEPLOY_STUB": str(deploy_stub),
            "FAKE_GIT_CAPTURE": str(tmp_path / "git-arguments.txt"),
            "FAKE_RELEASE_URL": (
                "https://github.com/InovaFiscaliza/Scarab/releases/tag/v9.9.9"
            ),
            "FAKE_SERVICE_HOME": str(fake_home),
            "HOME": str(fake_home),
            "PATH": f"{fake_bin}{os.pathsep}{environment['PATH']}",
        }
    )
    return environment


def _run_bootstrap(
    environment: dict[str, str], *arguments: str
) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available")
    return subprocess.run(
        [
            bash,
            str(BOOTSTRAP_SCRIPT),
            "--db-bind-address",
            "192.0.2.10",
            *arguments,
        ],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )


def test_shell_entry_points_have_valid_bash_syntax() -> None:
    """Deployment and operations entry points parse before host operations begin."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available")
    subprocess.run(
        [
            bash,
            "-n",
            "deploy/scarab-bootstrap.sh",
            "deploy/scarab-deploy.sh",
            "deploy/scarab-ops.sh",
            "deploy/lib/scarab-runtime.sh",
            "deploy/mount-host-volumes.sh",
            "examples/src/exe.sh",
        ],
        check=True,
        cwd=REPOSITORY_ROOT,
    )


def test_existing_stack_starts_application_after_database_provisioning() -> None:
    """Booting existing containers honors the database dependency order."""
    contents = RUNTIME_LIBRARY.read_text(encoding="utf-8")
    start_stack = contents[contents.index("start_stack() {") :]
    start_stack = start_stack[: start_stack.index("\n}\n")]

    expected_order = [
        'podman start "$db_container"',
        "wait_for_database",
        "provision_application_role",
        'podman start "$app_container"',
        "verify_stack",
    ]
    positions = [start_stack.index(operation) for operation in expected_order]

    assert positions == sorted(positions)


def test_installer_enables_systemd_boot_with_bounded_retry() -> None:
    """Installation makes boot activation mandatory and retries failed starts."""
    contents = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "StartLimitIntervalSec=5min" in contents
    assert "StartLimitBurst=5" in contents
    assert "Restart=on-failure" in contents
    assert "RestartSec=15s" in contents
    assert 'loginctl enable-linger "$service_user"' in contents
    assert 'systemctl --user enable "$instance.service"' in contents
    assert "ExecStart=$OPS_INSTALL_PATH start" in contents
    assert "ExecStop=$OPS_INSTALL_PATH stop" in contents
    assert "Optional systemd activation" not in contents


def test_deploy_cli_only_exposes_install_and_update() -> None:
    """Lifecycle and diagnostics belong to scarab-ops, not scarab-deploy."""
    contents = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    dispatch = contents[contents.index('case "$command_name" in') :]

    assert "install)" in dispatch
    assert "update)" in dispatch
    for command in ("validate", "start", "stop", "status", "logs", "backup", "test"):
        assert f"    {command})" not in dispatch

    assert "test_01.tgz" not in contents
    assert "fixtures_dir" not in contents
    assert (
        '"$source_root/deploy/mount-host-volumes.sh" "$MOUNT_INSTALL_PATH"' in contents
    )


def test_operations_cli_owns_runtime_commands() -> None:
    """The separate operations CLI exposes every non-deployment command."""
    contents = OPS_SCRIPT.read_text(encoding="utf-8")
    dispatch = contents[contents.index('case "$command_name" in') :]

    for command in ("validate", "start", "stop", "restart", "status", "logs", "backup"):
        assert f"    {command})" in dispatch
    assert "    install)" not in dispatch
    assert "    update)" not in dispatch


def test_database_is_published_on_an_explicit_host_address() -> None:
    """PostgreSQL publication requires an installed bind address and port."""
    compose_contents = (REPOSITORY_ROOT / "deploy" / "podman-compose.yml").read_text(
        encoding="utf-8"
    )
    deploy_contents = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert (
        '"${SCARAB_DB_BIND_ADDRESS:?Set SCARAB_DB_BIND_ADDRESS}:'
        '${SCARAB_DB_PORT:?Set SCARAB_DB_PORT}:5432"'
    ) in compose_contents
    assert "SCARAB_DB_BIND_ADDRESS=$db_bind_address" in deploy_contents
    assert "SCARAB_DB_PORT=$db_port" in deploy_contents


def test_bootstrap_preflights_systemd_requirements() -> None:
    """Bootstrap rejects unsupported hosts before cloning deployment sources."""
    contents = BOOTSTRAP_SCRIPT.read_text(encoding="utf-8")

    for command in ("loginctl", "runuser", "systemctl"):
        assert f"require_command {command}" in contents


def test_update_activates_systemd_service_after_starting_stack() -> None:
    """A successful update leaves the user service supervising the stack."""
    contents = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    update_stack = contents[contents.index("update_stack() {") :]
    update_stack = update_stack[: update_stack.index("\n}\n")]

    expected_order = [
        "compose down",
        "start_stack",
        'systemctl --user reset-failed "$instance.service"',
        'systemctl --user start "$instance.service"',
    ]
    positions = [update_stack.index(operation) for operation in expected_order]

    assert positions == sorted(positions)


def test_compose_restarts_both_services_unless_explicitly_stopped() -> None:
    """Podman keeps both long-running services under its restart policy."""
    compose_file = REPOSITORY_ROOT / "deploy" / "podman-compose.yml"
    contents = compose_file.read_text(encoding="utf-8")

    assert contents.count("restart: unless-stopped") == 2


def test_storage_mount_contract_uses_domain_names() -> None:
    """Runtime storage is exposed as independent post, get, and trash mounts."""
    compose_contents = (REPOSITORY_ROOT / "deploy" / "podman-compose.yml").read_text(
        encoding="utf-8"
    )
    deploy_contents = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    runtime_contents = RUNTIME_LIBRARY.read_text(encoding="utf-8")

    expected_mounts = (
        '"${SCARAB_POST_DIR:?Set SCARAB_POST_DIR}:/mnt/post:Z"',
        '"${SCARAB_GET_DIR:?Set SCARAB_GET_DIR}:/mnt/get:Z"',
        '"${SCARAB_TRASH_DIR:?Set SCARAB_TRASH_DIR}:/mnt/trash:Z"',
    )
    for mount in expected_mounts:
        assert mount in compose_contents

    expected_host_directories = (
        'post_dir="$storage_root/post"',
        'get_dir="$storage_root/get"',
        'trash_dir="$storage_root/trash"',
    )
    for directory in expected_host_directories:
        assert directory in runtime_contents

    expected_environment = (
        "SCARAB_POST_DIR=$post_dir",
        "SCARAB_GET_DIR=$get_dir",
        "SCARAB_TRASH_DIR=$trash_dir",
    )
    for variable in expected_environment:
        assert variable in deploy_contents

    combined_contents = compose_contents + deploy_contents + runtime_contents
    assert "/mnt/share" not in combined_contents
    assert "SCARAB_SHARE" not in combined_contents


@POSIX_ONLY
def test_latest_release_omits_unspecified_instance(
    bootstrap_environment: dict[str, str],
) -> None:
    """Default release mode leaves instance selection to scarab-deploy."""
    result = _run_bootstrap(
        bootstrap_environment,
        "--app-image",
        "registry.example/scarab/app:1.0",
        "--db-image",
        "registry.example/scarab/db:1.0",
    )

    assert result.returncode == 0, result.stderr
    deploy_arguments = (
        Path(bootstrap_environment["FAKE_DEPLOY_CAPTURE"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    git_arguments = (
        Path(bootstrap_environment["FAKE_GIT_CAPTURE"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert "--instance" not in deploy_arguments
    assert deploy_arguments[:5] == [
        "install",
        "--environment",
        "test",
        "--service-user",
        "testuser",
    ]
    assert git_arguments[git_arguments.index("--branch") + 1] == "v9.9.9"


@POSIX_ONLY
def test_branch_forwards_explicit_instance(
    bootstrap_environment: dict[str, str],
) -> None:
    """Branch and instance selections reach clone and deploy unchanged."""
    result = _run_bootstrap(
        bootstrap_environment,
        "--branch",
        "rewrite/postgres-architecture",
        "--instance",
        "scarab-test",
    )

    assert result.returncode == 0, result.stderr
    deploy_arguments = (
        Path(bootstrap_environment["FAKE_DEPLOY_CAPTURE"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    git_arguments = (
        Path(bootstrap_environment["FAKE_GIT_CAPTURE"])
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert deploy_arguments[deploy_arguments.index("--instance") + 1] == "scarab-test"
    assert (
        git_arguments[git_arguments.index("--branch") + 1]
        == "rewrite/postgres-architecture"
    )


@POSIX_ONLY
def test_check_mode_validates_without_running_deploy(
    bootstrap_environment: dict[str, str],
) -> None:
    """Check mode clones and validates the source but does not install it."""
    result = _run_bootstrap(
        bootstrap_environment,
        "--branch",
        "rewrite/postgres-architecture",
        "--check",
    )

    assert result.returncode == 0, result.stderr
    assert "Bootstrap checks passed" in result.stdout
    assert not Path(bootstrap_environment["FAKE_DEPLOY_CAPTURE"]).exists()


@POSIX_ONLY
def test_bootstrap_stops_when_sudo_validation_fails(
    bootstrap_environment: dict[str, str],
) -> None:
    """No repository is cloned when the operator lacks installation privileges."""
    bootstrap_environment["FAKE_SUDO_FAIL"] = "true"

    result = _run_bootstrap(
        bootstrap_environment,
        "--branch",
        "rewrite/postgres-architecture",
    )

    assert result.returncode != 0
    assert "requires sudo access" in result.stderr
    assert not Path(bootstrap_environment["FAKE_GIT_CAPTURE"]).exists()


@POSIX_ONLY
@pytest.mark.parametrize("address", ["0.0.0.0", "127.0.0.1", "224.0.0.1"])
def test_bootstrap_rejects_non_remote_database_addresses(
    bootstrap_environment: dict[str, str], address: str
) -> None:
    """Wildcard, loopback, and multicast addresses cannot publish PostgreSQL."""
    result = _run_bootstrap(
        bootstrap_environment,
        "--db-bind-address",
        address,
        "--check",
    )

    assert result.returncode != 0
    assert "non-loopback unicast IPv4" in result.stderr
    assert not Path(bootstrap_environment["FAKE_GIT_CAPTURE"]).exists()


def test_windows_launcher_conditionally_forwards_instance() -> None:
    """The Windows wrapper does not synthesize an instance argument."""
    contents = BATCH_SCRIPT.read_text(encoding="utf-8")
    assert (
        'if defined INSTANCE set "REMOTE_ARGUMENTS=!REMOTE_ARGUMENTS! '
        '--instance !INSTANCE!"'
    ) in contents


def test_remote_sandbox_reset_is_explicit_and_test_only() -> None:
    """The scenario executor cannot reset production or run without confirmation."""
    contents = EXE_SHELL_SCRIPT.read_text(encoding="utf-8")

    assert '[[ "$SCARAB_ENVIRONMENT" == "test" ]]' in contents
    assert '[[ "$confirm_reset" == "$instance" ]]' in contents
    assert '[[ "$SCARAB_POSTGRES_DIR" == "$postgres_dir" ]]' in contents
    assert '[[ "$SCARAB_POST_DIR" == "$post_dir" ]]' in contents
    assert '[[ "$SCARAB_GET_DIR" == "$get_dir" ]]' in contents
    assert '[[ "$SCARAB_TRASH_DIR" == "$trash_dir" ]]' in contents
    assert 'temporary="$sandbox_dir/.$filename.uploading"' in contents
    assert 'for fixture in "${fixtures[@]}"' in contents
    assert "nome_original_arquivo" in contents
    assert "mensagem_erro" in contents
    assert "scarab-deploy test" not in contents


def test_sandbox_mount_supports_modern_and_legacy_credentials() -> None:
    """CIFS credentials use encrypted storage or an explicit protected fallback."""
    contents = MOUNT_HOST_VOLUMES_SCRIPT.read_text(encoding="utf-8")

    assert "systemd-creds encrypt" in contents
    assert "LoadCredentialEncrypted=cifs:" in contents
    assert "credential_reference='${CREDENTIALS_DIRECTORY}/cifs'" in contents
    assert "credentials=$credential_reference" in contents
    assert 'chmod 0600 "$credential_plaintext"' in contents
    assert 'rm -f -- "$credential_plaintext" "$unit_temporary"' in contents
    assert "--with-key=host" in contents
    assert 'systemctl enable --now "$unit_name"' in contents
    assert '[[ -z "$domain" || "$domain" =~' in contents
    assert 'legacy_credential_dir="$etc_dir/.credentials"' in contents
    assert 'legacy_credential_file="$legacy_credential_dir/.cifs"' in contents
    assert 'install -d -o root -g root -m 0700 "$legacy_credential_dir"' in contents
    assert "install -o root -g root -m 0600" in contents
    assert "--legacy" in contents
    assert "mount.cifs is required; install the cifs-utils package first" in contents
    assert "mount.cifs -V" in contents
    assert "--cifs-version" not in contents
    assert "vers=$cifs_version" not in contents


def test_sandbox_mount_help_labels_mandatory_and_optional_arguments() -> None:
    """Help clearly separates required values from optional behavior switches."""
    contents = MOUNT_HOST_VOLUMES_SCRIPT.read_text(encoding="utf-8")

    assert "Mandatory arguments:" in contents
    assert "Optional arguments:" in contents
    assert "--legacy" in contents
    assert "--cifs-version" not in contents


@POSIX_ONLY
def test_sandbox_mount_requires_modern_systemd_or_legacy_mode(tmp_path: Path) -> None:
    """RHEL 8-style systemd is rejected unless protected legacy storage is explicit."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(
        fake_bin / "id",
        """
        #!/usr/bin/env bash
        case "${1:-}" in
            -u) [[ "$#" -eq 1 ]] && printf '0\n' || printf '1000\n' ;;
            -g) printf '1000\n' ;;
            -gn) printf 'testgroup\n' ;;
            *) exit 0 ;;
        esac
        """,
    )
    _write_executable(
        fake_bin / "mount.cifs",
        """
        #!/usr/bin/env bash
        [[ "${1:-}" == "-V" ]] && printf 'mount.cifs version: 6.8\n'
        exit 0
        """,
    )
    _write_executable(
        fake_bin / "systemctl",
        """
        #!/usr/bin/env bash
        [[ "${1:-}" == "--version" ]] && printf 'systemd 239 (239-82.el8)\n'
        exit 0
        """,
    )
    for command in ("getent", "install", "mount", "mountpoint", "runuser", "umount"):
        _write_executable(fake_bin / command, "#!/usr/bin/env bash\nexit 0\n")

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    arguments = [
        shutil.which("bash") or "bash",
        str(MOUNT_HOST_VOLUMES_SCRIPT),
        "--instance",
        "parser-test",
        "--server",
        "192.0.2.20",
        "--share",
        "ScarabSandbox",
        "--username",
        "testuser",
        "--service-user",
        "testuser",
        "--confirm-mount",
        "parser-test",
    ]
    modern_result = subprocess.run(
        arguments,
        capture_output=True,
        env=environment,
        text=True,
        check=False,
    )
    legacy_result = subprocess.run(
        [*arguments, "--legacy"],
        capture_output=True,
        env=environment,
        text=True,
        check=False,
    )
    _write_executable(
        fake_bin / "systemctl",
        """
        #!/usr/bin/env bash
        [[ "${1:-}" == "--version" ]] && printf 'systemd 257 (257.13)\n'
        exit 0
        """,
    )
    missing_creds_result = subprocess.run(
        arguments,
        capture_output=True,
        env=environment,
        text=True,
        check=False,
    )

    assert modern_result.returncode != 0
    assert "systemd 250 or newer" in modern_result.stderr
    assert "--legacy" in modern_result.stderr
    assert legacy_result.returncode != 0
    assert "Scarab instance is not installed" in legacy_result.stderr
    assert "systemd-creds" not in legacy_result.stderr
    assert "mount.cifs version: 6.8" in legacy_result.stdout
    assert missing_creds_result.returncode != 0
    assert "systemd-creds is required" in missing_creds_result.stderr
    assert "--legacy" in missing_creds_result.stderr


def test_windows_executor_checks_remote_database_access() -> None:
    """Windows validates TCP unconditionally and uses psql when configured."""
    contents = EXE_BATCH_SCRIPT.read_text(encoding="utf-8")

    assert "Test-NetConnection" in contents
    assert "PGPASSFILE" in contents
    assert "psql.exe" in contents
    assert "exe.sh" in contents
    assert "scarab-ops !OPERATION!" in contents

    tasks_contents = (REPOSITORY_ROOT / ".vscode" / "tasks.json").read_text(
        encoding="utf-8"
    )
    assert '"--db-port"' in tasks_contents
    assert '"${input:scarabDbPort}"' in tasks_contents


def test_windows_share_helper_publishes_only_the_sandbox() -> None:
    """The SMB helper shares examples/sandbox rather than the repository root."""
    contents = SHARE_SANDBOX_SCRIPT.read_text(encoding="utf-8")

    assert "New-SmbShare" in contents
    assert "examples\\sandbox" in contents
