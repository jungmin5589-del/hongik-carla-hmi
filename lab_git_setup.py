"""Attach Git history to a delivered live folder without checking out any files.

Run from the separate Git-Setup kit. SOURCE-MANIFEST.json identifies the exact
delivered tree; field modifications stay unstaged on codex/lab-integration.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

REMOTE = "https://github.com/jungmin5589-del/hongik-carla-hmi.git"
BRANCH = "codex/lab-integration"


def git(root, *args, data=None):
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(key, None)
    result = subprocess.run(["git", "-C", str(root), *args], input=data,
                            capture_output=True, env=env, timeout=180)
    if result.returncode:
        # Do not echo arbitrary remote/config values or credentials in errors.
        raise RuntimeError("Git operation failed: " + args[0] +
                           " (exit " + str(result.returncode) + ")")
    return result.stdout


def read_manifest(path):
    entries = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("Source manifest must be a nonempty list.")
    expected = {}
    for entry in entries:
        name, digest = entry["path"], entry["sha256"]
        pure = PurePosixPath(name)
        if (not name.startswith("live/") or "\\" in name or
                pure.is_absolute() or ".." in pure.parts or
                not re.fullmatch(r"[a-fA-F0-9]{64}", digest)):
            raise ValueError("Invalid source manifest entry.")
        relative = name[len("live/"):]
        if not relative or relative in expected or ".git" in pure.parts:
            raise ValueError("Duplicate or unsafe source manifest path.")
        expected[relative] = digest.lower()
    if not {".gitignore", "native_carla.py", "repo_safety.py"} <= expected.keys():
        raise ValueError("Manifest does not describe the lab application.")
    return expected


def tree_blobs(repo, commit):
    result = {}
    for record in git(repo, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        mode, kind, oid = header.split()
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            return None
        result[name.decode("utf-8")] = oid.decode("ascii")
    return result


def blob_hashes(repo, blobs):
    names = list(blobs)
    payload = "".join(blobs[name] + "\n" for name in names).encode("ascii")
    stream = io.BytesIO(git(repo, "cat-file", "--batch", data=payload))
    hashes = {}
    for name in names:
        header = stream.readline().split()
        if len(header) != 3 or header[1] != b"blob":
            raise RuntimeError("Could not read source blob.")
        content = stream.read(int(header[2]))
        if stream.read(1) != b"\n":
            raise RuntimeError("Invalid Git blob response.")
        hashes[name] = hashlib.sha256(content).hexdigest()
    return hashes


def find_baseline(repo, expected):
    for commit in git(repo, "rev-list", "origin/main").decode("ascii").splitlines():
        blobs = tree_blobs(repo, commit)
        if blobs is not None and blobs.keys() == expected.keys():
            if blob_hashes(repo, blobs) == expected:
                return commit
    raise ValueError("No exact delivered version matches SOURCE-MANIFEST.json. "
                     "Keep the original manifest; do not guess a baseline.")


def attach_metadata(live, source_git):
    """Only a new .git directory is installed; source files are never moved."""
    live = live.resolve(strict=True)
    destination = live / ".git"
    pending = live / (".git.setup-" + uuid.uuid4().hex)
    # Explicit resolved-boundary checks before the Windows directory rename.
    if (pending.resolve().parent != live or destination.resolve().parent != live
            or destination.name != ".git" or os.path.lexists(destination)):
        raise ValueError("Git metadata target is not a new child of live.")
    shutil.copytree(source_git, pending)
    if pending.resolve().parent != live or os.path.lexists(destination):
        raise ValueError("Git metadata target changed; no files were replaced.")
    os.rename(pending, destination)


def setup(live, manifest=None, remote=REMOTE):
    live = live.resolve(strict=True)
    if os.path.lexists(live / ".git"):
        top = Path(git(live, "rev-parse", "--show-toplevel").decode("utf-8").strip())
        if top.resolve() != live:
            raise ValueError("Existing Git root is not the selected live folder.")
        if git(live, "remote", "get-url", "origin").decode().strip() != remote:
            raise ValueError("Existing origin differs. Review it manually.")
        return {"status": "already-configured", "branch": git(
            live, "branch", "--show-current").decode().strip()}
    for name in ("native_carla.py", "repo_safety.py", ".gitignore"):
        if not (live / name).is_file():
            raise ValueError("Select the delivered live folder (missing " + name + ").")
    # Refuse nesting inside an unrelated repository before creating metadata.
    try:
        git(live, "rev-parse", "--show-toplevel")
    except RuntimeError:
        pass
    else:
        raise ValueError("live is already inside another Git repository.")
    expected = read_manifest(manifest or live.parent / "SOURCE-MANIFEST.json")
    stage = Path(tempfile.mkdtemp(prefix="git-setup-history-", dir=live.parent))
    repo = stage / "history"
    print("Downloading source history; existing application files stay in place.", flush=True)
    git(stage, "clone", "--no-checkout", "--no-tags", "--", remote, str(repo))
    baseline = find_baseline(repo, expected)
    baseline_ignore = git(repo, "show", baseline + ":.gitignore")
    if (live / ".gitignore").read_bytes().replace(b"\r\n", b"\n") != baseline_ignore.replace(b"\r\n", b"\n"):
        raise ValueError("Field .gitignore differs from the delivered baseline. "
                         "Review exclusion rules before connecting Git.")
    git(repo, "branch", BRANCH, baseline)
    git(repo, "symbolic-ref", "HEAD", "refs/heads/" + BRANCH)
    git(repo, "read-tree", baseline)  # Index only: no -u and no checkout.
    git(repo, "config", "core.autocrlf", "false")
    git(repo, "config", "pull.ff", "only")
    git(repo, "config", "fetch.prune", "true")
    attach_metadata(live, repo / ".git")
    return {"status": "connected", "baseline": baseline, "branch": BRANCH,
            "history_backup": str(stage)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = setup(args.live)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        print(git(args.live, "status", "--short").decode("utf-8", errors="replace"))
        print("Next: review changes, set your author identity, commit selected source "
              "files and push the lab branch. Read LAB-GIT-WORKFLOW-KO.md first.")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("SETUP STOPPED: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
