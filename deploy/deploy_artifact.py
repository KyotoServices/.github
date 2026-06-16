#!/usr/bin/env python3
"""Deploy a pre-built plugin jar to a Pelican stack — no build step.

Used by the CD pipeline: the release workflow already built and published the
jar; this uploads that exact artifact to the target container, restarts it, and
waits for the 'Enabling <plugin>' log line. With --rollback it instead restores
the most recent backup of the target jar (and restarts).

Credentials come from KYOTO_CREDS_FILE (see kyoto_deploy.py).
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kyoto_deploy as kd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True, help="target host IP")
    ap.add_argument("--remote-dir", required=True, help="plugins dir (embeds the Pelican UUID)")
    ap.add_argument("--plugin-name", required=True, help="plugin name for log check + stale glob")
    ap.add_argument("--log-path", required=True)
    ap.add_argument("--artifact", help="local jar path or glob (required unless --rollback)")
    ap.add_argument("--container-fallback", default=None)
    ap.add_argument("--name-glob", default=None, help="defaults to <plugin>-*.jar")
    ap.add_argument("--rollback", action="store_true", help="restore newest backup instead of deploying")
    args = ap.parse_args()

    name_glob = args.name_glob or f"{args.plugin_name}-*.jar"
    ssh = kd.connect(args.host)
    try:
        if args.rollback:
            _, out, _ = kd.run(ssh, f"ls -1t {args.remote_dir}/{name_glob} 2>/dev/null | head -n1", check=False)
            target = out.strip()
            if not target:
                sys.exit(f"No {name_glob} found in {args.remote_dir} to roll back")
            if not kd.restore_latest_backup(ssh, target):
                sys.exit("No backup to restore")
        else:
            if not args.artifact:
                sys.exit("--artifact is required unless --rollback")
            jars = [j for j in sorted(glob.glob(args.artifact))
                    if not j.endswith(("-sources.jar", "-javadoc.jar", "-plain.jar"))]
            if not jars:
                sys.exit(f"No artifact matched {args.artifact}")
            jar = jars[0]
            remote_path = f"{args.remote_dir}/{os.path.basename(jar)}"
            kd.upload_file_with_backup(ssh, jar, remote_path)
            kd.remove_stale_plugin_jars(ssh, args.remote_dir, os.path.basename(jar), name_glob)

        container = kd.resolve_container(ssh, kd.extract_uuid(args.remote_dir), fallback=args.container_fallback or None)
        kd.restart_container(ssh, container)
        if not kd.grep_log_for_enable(ssh, args.log_path, args.plugin_name):
            sys.exit(f"Did not see 'Enabling {args.plugin_name}' within timeout")
        kd._print(f"\n{'Rolled back' if args.rollback else 'Deployed'} {args.plugin_name} on {args.host}")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
