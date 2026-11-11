#!/usr/bin/env python3
"""Unit tests for GitEngine, run against throwaway repositories.

    python3 -m unittest discover -s tests
"""

import base64
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Hermetic git: the developer's ~/.gitconfig (pull.rebase, hooks, signing…) must not leak in
os.environ["GIT_CONFIG_GLOBAL"] = os.devnull
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"

from git_engine import GitEngine, DETACHED_HEAD_MSG  # noqa: E402


def sh(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self._tmp.name)
        sh(self.root, "init", "-q", "-b", "main")
        sh(self.root, "config", "user.name", "Test")
        sh(self.root, "config", "user.email", "test@example.com")
        sh(self.root, "config", "commit.gpgsign", "false")
        write(self.root, "base.txt", "base\n")
        sh(self.root, "add", "-A")
        sh(self.root, "commit", "-q", "-m", "init")
        self.git = GitEngine(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def paths(self, group):
        return sorted(x["path"] for x in self.git.get_status_files()[group])


class StatusTests(RepoTestCase):
    def test_paths_with_spaces_quotes_and_unicode(self):
        names = ["with space.txt", 'quo"te.txt', "Документ.md", "dir/sub file.cs"]
        for n in names:
            write(self.root, n, "x\n")
        self.assertEqual(self.paths("untracked"), sorted(names))
        for n in names:
            self.assertTrue(self.git.stage_file(n), n)
        self.assertEqual(self.paths("staged"), sorted(names))
        self.assertEqual(self.paths("untracked"), [])

    def test_staged_and_unstaged_same_file(self):
        write(self.root, "base.txt", "base\nstaged\n")
        self.git.stage_file("base.txt")
        write(self.root, "base.txt", "base\nstaged\nunstaged\n")
        st = self.git.get_status_files()
        self.assertEqual([(x["path"], x["status"], x["lines_add"]) for x in st["staged"]], [("base.txt", "M", 1)])
        self.assertEqual([(x["path"], x["status"], x["lines_add"]) for x in st["unstaged"]], [("base.txt", "M", 1)])

    def test_rename_reports_new_path_once(self):
        sh(self.root, "mv", "base.txt", "renamed file.txt")
        st = self.git.get_status_files()
        self.assertEqual([(x["path"], x["status"]) for x in st["staged"]], [("renamed file.txt", "R")])
        self.assertEqual(st["unstaged"], [])
        self.assertEqual(st["untracked"], [])

    def test_deleted_file(self):
        os.remove(os.path.join(self.root, "base.txt"))
        self.assertEqual([(x["path"], x["status"]) for x in self.git.get_status_files()["unstaged"]],
                         [("base.txt", "D")])

    def test_conflicts_are_reported(self):
        sh(self.root, "switch", "-q", "-c", "other")
        write(self.root, "base.txt", "other\n")
        sh(self.root, "commit", "-q", "-am", "other")
        sh(self.root, "switch", "-q", "main")
        write(self.root, "base.txt", "main\n")
        sh(self.root, "commit", "-q", "-am", "main")
        ok, _ = self.git.merge_branch("other")
        self.assertFalse(ok)
        self.assertTrue(self.git.is_merging())
        st = self.git.get_status_files()
        self.assertEqual([(x["path"], x["conflict"]) for x in st["conflicted"]], [("base.txt", "UU")])
        self.assertEqual(st["staged"] + st["unstaged"], [])
        ok, _ = self.git.merge_abort()
        self.assertTrue(ok)
        self.assertFalse(self.git.is_merging())

    def test_unstage_before_first_commit(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        sh(tmp.name, "init", "-q", "-b", "main")
        write(tmp.name, "a.txt", "a\n")
        g = GitEngine(tmp.name)
        g.stage_all()
        self.assertEqual([x["path"] for x in g.get_status_files()["staged"]], ["a.txt"])
        self.assertTrue(g.unstage_file("a.txt"))
        self.assertEqual([x["path"] for x in g.get_status_files()["untracked"]], ["a.txt"])


class CommitToolsTests(RepoTestCase):
    def head_subject(self):
        return sh(self.root, "log", "-1", "--format=%s").strip()

    def test_commit_with_body(self):
        write(self.root, "a.txt", "a\n")
        self.git.stage_all()
        ok, msg = self.git.commit("feat: a", body="line one\nline two")
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.get_last_commit_message(), ("feat: a", "line one\nline two"))

    def test_empty_message_rejected(self):
        write(self.root, "a.txt", "a\n")
        self.git.stage_all()
        self.assertFalse(self.git.commit("   ")[0])

    def test_amend_adds_staged_file_and_keeps_message(self):
        count = sh(self.root, "rev-list", "--count", "HEAD").strip()
        write(self.root, "forgot.txt", "x\n")
        self.git.stage_all()
        ok, msg = self.git.commit("", amend=True)
        self.assertTrue(ok, msg)
        self.assertEqual(self.head_subject(), "init")
        self.assertEqual(sh(self.root, "rev-list", "--count", "HEAD").strip(), count)
        self.assertIn("forgot.txt", sh(self.root, "show", "--name-only", "--format=", "HEAD"))

    def test_reword_head_ignores_index(self):
        sh(self.root, "commit", "-q", "--amend", "-m", "old subject", "-m", "kept body")
        write(self.root, "staged.txt", "s\n")
        self.git.stage_file("staged.txt")
        ok, msg = self.git.reword_head("new subject")
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.get_last_commit_message(), ("new subject", "kept body"))
        self.assertEqual([x["path"] for x in self.git.get_status_files()["staged"]], ["staged.txt"])

    def test_is_head_pushed(self):
        self.assertFalse(self.git.is_head_pushed())
        remote = tempfile.TemporaryDirectory()
        self.addCleanup(remote.cleanup)
        sh(remote.name, "init", "-q", "--bare", "-b", "main")
        sh(self.root, "remote", "add", "origin", remote.name)
        self.git.push()
        self.assertTrue(self.git.is_head_pushed())

    def test_discard_tracked_and_untracked(self):
        write(self.root, "base.txt", "changed\n")
        write(self.root, "junk file.txt", "junk\n")
        self.assertTrue(self.git.discard_file("base.txt")[0])
        self.assertTrue(self.git.discard_file("junk file.txt", untracked=True)[0])
        st = self.git.get_status_files()
        self.assertEqual(st["unstaged"] + st["untracked"], [])
        with open(os.path.join(self.root, "base.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "base\n")

    def test_discard_keeps_staged_version(self):
        write(self.root, "base.txt", "staged\n")
        self.git.stage_file("base.txt")
        write(self.root, "base.txt", "staged\nplus worktree\n")
        self.git.discard_file("base.txt")
        with open(os.path.join(self.root, "base.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "staged\n")

    def test_show_commit(self):
        out = self.git.show_commit("HEAD")
        self.assertIn("init", out)
        self.assertIn("+base", out)


class BranchTests(RepoTestCase):
    def test_create_switch_rename_delete(self):
        ok, msg = self.git.create_branch("feature/login")
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.get_branch_name(), "feature/login")

        ok, msg = self.git.rename_branch("feature/login", "feature/auth")
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.get_branch_name(), "feature/auth")

        ok, msg = self.git.checkout_branch("main")
        self.assertTrue(ok, msg)
        ok, msg = self.git.delete_branch("feature/auth")
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.list_branches(), ["main"])

    def test_invalid_and_duplicate_names_rejected(self):
        for bad in ["", "-x", "has space", "a..b", "HEAD", "end/"]:
            ok, _ = self.git.create_branch(bad)
            self.assertFalse(ok, bad)
        ok, _ = self.git.create_branch("main")
        self.assertFalse(ok)

    def test_cannot_delete_current_branch(self):
        ok, _ = self.git.delete_branch("main", force=True)
        self.assertFalse(ok)

    def test_unmerged_count_and_force_delete(self):
        self.git.create_branch("wip")
        write(self.root, "wip.txt", "x\n")
        self.git.stage_all()
        self.git.commit("wip")
        self.git.checkout_branch("main")
        self.assertEqual(self.git.unmerged_commit_count("wip"), 1)
        ok, _ = self.git.delete_branch("wip")
        self.assertFalse(ok)  # -d refuses unmerged work
        ok, msg = self.git.delete_branch("wip", force=True)
        self.assertTrue(ok, msg)

    def test_merge_fast_forward(self):
        self.git.create_branch("feat")
        write(self.root, "f.txt", "f\n")
        self.git.stage_all()
        self.git.commit("feat: f")
        self.git.checkout_branch("main")
        ok, msg = self.git.merge_branch("feat")
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.unmerged_commit_count("feat"), 0)

    def test_detailed_listing_with_remote(self):
        remote = tempfile.TemporaryDirectory()
        self.addCleanup(remote.cleanup)
        sh(remote.name, "init", "-q", "--bare", "-b", "main")
        sh(self.root, "remote", "add", "origin", remote.name)
        sh(self.root, "push", "-q", "-u", "origin", "main")
        sh(self.root, "push", "-q", "origin", "main:remote-only")
        self.git.fetch()

        write(self.root, "x.txt", "x\n")
        self.git.stage_all()
        self.git.commit("local")

        branches = self.git.list_branches_detailed()
        local = {b["name"]: b for b in branches if b["kind"] == "local"}
        remote_b = {b["name"]: b for b in branches if b["kind"] == "remote"}

        self.assertTrue(local["main"]["current"])
        self.assertEqual(local["main"]["upstream"], "origin/main")
        self.assertEqual((local["main"]["ahead"], local["main"]["behind"]), (1, 0))
        self.assertNotIn("origin/HEAD", remote_b)
        self.assertTrue(remote_b["origin/main"]["has_local"])
        self.assertFalse(remote_b["origin/remote-only"]["has_local"])

        ok, msg = self.git.checkout_remote_branch("origin/remote-only")
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.get_branch_name(), "remote-only")
        self.assertEqual(self.git.get_upstream(), "origin/remote-only")

    def test_dirty_tree_blocks_switch_then_stash(self):
        self.git.create_branch("other")
        write(self.root, "base.txt", "other\n")
        self.git.stage_all()
        self.git.commit("other")
        self.git.checkout_branch("main")
        write(self.root, "base.txt", "dirty\n")

        ok, _ = self.git.checkout_branch("other")
        self.assertFalse(ok)
        self.assertTrue(self.git.has_changes())

        ok, msg = self.git.stash_save("auto", include_untracked=True)
        self.assertTrue(ok, msg)
        ok, msg = self.git.checkout_branch("other")
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.stash_count(), 1)


