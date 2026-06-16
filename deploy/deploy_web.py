#!/usr/bin/env python3
"""Deploy a pre-built static site zip to an nginx web root.

Unzips the release artifact locally, uploads it to /var/www/<domain> (with a
timestamped backup of the previous deploy), runs `nginx -t`, reloads nginx, and
optionally curls the site. With --rollback it restores the newest backup.

Credentials come from KYOTO_CREDS_FILE (see kyoto_deploy.py).
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kyoto_deploy as kd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--web-dir", required=True, help="remote nginx root, e.g. /var/www/stats.kyotopvp.com")
    ap.add_argument("--artifact", help="local .zip of the built site (required unless --rollback)")
    ap.add_argument("--domain", default=None, help="optional Host header for a curl smoke test")
    ap.add_argument("--rollback", action="store_true")
    args = ap.parse_args()

    ssh = kd.connect(args.host)
    try:
        if args.rollback:
            _, out, _ = kd.run(ssh, f"ls -1dt {args.web_dir}.bak-* 2>/dev/null | head -n1", check=False)
            bak = out.strip()
            if not bak:
                sys.exit(f"No backup found for {args.web_dir}")
            kd.run(ssh, f'rm -rf "{args.web_dir}" && cp -a "{bak}" "{args.web_dir}"')
            kd._print(f"    restored {args.web_dir} from {bak}")
        else:
            if not args.artifact:
                sys.exit("--artifact is required unless --rollback")
            zips = sorted(glob.glob(args.artifact))
            if not zips:
                sys.exit(f"No artifact matched {args.artifact}")
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(zips[0]) as zf:
                    zf.extractall(tmp)
                # if the zip wrapped everything in a single dir, descend into it
                entries = [e for e in os.listdir(tmp) if not e.startswith(".")]
                src = os.path.join(tmp, entries[0]) if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])) else tmp
                if not os.path.exists(os.path.join(src, "index.html")):
                    src = tmp  # fall back to root if index.html isn't in the single subdir
                kd.upload_dir_with_backup(ssh, src, args.web_dir)

        kd.run(ssh, "sudo nginx -t")
        kd.run(ssh, "sudo systemctl reload nginx")
        kd._print("    nginx reloaded")

        if args.domain:
            _, code, _ = kd.run(
                ssh, f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Host: {args.domain}' http://localhost/",
                check=False)
            kd._print(f"    curl {args.domain} -> {code.strip()}")

        kd._print(f"\n{'Rolled back' if args.rollback else 'Deployed'} {args.web_dir} on {args.host}")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
