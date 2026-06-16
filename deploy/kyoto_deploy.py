"""Paramiko helpers for Kyoto CD deploys (runs on the self-hosted runner).

This is the CI/CD twin of the repo-local tools/kyoto_deploy.py used by the
per-project deploy_dev.py scripts. The only behavioural difference: credentials
are read from the path in the KYOTO_CREDS_FILE env var (set to the root-only
creds file placed on the self-hosted runner), so passwords never live in GitHub.
"""

from __future__ import annotations

import os
import posixpath
import re
import sys
import time

import paramiko

# Path to the creds file (host -> user/pass), provided on the self-hosted runner.
# Target hosts are passed in per deploy (workflow inputs); none are hardcoded here.
CREDENTIALS_FILE = os.environ.get("KYOTO_CREDS_FILE", "/opt/kyoto-deploy/creds.md")


def _print(text: str) -> None:
    sys.stdout.write(str(text) + "\n")
    sys.stdout.flush()


def load_credentials(path: str = CREDENTIALS_FILE) -> dict:
    """Parse the `"User"`/`"Pass"` blocks in the creds file into {ip: (user, pass)}."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    creds = {}
    for block in re.split(r"\n(?=\d+\.\d+\.\d+\.\d+)", content):
        host = re.match(r"(\d+\.\d+\.\d+\.\d+)", block.strip())
        user = re.search(r'"User":\s*"([^"]+)"', block)
        pw = re.search(r'"Pass":\s*"([^"]+)"', block)
        if host and user and pw:
            creds[host.group(1)] = (user.group(1), pw.group(1))
    return creds


def connect(host: str) -> paramiko.SSHClient:
    creds = load_credentials()
    if host not in creds:
        raise KeyError(f"No credentials for {host} in {CREDENTIALS_FILE}")
    user, password = creds[host]
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=20)
    return client


def run(ssh: paramiko.SSHClient, command: str, check: bool = True):
    _print(f"    $ {command}")
    _, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    status = stdout.channel.recv_exit_status()
    if out.strip():
        _print(out.rstrip())
    if err.strip():
        _print(err.rstrip())
    if check and status != 0:
        raise RuntimeError(f"Remote command failed (exit {status}): {command}")
    return status, out, err


def remote_path_exists(ssh, remote_path: str) -> bool:
    status, _, _ = run(ssh, f'test -e "{remote_path}"', check=False)
    return status == 0


def _backup_suffix() -> str:
    return time.strftime(".bak-%Y%m%d-%H%M%S")


def upload_file_with_backup(ssh, local_path: str, remote_path: str) -> None:
    if remote_path_exists(ssh, remote_path):
        backup = remote_path + _backup_suffix()
        run(ssh, f'mv "{remote_path}" "{backup}"')
        _print(f"    backed up existing remote file to {backup}")
    sftp = ssh.open_sftp()
    try:
        _print(f"    uploading {local_path} -> {remote_path}")
        sftp.put(local_path, remote_path)
    finally:
        sftp.close()


def remove_stale_plugin_jars(ssh, remote_dir: str, keep_filename: str, name_glob: str) -> None:
    """Back up other jars matching name_glob so the server can't load a duplicate plugin id."""
    _, out, _ = run(ssh, f"ls {remote_dir}/{name_glob} 2>/dev/null", check=False)
    for line in out.splitlines():
        path = line.strip()
        if not path or posixpath.basename(path) == keep_filename:
            continue
        run(ssh, f'mv "{path}" "{path}{_backup_suffix()}"')
        _print(f"    backed up stale duplicate plugin jar {path}")


_UUID_RE = re.compile(
    r"/volumes/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})(?:/|$)"
)


def extract_uuid(remote_path: str) -> str:
    m = _UUID_RE.search(remote_path)
    if not m:
        raise ValueError(f"No Pelican server UUID in path: {remote_path}")
    return m.group(1)


def resolve_container(ssh, uuid: str, fallback: str | None = None) -> str:
    """Resolve the live docker short-ID for a Pelican server by its (stable) UUID name."""
    _, out, _ = run(ssh, f"docker ps --filter name={uuid} --format '{{{{.ID}}}}'", check=False)
    lines = [l.strip() for l in out.splitlines() if l.strip()]
    if lines:
        _print(f"    resolved container {lines[0]} for {uuid}")
        return lines[0]
    if fallback:
        _print(f"    WARNING: no running container named {uuid}; falling back to {fallback}")
        return fallback
    raise RuntimeError(f"No running container matches UUID {uuid} and no fallback given")


def restart_container(ssh, container_id: str) -> None:
    _print(f"    restarting container {container_id}")
    run(ssh, f"docker restart {container_id}")


def restart_service(ssh, service_name: str) -> None:
    _print(f"    restarting service {service_name}")
    run(ssh, f"sudo systemctl restart {service_name}")


def upload_dir_with_backup(ssh, local_dir: str, remote_dir: str) -> None:
    """Upload a local dir tree to remote_dir, renaming any existing dir to a timestamped backup."""
    if remote_path_exists(ssh, remote_dir):
        backup = remote_dir + _backup_suffix()
        run(ssh, f'mv "{remote_dir}" "{backup}"')
        _print(f"    backed up existing remote dir to {backup}")
    run(ssh, f'mkdir -p "{remote_dir}"')
    sftp = ssh.open_sftp()
    try:
        for root, _dirs, files in os.walk(local_dir):
            rel = os.path.relpath(root, local_dir)
            remote_root = remote_dir if rel == "." else posixpath.join(remote_dir, *rel.split(os.sep))
            if rel != ".":
                run(ssh, f'mkdir -p "{remote_root}"', check=False)
            for fname in files:
                sftp.put(os.path.join(root, fname), posixpath.join(remote_root, fname))
        _print(f"    uploaded {local_dir} -> {remote_dir}")
    finally:
        sftp.close()


def wait_for_log_match(ssh, log_path: str, grep_pattern: str, description: str,
                       timeout_seconds: int = 150, poll_interval: int = 10) -> bool:
    _print(f"    waiting up to {timeout_seconds}s for: {description}...")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        time.sleep(poll_interval)
        _, out, _ = run(ssh, f'grep -i "{grep_pattern}" "{log_path}" | tail -n 5', check=False)
        if out.strip():
            _print(f"    OK: {description}")
            return True
    _print(f"    WARNING: timed out after {timeout_seconds}s waiting for: {description}")
    return False


def grep_log_for_enable(ssh, log_path: str, plugin_name: str, timeout_seconds: int = 150) -> bool:
    return wait_for_log_match(ssh, log_path, f"Enabling {plugin_name}",
                              f"'Enabling {plugin_name}' in {log_path}", timeout_seconds)


def restore_latest_backup(ssh, remote_path: str) -> bool:
    """Roll back: restore the most recent <remote_path>.bak-* over remote_path."""
    _, out, _ = run(ssh, f"ls -1t {remote_path}.bak-* 2>/dev/null | head -n1", check=False)
    backup = out.strip()
    if not backup:
        _print(f"    no backup found for {remote_path}")
        return False
    run(ssh, f'cp "{backup}" "{remote_path}"')
    _print(f"    restored {remote_path} from {backup}")
    return True
