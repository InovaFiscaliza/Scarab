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
BATCH_SCRIPT = REPOSITORY_ROOT / "deploy" / "scarab-bootstrap.bat"
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
            deploy/podman-compose.yml
            deploy/podman-compose.build.yml
            deploy/Containerfile.app
            deploy/Containerfile.db
            deploy/scarab.env.example
            config/default_config.json
            examples/sandbox/config.json
            examples/data/test_01.tgz
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
        [bash, str(BOOTSTRAP_SCRIPT), *arguments],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )


def test_shell_entry_points_have_valid_bash_syntax() -> None:
    """Both Bash entry points parse before any host operations begin."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not available")
    subprocess.run(
        [
            bash,
            "-n",
            "deploy/scarab-bootstrap.sh",
            "deploy/scarab-deploy.sh",
        ],
        check=True,
        cwd=REPOSITORY_ROOT,
    )


def test_existing_stack_starts_application_after_database_provisioning() -> None:
    """Booting existing containers honors the database dependency order."""
    contents = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    start_stack = contents[contents.index("start_stack() {") :]
    start_stack = start_stack[: start_stack.index("\n}\n")]

    expected_order = [
        'podman start "$db_container"',
        "wait_for_database",
        "provision_application_role",
        'podman start "$app_container"',
        "wait_for_application",
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
    assert "Optional systemd activation" not in contents


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


def test_windows_launcher_conditionally_forwards_instance() -> None:
    """The Windows wrapper does not synthesize an instance argument."""
    contents = BATCH_SCRIPT.read_text(encoding="utf-8")
    assert (
        'if defined INSTANCE set "REMOTE_ARGUMENTS=!REMOTE_ARGUMENTS! '
        '--instance !INSTANCE!"'
    ) in contents
