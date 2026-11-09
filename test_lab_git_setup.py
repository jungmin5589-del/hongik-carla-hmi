"""Real temporary Git repositories exercise non-destructive lab bootstrapping."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from lab_git_setup import find_baseline, git, read_manifest, setup


class LabGitSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hongik-git-test-")
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.remote = root / "remote"
        self.remote.mkdir()
        subprocess.run(["git", "init", "-b", "main", str(self.remote)],
                       capture_output=True, check=True)
        git(self.remote, "config", "user.name", "Fixture")
        git(self.remote, "config", "user.email", "fixture@example.invalid")
        git(self.remote, "config", "core.autocrlf", "false")
        initial = {".gitignore": b"*\n!/.gitignore\n!/*.py\n",
                   "native_carla.py": b"version = 'delivered'\n",
                   "repo_safety.py": b"# fixture safety audit\n"}
        self.live = root / "Lab 한글 폴더" / "live"
        self.live.mkdir(parents=True)
        manifest = []
        for name, content in initial.items():
            (self.remote / name).write_bytes(content)
            (self.live / name).write_bytes(content)
            manifest.append({"path": "live/" + name,
                             "sha256": hashlib.sha256(content).hexdigest()})
        self.manifest = self.live.parent / "SOURCE-MANIFEST.json"
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        git(self.remote, "add", ".gitignore", "native_carla.py", "repo_safety.py")
        git(self.remote, "commit", "-m", "Delivered base")
        self.base = git(self.remote, "rev-parse", "HEAD").decode().strip()
        # A later commit has exactly the same filenames but different content.
        (self.remote / "native_carla.py").write_text("version = 'newer-main'\n")
        git(self.remote, "commit", "-am", "New remote version")
        (self.live / "native_carla.py").write_text("version = 'lab-websocket'\n")
        (self.live / "lab.local.json").write_text('{"private":true}')
        (self.live / "ui_assets").mkdir()
        (self.live / "ui_assets" / "runtime.bin").write_bytes(b"runtime remains")

    def snapshot(self):
        return {str(p.relative_to(self.live)): p.read_bytes()
                for p in self.live.rglob("*") if p.is_file() and ".git" not in p.parts}

    def test_connect_preserves_working_files_and_finds_exact_base(self):
        before = self.snapshot()
        result = setup(self.live, remote=str(self.remote))
        self.assertEqual(result["baseline"], self.base)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(git(self.live, "rev-parse", "HEAD").decode().strip(), self.base)
        self.assertEqual(git(self.live, "branch", "--show-current").strip(),
                         b"codex/lab-integration")
        self.assertEqual(git(self.live, "diff", "--name-only").strip(), b"native_carla.py")
        self.assertEqual(git(self.live, "diff", "--cached", "--name-only"), b"")
        ignored = git(self.live, "check-ignore", "lab.local.json", "ui_assets/runtime.bin")
        self.assertIn(b"lab.local.json", ignored)
        self.assertIn(b"ui_assets/runtime.bin", ignored)
        self.assertEqual(git(self.live, "config", "pull.ff").strip(), b"only")

    def test_existing_repo_does_not_change_head_or_config(self):
        setup(self.live, remote=str(self.remote))
        git(self.live, "config", "pull.ff", "false")
        head = git(self.live, "rev-parse", "HEAD")
        result = setup(self.live, remote=str(self.remote))
        self.assertEqual(result["status"], "already-configured")
        self.assertEqual(head, git(self.live, "rev-parse", "HEAD"))
        self.assertEqual(git(self.live, "config", "pull.ff").strip(), b"false")

    def test_unknown_manifest_does_not_install_git(self):
        manifest = json.loads(self.manifest.read_text())
        manifest[1]["sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(manifest))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "No exact"):
            setup(self.live, remote=str(self.remote))
        self.assertFalse((self.live / ".git").exists())
        self.assertEqual(before, self.snapshot())

    def test_changed_ignore_does_not_install_git(self):
        (self.live / ".gitignore").write_text("# changed exclusion policy\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "Field .gitignore differs"):
            setup(self.live, remote=str(self.remote))
        self.assertFalse((self.live / ".git").exists())
        self.assertEqual(before, self.snapshot())

    def test_malformed_manifest_does_not_clone(self):
        self.manifest.write_text('[{"path":"live/../x","sha256":"' + "0" * 64 + '"}]')
        with self.assertRaisesRegex(ValueError, "Invalid"):
            read_manifest(self.manifest)
        self.assertFalse((self.live / ".git").exists())


if __name__ == "__main__":
    unittest.main()