class PushSafetyTests(RepoTestCase):
    def test_push_refuses_detached_head(self):
        sh(self.root, "remote", "add", "origin", "https://github.com/example/repo.git")
        sh(self.root, "switch", "-q", "--detach", "HEAD")
        self.assertTrue(self.git.is_detached())
        self.assertEqual(self.git.push(token="t"), (False, DETACHED_HEAD_MSG))
        self.assertEqual(self.git.pull(token="t"), (False, DETACHED_HEAD_MSG))
        self.assertFalse(self.git.push_initial(branch="HEAD (abc)")[0])

    def test_auth_env_keeps_token_out_of_config(self):
        url = "https://github.com/owner/repo.git"
        sh(self.root, "remote", "add", "origin", url)
        env = self.git._auth_env("secret-token")
        self.assertEqual(env["GIT_CONFIG_KEY_0"], "http.https://github.com/.extraheader")
        encoded = env["GIT_CONFIG_VALUE_0"].split("Basic ", 1)[1]
        self.assertEqual(base64.b64decode(encoded).decode(), "owner:secret-token")
        # The header is visible to git through the env...
        seen = self.git._git(["config", "--get", "http.https://github.com/.extraheader"], extra_env=env)
        self.assertTrue(seen.ok)
        # ...but nothing is written to disk or to the remote URL
        self.assertEqual(sh(self.root, "remote", "get-url", "origin").strip(), url)
        with open(os.path.join(self.root, ".git", "config"), encoding="utf-8") as f:
            self.assertNotIn("secret-token", f.read())

    def test_auth_env_skipped_for_ssh_and_empty_token(self):
        sh(self.root, "remote", "add", "origin", "git@github.com:owner/repo.git")
        self.assertIsNone(self.git._auth_env("tok"))
        self.assertIsNone(self.git._auth_env(""))

    def test_push_to_local_bare_remote(self):
        remote = tempfile.TemporaryDirectory()
        self.addCleanup(remote.cleanup)
        sh(remote.name, "init", "-q", "--bare", "-b", "main")
        sh(self.root, "remote", "add", "origin", remote.name)
        ok, msg = self.git.push()
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.get_upstream(), "origin/main")
        self.assertEqual(self.git.get_ahead_behind(), (0, 0))

        # A new local branch only counts commits that are not on the remote yet
        self.git.create_branch("feature")
        self.assertEqual(self.git.get_ahead_behind(), (0, 0))
        write(self.root, "f.txt", "f\n")
        self.git.stage_all()
        self.git.commit("f")
        self.assertEqual(self.git.get_ahead_behind(), (1, 0))


