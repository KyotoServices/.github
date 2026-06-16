#!/usr/bin/env python3
"""Deploy a pre-built plugin jar to one or more Pelican stacks — no build step.

Works for Paper plugins (log pattern "Enabling <name>") and Velocity plugins
(e.g. "Loaded plugin kyotoproxy") via --log-pattern. Supports fan-out to many
targets (e.g. KyotoCore -> lobby+practice+sg). With --rollback it restores the
newest backup of the target jar on every target and restarts.

Credentials come from KYOTO_CREDS_FILE (see kyoto_deploy.py).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kyoto_deploy as kd


def _deploy_one(target: dict, jar: str | None, plugin: str, log_pattern: str,
                name_glob: str, rollback: bool) -> bool:
    host = target["host"]
    remote_dir = target["remote_dir"]
    log_path = target["log_path"]
    fallback = target.get("container_fallback") or None
    kd._print(f"\n>>> {plugin} -> {host} ({remote_dir})")
    ssh = kd.connect(host)
    try:
        if rollback:
            _, out, _ = kd.run(ssh, f"ls -1t {remote_dir}/{name_glob} 2>/dev/null | head -n1", check=False)
            target_jar = out.strip()
            if not target_jar or not kd.restore_latest_backup(ssh, target_jar):
                kd._print(f"    no backup to restore on {host}")
                return False
        else:
            remote_path = f"{remote_dir}/{os.path.basename(jar)}"
            kd.upload_file_with_backup(ssh, jar, remote_path)
            kd.remove_stale_plugin_jars(ssh, remote_dir, os.path.basename(jar), name_glob)
        container = kd.resolve_container(ssh, kd.extract_uuid(remote_dir), fallback=fallback)
        kd.restart_container(ssh, container)
        return kd.wait_for_log_match(ssh, log_path, log_pattern,
                                     f"'{log_pattern}' in {log_path}")
    finally:
        ssh.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin-name", required=True, help="plugin name (jar prefix + log substitution)")
    ap.add_argument("--targets", required=True, help="JSON list of {host,remote_dir,log_path,container_fallback?}")
    ap.add_argument("--artifact", help="local jar path/glob (required unless --rollback)")
    ap.add_argument("--log-pattern", default="Enabling {plugin}",
                    help="log line to wait for; {plugin} is substituted")
    ap.add_argument("--name-glob", default=None, help="defaults to <plugin>-*.jar")
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args()

    targets = json.loads(args.targets)
    if not targets:
        sys.exit("No targets given")
    name_glob = args.name_glob or f"{args.plugin_name}-*.jar"
    log_pattern = args.log_pattern.replace("{plugin}", args.plugin_name)

    jar = None
    if not args.rollback:
        if not args.artifact:
            sys.exit("--artifact is required unless --rollback")
        jars = [j for j in sorted(glob.glob(args.artifact))
                if not j.endswith(("-sources.jar", "-javadoc.jar", "-plain.jar"))]
        if not jars:
            sys.exit(f"No artifact matched {args.artifact}")
        jar = jars[0]

    failures = []
    for t in targets:
        ok = _deploy_one(t, jar, args.plugin_name, log_pattern, name_glob, args.rollback)
        if not ok:
            failures.append(t["host"] + " " + t["remote_dir"])

    verb = "Rolled back" if args.rollback else "Deployed"
    kd._print(f"\n{verb} {args.plugin_name} to {len(targets) - len(failures)}/{len(targets)} target(s)")
    if failures:
        sys.exit("FAILED targets:\n  " + "\n  ".join(failures))


if __name__ == "__main__":
    main()
