#!/usr/bin/env python3
"""
GitPulse HUD — Git Engine
Pure-subprocess Git client and local repository analytics engine.

Every git invocation goes through GitEngine._git(): it applies a timeout,
disables interactive prompts, decodes output safely and returns a GitResult
instead of raising. Public methods keep returning plain values or
(ok, message) tuples.
"""

import base64
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit

# Timeouts (seconds)
LOCAL_TIMEOUT = 15      # fast read-only commands
LONG_TIMEOUT = 300      # commands that touch the work tree or run hooks (switch, merge, commit, add)
NETWORK_TIMEOUT = 180   # push / pull / fetch

DETACHED_HEAD_MSG = "HEAD is detached: switch to a branch first."


def _is_forbidden_root(path):
    """Home, / and /root must never be treated as a repository."""
    home_abs = os.path.abspath(os.path.expanduser("~"))
    return os.path.abspath(path) in (home_abs, "/", "/root")


@dataclass
class GitResult:
    ok: bool
    out: str = ""
    err: str = ""
    code: int = 0

    @property
    def message(self):
        """Human-readable output: stdout on success, stderr (or stdout) on failure."""
        if self.ok:
            return (self.out or self.err).strip()
        return (self.err or self.out).strip()

    def pair(self):
        return self.ok, self.message