class SyncTests(RepoTestCase):
    def setUp(self):
        super().setUp()
        self._remote = tempfile.TemporaryDirectory()
        self.addCleanup(self._remote.cleanup)
        sh(self._remote.name, "init", "-q", "--bare", "-b", "main")
        sh(self.root, "remote", "add", "origin", self._remote.name)
        sh(self.root, "push", "-q", "-u", "origin", "main")
        # A second clone pushes a commit the first one does not have
        self._other = tempfile.TemporaryDirectory()
        self.addCleanup(self._other.cleanup)
        other = os.path.join(self._other.name, "c")
        subprocess.run(["git", "clone", "-q", self._remote.name, other], check=True, capture_output=True)
        sh(other, "config", "user.name", "O")
        sh(other, "config", "user.email", "o@example.com")
        write(other, "remote.txt", "r\n")
        sh(other, "add", "-A")
        sh(other, "commit", "-q", "-m", "remote")
        sh(other, "push", "-q", "origin", "main")

    def test_fetch_then_pull_divergent_merges(self):
        write(self.root, "local.txt", "l\n")
        self.git.stage_all()
        self.git.commit("local")
        self.assertEqual(self.git.get_ahead_behind(), (1, 0))
        ok, msg = self.git.fetch()
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.get_ahead_behind(), (1, 1))
        ok, msg = self.git.pull()
        self.assertTrue(ok, msg)
        self.assertEqual(self.git.get_ahead_behind(), (2, 0))  # local commit + merge commit

    def test_state_signature_tracks_changes(self):
        sig1 = self.git.state_signature()
        self.assertEqual(sig1, self.git.state_signature())
        write(self.root, "base.txt", "changed\n")
        sig2 = self.git.state_signature()
        self.assertNotEqual(sig1, sig2)
        write(self.root, "base.txt", "changed again\nmore\n")
        self.assertNotEqual(sig2, self.git.state_signature())
        self.git.fetch()
        sig3 = self.git.state_signature()
        self.assertIn("branch.ab +0 -1", sig3)


class RunnerTests(unittest.TestCase):
    def test_invalid_repo_never_raises(self):
        g = GitEngine(None)
        self.assertFalse(g.is_valid())
        self.assertEqual(g.get_status_files()["staged"], [])
        self.assertFalse(g._git(["status"]).ok)
        self.assertEqual(g._run(["status"]), "")

    def test_timeout_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as d:
            sh(d, "init", "-q")
            g = GitEngine(d)
            res = g._git(["-c", "alias.slow=!sleep 5", "slow"], timeout=0.5)
            self.assertFalse(res.ok)
            self.assertIn("timed out", res.err)


if __name__ == "__main__":
    unittest.main()
