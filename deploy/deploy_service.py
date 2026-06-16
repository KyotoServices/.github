#!/usr/bin/env python3
"""Deploy a pre-built installDist tarball to a systemd service host (Kyoto-API, KyotoBot).

Uploads the release .tar.gz, extracts it (with a timestamped backup of the
previous install), optionally syncs the extracted dir into an app dir, restarts
the systemd service, and verifies: systemctl is-active (+ optional HTTP check or
a 'ready' log line). With --rollback it restores the newest backup and restarts.

Credentials come from KYOTO_CREDS_FILE (see kyoto_deploy.py).
"""

from __future__ import annotations

import argparse
import glob
import os
import posixpath
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kyoto_deploy as kd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--service-name", required=True)
    ap.add_argument("--artifact", help="local .tar.gz (required unless --rollback)")
    ap.add_argument("--inner-dir", required=True, help="top dir name inside the tar (e.g. kyotopvp-api)")
    ap.add_argument("--extract-dir", required=True, help="remote dir to extract into")
    ap.add_argument("--app-dir", default=None, help="if set, sync <extract-dir>/<inner-dir>/ into this dir")
    ap.add_argument("--http-check", default=None, help="optional URL to curl for HTTP 200 after restart")
    ap.add_argument("--log-path", default=None)
    ap.add_argument("--log-ready", default=None, help="log line to wait for after restart")
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args()

    dest = args.app_dir or posixpath.join(args.extract_dir, args.inner_dir)

    ssh = kd.connect(args.host)
    try:
        if args.rollback:
            if not kd.restore_latest_backup(ssh, dest):
                # restore_latest_backup handles single files; for dirs, find newest .bak dir
                _, out, _ = kd.run(ssh, f"ls -1dt {dest}.bak-* 2>/dev/null | head -n1", check=False)
                bak = out.strip()
                if not bak:
                    sys.exit(f"No backup found for {dest}")
                kd.run(ssh, f'rm -rf "{dest}" && cp -a "{bak}" "{dest}"')
                kd._print(f"    restored {dest} from {bak}")
        else:
            if not args.artifact:
                sys.exit("--artifact is required unless --rollback")
            tars = sorted(glob.glob(args.artifact))
            if not tars:
                sys.exit(f"No artifact matched {args.artifact}")
            tar = tars[0]
            remote_tar = f"/tmp/{os.path.basename(tar)}"
            kd._print(f"    uploading {tar} -> {remote_tar}")
            sftp = ssh.open_sftp(); sftp.put(tar, remote_tar); sftp.close()
            staging = f"/tmp/kyoto-deploy-{args.service_name}"
            kd.run(ssh, f'rm -rf "{staging}" && mkdir -p "{staging}" && tar -xzf "{remote_tar}" -C "{staging}"')
            extracted = posixpath.join(staging, args.inner_dir)
            if args.app_dir:
                # sync the install contents into the app dir, backing up the old one
                if kd.remote_path_exists(ssh, dest):
                    kd.run(ssh, f'mv "{dest}" "{dest}{kd._backup_suffix()}"')
                kd.run(ssh, f'mkdir -p "{dest}" && cp -a "{extracted}/." "{dest}/"')
            else:
                if kd.remote_path_exists(ssh, dest):
                    kd.run(ssh, f'mv "{dest}" "{dest}{kd._backup_suffix()}"')
                kd.run(ssh, f'mkdir -p "$(dirname "{dest}")" && cp -a "{extracted}" "{dest}"')
            kd.run(ssh, f'chmod +x "{dest}/bin/"* 2>/dev/null; rm -f "{remote_tar}"; rm -rf "{staging}"', check=False)

        kd.restart_service(ssh, args.service_name)

        status, out, _ = kd.run(ssh, f"sudo systemctl is-active {args.service_name}", check=False)
        if out.strip() != "active":
            sys.exit(f"Service {args.service_name} is not active after restart (got: {out.strip()})")
        kd._print(f"    {args.service_name} is active")

        if args.log_path and args.log_ready:
            if not kd.wait_for_log_match(ssh, args.log_path, args.log_ready, f"'{args.log_ready}' in {args.log_path}"):
                sys.exit(f"Did not see '{args.log_ready}' in {args.log_path}")

        if args.http_check:
            kd.wait_for_log_match  # noop ref
            _, code, _ = kd.run(ssh, f"sleep 3; curl -s -o /dev/null -w '%{{http_code}}' {args.http_check}", check=False)
            if code.strip() != "200":
                sys.exit(f"HTTP check {args.http_check} returned {code.strip()} (expected 200)")
            kd._print(f"    HTTP check {args.http_check} -> 200")

        kd._print(f"\n{'Rolled back' if args.rollback else 'Deployed'} {args.service_name} on {args.host}")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