class GitEngine:
    def __init__(self, repo_path=None):
        if repo_path and os.path.exists(repo_path) and not _is_forbidden_root(repo_path):
            self.repo_path = repo_path
            self.root_path = self.find_repo_root(self.repo_path)
        else:
            self.repo_path = None
            self.root_path = None

    # --- Low-level runner ---

    def _git(self, args, timeout=LOCAL_TIMEOUT, extra_env=None, cwd=None, strip=True):
        """Runs one git command. Never raises; never prompts on a terminal."""
        cwd = cwd or self.root_path
        if not cwd or not os.path.isdir(cwd):
            return GitResult(False, err="Not a valid repository", code=-1)
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        if extra_env:
            env.update(extra_env)
        try:
            res = subprocess.run(
                ["git", "-c", "core.quotepath=false"] + list(args),
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return GitResult(False, err=f"git {args[0]} timed out after {timeout}s", code=-1)
        except (OSError, ValueError) as e:
            return GitResult(False, err=str(e), code=-1)
        out = res.stdout.rstrip("\r\n") if strip else res.stdout
        return GitResult(res.returncode == 0, out, res.stderr.strip(), res.returncode)

    def _run(self, args, check=False):
        """Legacy helper: stdout of a git command ('' if the repo is invalid)."""
        if not self.is_valid():
            return ""
        return self._git(args).out

    def _auth_env(self, token, remote="origin"):
        """Env vars that add an HTTP auth header to a single git process.

        Uses GIT_CONFIG_COUNT/KEY/VALUE (git >= 2.31), so the token is never
        written to .git/config, never embedded in the remote URL and never
        visible in the process argument list.
        """
        if not token:
            return None
        url = self._run(["remote", "get-url", remote]).strip()
        if not url.startswith("https://"):
            return None
        parts = urlsplit(url)
        if not parts.hostname:
            return None
        if ":" in token:
            credentials = token
        else:
            owner, _ = self.get_github_coords(remote)
            credentials = f"{owner or 'x-access-token'}:{token}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        port = f":{parts.port}" if parts.port else ""
        return {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"http.https://{parts.hostname}{port}/.extraheader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {encoded}",
        }

    def _network(self, args, token=None, remote="origin"):
        return self._git(args, timeout=NETWORK_TIMEOUT, extra_env=self._auth_env(token, remote))

    # --- Repository discovery ---

    def find_repo_root(self, path):
        if not path or not os.path.exists(path) or _is_forbidden_root(path):
            return None
        res = self._git(["rev-parse", "--show-toplevel"], cwd=path, timeout=5)
        if res.ok and res.out.strip() and not _is_forbidden_root(res.out.strip()):
            return res.out.strip()
        return None

    def set_repo(self, path):
        if not path or not os.path.exists(path) or _is_forbidden_root(path):
            self.repo_path = None
            self.root_path = None
            return False
        root = self.find_repo_root(path)
        if root:
            self.repo_path = root
            self.root_path = root
            return True
        # Path is a valid directory, but not a git repo yet
        self.repo_path = os.path.abspath(path)
        self.root_path = None
        return False

    def is_valid(self):
        return self.root_path is not None and os.path.exists(self.root_path)

    def get_repo_name(self):
        if self.root_path:
            return os.path.basename(self.root_path)
        return "No Repository"

    def get_github_coords(self, remote="origin"):
        """Returns (owner, repo) if remote is a GitHub remote, else (None, None)."""
        remote_url = self._run(["remote", "get-url", remote]).strip()
        if not remote_url:
            return None, None

        clean = remote_url
        if clean.endswith(".git"):
            clean = clean[:-4]

        # Matches https://github.com/owner/repo or git@github.com:owner/repo
        m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/\s]+)$", clean)
        if m:
            return m.group("owner"), m.group("repo")
        return None, None

    def get_github_repo_info(self):
        """Alias for get_github_coords."""
        return self.get_github_coords()

    def init_repo(self, path=None):
        """Initializes a new Git repository with default branch 'main'."""
        target = path or self.repo_path
        if not target or not os.path.exists(target):
            return False, "Directory does not exist or not specified"
        target_abs = os.path.abspath(target)
        if _is_forbidden_root(target_abs) or target_abs == "/home":
            return False, "Cannot initialize Git directly in home or root directory"
        res = self._git(["init", "-b", "main"], cwd=target_abs)
        if not res.ok:
            # Fallback for older git versions without -b flag
            res = self._git(["init"], cwd=target_abs)
        if res.ok:
            self.set_repo(target_abs)
            return True, "Repository initialized"
        return False, res.message

    def ensure_author_identity(self, name=None, email=None):
        """
        Ensures git user.name and user.email are configured.
        Prevents 'Author identity unknown' errors on fresh OS installs.
        """
        if not self.is_valid():
            return

        fallback_name = name or os.environ.get("USER", "Developer")
        fallback_email = email or f"{os.environ.get('USER', 'developer')}@users.noreply.github.com"

        for key, fallback in (("user.name", fallback_name), ("user.email", fallback_email)):
            if self._run(["config", key]).strip():
                continue
            self._git(["config", key, fallback])
            if not self._run(["config", "--global", key]).strip():
                self._git(["config", "--global", key, fallback])

    # --- Remotes ---

    def has_remote(self, remote_name="origin"):
        """Returns True if the specified remote is configured."""
        if not self.is_valid():
            return False
        out = self._run(["remote"])
        return remote_name in [r.strip() for r in out.splitlines()]

    def add_remote(self, name, url):
        """Adds a remote repository URL."""
        if not self.is_valid():
            return False, "Not a valid repository"
        res = self._git(["remote", "add", name, url])
        return (True, "Remote added") if res.ok else (False, res.message)

    def set_remote_url(self, name, url):
        """Updates a remote repository URL."""
        if not self.is_valid():
            return False, "Not a valid repository"
        res = self._git(["remote", "set-url", name, url])
        return res.ok, res.err

    def has_commits(self):
        """Returns True if HEAD points to a valid commit."""
        if not self.is_valid():
            return False
        return self._git(["rev-parse", "--verify", "--quiet", "HEAD"]).ok

    def push_initial(self, remote="origin", branch=None, token=None):
        """Pushes the current branch to remote, setting upstream tracking."""
        if not self.is_valid():
            return False, "Not a valid repository"
        if not branch or "HEAD" in branch or branch == "no commits":
            branch = self.get_branch_name()
        if not branch:
            return False, DETACHED_HEAD_MSG
        return self._network(["push", "-u", remote, f"{branch}:{branch}"], token, remote).pair()

    def push(self, token=None, remote="origin"):
        if not self.is_valid():
            return False, "Not a valid repository"
        if not self.has_remote(remote):
            return False, f"No remote '{remote}' configured"
        branch = self.get_branch_name()
        if not branch:
            # Never guess a target branch: pushing a detached HEAD to 'main' rewrites the wrong branch.
            return False, DETACHED_HEAD_MSG
        return self._network(["push", "-u", remote, f"{branch}:{branch}"], token, remote).pair()

    def pull(self, token=None, remote="origin"):
        if not self.is_valid():
            return False, "Not a valid repository"
        if not self.has_remote(remote):
            return False, f"No remote '{remote}' configured"
        branch = self.get_branch_name()
        if not branch:
            return False, DETACHED_HEAD_MSG
        args = ["pull", "--no-edit"]
        # git >= 2.33 refuses divergent pulls unless a strategy is configured.
        # Respect the user's pull.rebase / pull.ff, otherwise merge (like GitHub Desktop).
        if not self._run(["config", "--get", "pull.rebase"]).strip() and not self._run(["config", "--get", "pull.ff"]).strip():
            args.append("--no-rebase")
        if not self.get_upstream(branch):
            args += [remote, branch]
        return self._network(args, token, remote).pair()

    def fetch(self, token=None, remote="origin"):
        if not self.is_valid():
            return False, "Not a valid repository"
        if not self.has_remote(remote):
            return False, f"No remote '{remote}' configured"
        return self._network(["fetch", "--prune", remote], token, remote).pair()

    def push_tag(self, tag_name, token=None, remote="origin"):
        if not self.has_remote(remote):
            return False, f"No remote '{remote}' configured"
        return self._network(["push", remote, f"refs/tags/{tag_name}"], token, remote).pair()

    # --- Branch state ---

    def get_branch_name(self):
        """Current branch name, or '' when HEAD is detached."""
        return self._run(["branch", "--show-current"]).strip()

    def get_current_branch(self):
        """Display name of the current branch ('HEAD (abc1234)' when detached)."""
        branch = self.get_branch_name()
        if not branch:
            commit = self._run(["rev-parse", "--short", "HEAD"]).strip()
            return f"HEAD ({commit})" if commit else "no commits"
        return branch

    def is_detached(self):
        return self.is_valid() and not self.get_branch_name()

    def get_upstream(self, branch=None):
        """Upstream of a branch ('origin/main'), or '' when none is set."""
        branch = branch or self.get_branch_name()
        if not branch:
            return ""
        return self._run(["for-each-ref", "--format=%(upstream:short)", f"refs/heads/{branch}"]).strip()

    def _count_ahead_behind(self, upstream, branch):
        parts = self._run(["rev-list", "--left-right", "--count", f"{upstream}...refs/heads/{branch}"]).split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            behind, ahead = int(parts[0]), int(parts[1])
            return ahead, behind
        return 0, 0

    def get_ahead_behind(self):
        branch = self.get_branch_name()
        if not branch or not self.has_commits():
            return 0, 0

        # 1. Configured upstream, else 2. a same-named branch on origin
        upstream = self.get_upstream(branch)
        if not upstream and self.has_remote("origin"):
            if self._git(["rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}"]).ok:
                upstream = f"origin/{branch}"
        if upstream:
            return self._count_ahead_behind(upstream, branch)

        # 3. Branch not on the remote yet: count commits no remote-tracking ref contains
        args = ["rev-list", "--count", f"refs/heads/{branch}"]
        if self.has_remote("origin"):
            args += ["--not", "--remotes=origin"]
        total = self._run(args).strip()
        return (int(total), 0) if total.isdigit() else (0, 0)

    # --- Working tree status ---

    def _numstat(self, cached):
        """{path: (added, deleted)} for staged (cached=True) or unstaged changes."""
        args = ["diff", "--numstat", "-z"] + (["--cached"] if cached else [])
        tokens = self._git(args, strip=False).out.split("\0")
        stats = {}
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            i += 1
            parts = tok.split("\t", 2)
            if len(parts) < 3:
                continue
            add = int(parts[0]) if parts[0].isdigit() else 0
            dels = int(parts[1]) if parts[1].isdigit() else 0
            path = parts[2]
            if path == "":
                # Rename/copy: "<add>\t<del>\t\0<old>\0<new>\0"
                if i + 1 >= len(tokens):
                    break
                path = tokens[i + 1]
                i += 2
            stats[path] = (add, dels)
        return stats

    @staticmethod
    def _file_item(path, status, stats=None):
        add, dels = (stats or {}).get(path, (0, 0))
        return {"path": path, "status": status, "lines_add": add, "lines_del": dels}

    def get_status_files(self):
        """
        Returns {
            'staged':     [{'path': ..., 'status': 'M', 'lines_add': 0, 'lines_del': 0}],
            'unstaged':   [...],
            'untracked':  [...],
            'conflicted': [{'path': ..., 'status': 'U', 'conflict': 'UU', ...}],
        }
        Parsed from `git status --porcelain=v2 -z`, so paths with spaces,
        quotes, non-ASCII characters and renames survive intact.
        """
        result = {"staged": [], "unstaged": [], "untracked": [], "conflicted": []}
        if not self.is_valid():
            return result

        res = self._git(["status", "--porcelain=v2", "-z", "-uall"], strip=False)
        if not res.ok:
            return result

        staged_stats = self._numstat(cached=True)
        unstaged_stats = self._numstat(cached=False)

        tokens = res.out.split("\0")
        i = 0
        while i < len(tokens):
            entry = tokens[i]
            i += 1
            if not entry:
                continue
            kind = entry[0]
            if kind == "?":
                result["untracked"].append(self._file_item(entry[2:], "?"))
            elif kind in ("1", "2"):
                # 1 XY sub mH mI mW hH hI path
                # 2 XY sub mH mI mW hH hI Xscore path\0origPath
                fields = entry.split(" ", 9 if kind == "2" else 8)
                if len(fields) < (10 if kind == "2" else 9):
                    continue
                xy, path = fields[1], fields[-1]
                if kind == "2":
                    i += 1  # skip the original path token
                if xy[0] != ".":
                    result["staged"].append(self._file_item(path, xy[0], staged_stats))
                if xy[1] != ".":
                    result["unstaged"].append(self._file_item(path, xy[1], unstaged_stats))
            elif kind == "u":
                # u XY sub m1 m2 m3 mW h1 h2 h3 path
                fields = entry.split(" ", 10)
                if len(fields) < 11:
                    continue
                item = self._file_item(fields[-1], "U")
                item["conflict"] = fields[1]
                result["conflicted"].append(item)
        return result

    def state_signature(self):
        """Cheap fingerprint of HEAD, branch, ahead/behind, index and work tree.

        Two equal signatures mean the UI does not need to be rebuilt; used by
        the auto-refresh poller. Returns None when the repo is not valid.
        """
        if not self.is_valid():
            return None
        status = self._git(["status", "--porcelain=v2", "-z", "--branch", "-uall"], strip=False)
        if not status.ok:
            return None
        numstat = self._git(["diff", "--numstat", "-z"], strip=False).out
        stashes = self._run(["rev-parse", "-q", "--verify", "refs/stash"])
        return f"{self.root_path}\0{status.out}\0{numstat}\0{stashes}"

    def has_changes(self, include_untracked=True):
        """True if the work tree or index has uncommitted changes."""
        args = ["status", "--porcelain=v2"] + ([] if include_untracked else ["-uno"])
        return bool(self._run(args).strip())

    def stage_file(self, filepath):
        return self._git(["add", "--", filepath], timeout=LONG_TIMEOUT).ok

    def unstage_file(self, filepath):
        if self._git(["restore", "--staged", "--", filepath]).ok:
            return True
        if not self.has_commits():
            # No HEAD yet: drop the path from the index instead
            return self._git(["rm", "--cached", "--quiet", "--", filepath]).ok
        return self._git(["reset", "-q", "HEAD", "--", filepath]).ok

    def stage_all(self):
        return self._git(["add", "-A"], timeout=LONG_TIMEOUT).ok

    def unstage_all(self):
        if not self.has_commits():
            return self._git(["rm", "-r", "--cached", "--quiet", "."]).ok
        return self._git(["reset", "-q"]).ok

    def commit(self, message, body=None, amend=False):
        """Commits the index. With amend=True and no message, keeps the previous message."""
        args = ["commit"]
        if amend:
            args.append("--amend")
        message = (message or "").strip()
        if message:
            args += ["-m", message]
            if body and body.strip():
                args += ["-m", body.strip()]
        elif amend:
            args.append("--no-edit")
        else:
            return False, "Empty commit message"
        # Hooks (pre-commit, lint) may run here, hence the long timeout
        return self._git(args, timeout=LONG_TIMEOUT).pair()

    def get_last_commit_message(self):
        """(subject, body) of HEAD, or ('', '') when there are no commits."""
        if not self.has_commits():
            return "", ""
        msg = self._git(["log", "-1", "--format=%B"]).out.strip()
        subject, _, body = msg.partition("\n")
        return subject.strip(), body.strip()

    def reword_head(self, subject):
        """Changes the subject line of HEAD, keeping its body and ignoring the index."""
        subject = (subject or "").strip()
        if not subject:
            return False, "Empty commit message"
        _, body = self.get_last_commit_message()
        args = ["commit", "--amend", "--only", "--allow-empty", "-m", subject]
        if body:
            args += ["-m", body]
        return self._git(args, timeout=LONG_TIMEOUT).pair()

    def is_head_pushed(self):
        """True if HEAD is already contained in some remote-tracking branch."""
        return bool(self._run(["branch", "-r", "--contains", "HEAD"]).strip())

    def discard_file(self, filepath, untracked=False):
        """Throws away work-tree changes of one file (untracked: deletes it)."""
        if untracked:
            return self._git(["clean", "-f", "-q", "--", filepath]).pair()
        return self._git(["restore", "--worktree", "--", filepath], timeout=LONG_TIMEOUT).pair()

    def show_commit(self, commit_hash):
        """Header, stat and patch of one commit for the diff viewer."""
        res = self._git(["show", "--stat", "--patch", "--format=fuller", "--no-color", commit_hash], timeout=LONG_TIMEOUT)
        return res.out if res.ok else res.message

    # --- Branches ---

    _BRANCH_FORMAT = "%00".join([
        "%(refname)", "%(HEAD)", "%(upstream:short)", "%(upstream:track,nobracket)",
        "%(committerdate:relative)", "%(symref)", "%(subject)",
    ])

    @staticmethod
    def _parse_track(track):
        ahead = re.search(r"ahead (\d+)", track or "")
        behind = re.search(r"behind (\d+)", track or "")
        return (
            int(ahead.group(1)) if ahead else 0,
            int(behind.group(1)) if behind else 0,
            (track or "").strip() == "gone",
        )

    def list_branches(self):
        out = self._run(["for-each-ref", "--format=%(refname:short)", "refs/heads"])
        return [b.strip() for b in out.splitlines() if b.strip()]

    def list_branches_detailed(self, include_remote=True):
        """
        Local branches (most recently committed first), then remote branches.
        Local:  {'name', 'kind': 'local', 'current', 'upstream', 'ahead', 'behind', 'gone', 'date', 'subject'}
        Remote: {'name': 'origin/x', 'kind': 'remote', 'remote', 'branch', 'has_local', 'current': False, 'date', 'subject'}
        """
        refs = ["refs/heads"] + (["refs/remotes"] if include_remote else [])
        out = self._run(["for-each-ref", "--sort=-committerdate", f"--format={self._BRANCH_FORMAT}"] + refs)
        local, remote = [], []
        for line in out.splitlines():
            fields = line.split("\0")
            if len(fields) < 7:
                continue
            refname, head, upstream, track, date, symref, subject = fields[:7]
            if symref:
                continue  # origin/HEAD -> origin/main
            if refname.startswith("refs/heads/"):
                ahead, behind, gone = self._parse_track(track)
                local.append({
                    "name": refname[len("refs/heads/"):],
                    "kind": "local",
                    "current": head == "*",
                    "upstream": upstream,
                    "ahead": ahead,
                    "behind": behind,
                    "gone": gone,
                    "date": date,
                    "subject": subject,
                })
            elif refname.startswith("refs/remotes/"):
                short = refname[len("refs/remotes/"):]
                remote_name, _, branch = short.partition("/")
                remote.append({
                    "name": short,
                    "kind": "remote",
                    "remote": remote_name,
                    "branch": branch,
                    "current": False,
                    "date": date,
                    "subject": subject,
                })

        local_names = {b["name"] for b in local}
        tracked = {b["upstream"] for b in local if b["upstream"]}
        for rb in remote:
            rb["has_local"] = rb["branch"] in local_names or rb["name"] in tracked
        return local + remote

    def is_valid_branch_name(self, name):
        name = (name or "").strip()
        if not name or name.startswith("-") or name == "HEAD":
            return False
        return self._git(["check-ref-format", "--branch", name]).ok

    def branch_exists(self, name):
        return self._git(["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"]).ok

    def checkout_branch(self, branch_name):
        """Switches to an existing local branch."""
        return self._git(["switch", branch_name], timeout=LONG_TIMEOUT).pair()

    def checkout_remote_branch(self, remote_ref):
        """Switches to a remote branch ('origin/feature'), creating a tracking local branch if needed."""
        _, _, local_name = remote_ref.partition("/")
        if not local_name:
            return False, f"Not a remote branch: {remote_ref}"
        if self.branch_exists(local_name):
            return self.checkout_branch(local_name)
        return self._git(["switch", "-c", local_name, "--track", remote_ref], timeout=LONG_TIMEOUT).pair()

    def create_branch(self, name, start_point=None, checkout=True):
        name = (name or "").strip()
        if not self.is_valid_branch_name(name):
            return False, f"Invalid branch name: '{name}'"
        if self.branch_exists(name):
            return False, f"Branch '{name}' already exists"
        if checkout:
            args = ["switch", "-c", name]
        else:
            args = ["branch", name]
        if start_point:
            args.append(start_point)
        return self._git(args, timeout=LONG_TIMEOUT).pair()

    def rename_branch(self, old_name, new_name):
        new_name = (new_name or "").strip()
        if not self.is_valid_branch_name(new_name):
            return False, f"Invalid branch name: '{new_name}'"
        if self.branch_exists(new_name):
            return False, f"Branch '{new_name}' already exists"
        return self._git(["branch", "-m", old_name, new_name]).pair()

    def unmerged_commit_count(self, branch_name):
        """Commits on branch_name that the current HEAD does not contain."""
        out = self._run(["rev-list", "--count", f"HEAD..refs/heads/{branch_name}"]).strip()
        return int(out) if out.isdigit() else 0

    def delete_branch(self, branch_name, force=False):
        if branch_name == self.get_branch_name():
            return False, f"Cannot delete the current branch '{branch_name}'"
        return self._git(["branch", "-D" if force else "-d", branch_name]).pair()

    def merge_branch(self, branch_name):
        return self._git(["merge", "--no-edit", branch_name], timeout=LONG_TIMEOUT).pair()

    def is_merging(self):
        return self._git(["rev-parse", "--verify", "--quiet", "MERGE_HEAD"]).ok

    def merge_abort(self):
        return self._git(["merge", "--abort"], timeout=LONG_TIMEOUT).pair()

    # --- Stash ---

    def stash_save(self, message="GitPulse quick stash", include_untracked=False):
        args = ["stash", "push"] + (["--include-untracked"] if include_untracked else []) + ["-m", message]
        return self._git(args, timeout=LONG_TIMEOUT).pair()

    def stash_pop(self, index=None):
        args = ["stash", "pop"]
        if index is not None:
            args.append(f"stash@{{{index}}}")
        return self._git(args, timeout=LONG_TIMEOUT).pair()

    def stash_apply(self, index=0):
        return self._git(["stash", "apply", f"stash@{{{index}}}"], timeout=LONG_TIMEOUT).pair()

    def stash_drop(self, index=0):
        return self._git(["stash", "drop", f"stash@{{{index}}}"]).pair()

    def stash_diff(self, index=0):
        out = self._run(["stash", "show", "-p", f"stash@{{{index}}}"])
        return out or "(Empty stash or no changes)"

    def stash_list(self):
        """Returns list of stashes: [{'index': int, 'id': 'stash@{0}', 'date': '2 hours ago', 'message': str}]."""
        out = self._run(["stash", "list", "--pretty=format:%gd%x09%cr%x09%gs"])
        stashes = []
        if out:
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    s_id = parts[0].strip()
                    idx = 0
                    if "{" in s_id and "}" in s_id:
                        try:
                            idx = int(s_id.split("{")[1].split("}")[0])
                        except Exception:
                            idx = len(stashes)
                    stashes.append({
                        "index": idx,
                        "id": s_id,
                        "date": parts[1].strip(),
                        "message": parts[2].strip()
                    })
        return stashes

    def stash_count(self):
        out = self._run(["stash", "list"])
        return len(out.splitlines()) if out else 0

    # --- Tags & changelog ---

    def get_latest_tag(self):
        out = self._run(["describe", "--tags", "--abbrev=0"])
        if out:
            return out.strip()
        tags = self._run(["tag", "-l", "--sort=-creatordate"])
        if tags:
            return tags.splitlines()[0].strip()
        return None

    def get_changelog_data(self):
        latest_tag = self.get_latest_tag()
        if latest_tag:
            out = self._run(["log", f"{latest_tag}..HEAD", "--pretty=format:%h%x09%s%x09%an"])
        else:
            out = self._run(["log", "-n", "50", "--pretty=format:%h%x09%s%x09%an"])
        
        categories = {
            "feat": [],
            "fix": [],
            "docs": [],
            "perf": [],
            "refactor": [],
            "chore": [],
            "other": []
        }
        
        if out:
            for line in out.splitlines():
                parts = line.split("\t")
                if len(parts) >= 2:
                    h, msg = parts[0], parts[1]
                    matched = False
                    for cat in ["feat", "fix", "docs", "perf", "refactor", "chore"]:
                        if msg.startswith(f"{cat}:") or msg.startswith(f"{cat}(") or msg.startswith(f"{cat}!:"):
                            categories[cat].append({"hash": h, "message": msg})
                            matched = True
                            break
                    if not matched:
                        categories["other"].append({"hash": h, "message": msg})
                        
        return {
            "latest_tag": latest_tag,
            "categories": categories
        }

    def create_tag(self, tag_name, message=""):
        msg = message.strip() or f"Release {tag_name}"
        return self._git(["tag", "-a", tag_name, "-m", msg]).pair()

    def get_commit_graph(self, limit=40):
        """Returns commits with track column and branch metadata."""
        format_str = "%h%x09%p%x09%an%x09%ar%x09%s%x09%d"
        out = self._run(["log", f"-n", str(limit), f"--pretty=format:{format_str}"])
        commits = []
        if not out:
            return commits
        
        lines = out.splitlines()
        active_tracks = []
        
        for line in lines:
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            h = parts[0].strip()
            parents = parts[1].strip().split() if parts[1].strip() else []
            author = parts[2].strip()
            rel_date = parts[3].strip()
            subject = parts[4].strip()
            decorations = parts[5].strip() if len(parts) > 5 else ""
            
            col = 0
            if h in active_tracks:
                col = active_tracks.index(h)
            else:
                if None in active_tracks:
                    col = active_tracks.index(None)
                    active_tracks[col] = h
                else:
                    col = len(active_tracks)
                    active_tracks.append(h)
            
            is_merge = len(parents) > 1
            if parents:
                active_tracks[col] = parents[0]
                for p in parents[1:]:
                    if p not in active_tracks:
                        active_tracks.append(p)
            else:
                active_tracks[col] = None
            
            while active_tracks and active_tracks[-1] is None:
                active_tracks.pop()
                
            branch_label = ""
            if decorations:
                clean_dec = decorations.strip("()")
                for item in clean_dec.split(","):
                    item = item.strip()
                    if "->" in item:
                        branch_label = item.split("->")[-1].strip()
                        break
                    elif item and not item.startswith("tag:"):
                        branch_label = item
                        break
            
            commits.append({
                "hash": h,
                "parents": parents,
                "is_merge": is_merge,
                "col": col,
                "max_cols": max(len(active_tracks), col + 1),
                "author": author,
                "relative_date": rel_date,
                "message": subject,
                "branch": branch_label
            })
            
        return commits

    def get_file_diff(self, filepath, staged=False):
        args = ["diff"]
        if staged:
            args.append("--cached")
        args.extend(["--", filepath])
        diff = self._run(args)
        if not diff and not staged and self.root_path:
            full_p = os.path.join(self.root_path, filepath)
            if os.path.exists(full_p) and not os.path.isdir(full_p):
                # Untracked file: diff against nothing (exit code 1 is expected here)
                return self._git(["diff", "--no-index", "--", "/dev/null", filepath]).out
        return diff

    # --- Pulse & Analytics Methods ---

    def get_commit_velocity(self, days=14):
        """Returns list of {'date': 'YYYY-MM-DD', 'label': '07 Sep', 'count': int}."""
        today = datetime.now().date()
        date_counts = defaultdict(int)

        # Get commits from last N days
        since_date = (today - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        log_out = self._run(["log", f"--since={since_date}", "--date=short", "--pretty=format:%ad"])

        if log_out:
            for line in log_out.splitlines():
                d = line.strip()
                if d:
                    date_counts[d] += 1

        result = []
        for i in range(days):
            day = today - timedelta(days=(days - 1 - i))
            d_str = day.strftime("%Y-%m-%d")
            label = day.strftime("%d %b")
            result.append({
                "date": d_str,
                "label": label,
                "count": date_counts.get(d_str, 0)
            })
        return result

    def get_punchcard(self):
        """Returns list of 24 integers representing commits per hour of the day (0..23)."""
        hours = [0] * 24
        log_out = self._run(["log", "-n", "300", "--date=format:%H", "--pretty=format:%ad"])
        if log_out:
            for line in log_out.splitlines():
                try:
                    h = int(line.strip())
                    if 0 <= h < 24:
                        hours[h] += 1
                except ValueError:
                    pass
        return hours

    def get_recent_commits(self, limit=10):
        """Returns list of recent commits with metadata."""
        format_str = "%h%x09%an%x09%ar%x09%s%x09%ad"
        log_out = self._run(["log", f"-n", str(limit), f"--pretty=format:{format_str}", "--date=iso"])
        commits = []
        if log_out:
            for line in log_out.splitlines():
                parts = line.split("\t")
                if len(parts) >= 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "relative_date": parts[2],
                        "message": parts[3],
                        "date_iso": parts[4] if len(parts) > 4 else ""
                    })
        return commits

    def get_repo_summary(self):
        """Returns total commits, contributors count, and tracked files count."""
        total_commits = self._run(["rev-list", "--count", "HEAD"]) or "0"
        authors_out = self._run(["shortlog", "-sn", "--all"])
        contributors = len(authors_out.splitlines()) if authors_out else 0
        tracked_out = self._run(["ls-files"])
        files_count = len(tracked_out.splitlines()) if tracked_out else 0

        return {
            "name": self.get_repo_name(),
            "root": self.root_path,
            "branch": self.get_current_branch(),
            "total_commits": total_commits,
            "contributors": contributors,
            "files_count": files_count,
            "stashes": self.stash_count()
        }


if __name__ == "__main__":
    git = GitEngine()
    print("Testing GitEngine on current directory:")
    print("Repo root:", git.root_path)
    print("Summary:", git.get_repo_summary())
    print("GitHub coords:", git.get_github_coords())
    print("Status:", git.get_status_files())
    print("Velocity (last 7 days):", git.get_commit_velocity(7))
    print("Punchcard (24h):", git.get_punchcard())
    print("Recent commits:", git.get_recent_commits(3))
