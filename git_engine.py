#!/usr/bin/env python3
"""
GitPulse HUD — Git Engine
High-performance, pure-subprocess Git client and local repository analytics engine.
"""

import os
import re
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict


class GitEngine:
    def __init__(self, repo_path=None):
        self.repo_path = repo_path or os.getcwd()
        self.root_path = self.find_repo_root(self.repo_path)

    def find_repo_root(self, path):
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if res.returncode == 0:
                return res.stdout.strip()
        except Exception:
            pass
        return None

    def set_repo(self, path):
        root = self.find_repo_root(path)
        if root:
            self.repo_path = root
            self.root_path = root
            return True
        return False

    def is_valid(self):
        return self.root_path is not None and os.path.exists(self.root_path)

    def _run(self, args, check=False):
        if not self.is_valid():
            return ""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=self.root_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=check
            )
            return res.stdout.strip()
        except Exception:
            return ""

    def get_repo_name(self):
        if self.root_path:
            return os.path.basename(self.root_path)
        return "No Repository"

    def get_github_coords(self):
        """Returns (owner, repo) if origin is a GitHub remote, else (None, None)."""
        remote_url = self._run(["remote", "get-url", "origin"])
        if not remote_url:
            return None, None
        
        # Matches https://github.com/owner/repo.git or git@github.com:owner/repo.git
        patterns = [
            r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?",
        ]
        for pat in patterns:
            m = re.search(pat, remote_url)
            if m:
                return m.group("owner"), m.group("repo")
        return None, None

    def get_current_branch(self):
        branch = self._run(["branch", "--show-current"])
        if not branch:
            # Maybe detached HEAD
            commit = self._run(["rev-parse", "--short", "HEAD"])
            return f"HEAD ({commit})" if commit else "no commits"
        return branch

    def get_ahead_behind(self):
        branch = self.get_current_branch()
        if not branch or "HEAD" in branch:
            return 0, 0
        upstream = self._run(["rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"])
        if not upstream:
            return 0, 0
        counts = self._run(["rev-list", "--left-right", "--count", f"{upstream}...{branch}"])
        if counts:
            parts = counts.split()
            if len(parts) == 2:
                try:
                    behind, ahead = int(parts[0]), int(parts[1])
                    return ahead, behind
                except ValueError:
                    pass
        return 0, 0

    def get_status_files(self):
        """
        Returns {
            'staged': [{'path': ..., 'status': 'M', 'lines_add': 0, 'lines_del': 0}],
            'unstaged': [...],
            'untracked': [...]
        }
        """
        staged = []
        unstaged = []
        untracked = []

        if not self.is_valid():
            return {"staged": staged, "unstaged": unstaged, "untracked": untracked}

        # Get line numbers stat for staged
        staged_stats = {}
        cached_numstat = self._run(["diff", "--cached", "--numstat"])
        if cached_numstat:
            for line in cached_numstat.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    add = int(parts[0]) if parts[0].isdigit() else 0
                    dels = int(parts[1]) if parts[1].isdigit() else 0
                    staged_stats[parts[2]] = (add, dels)

        # Get line numbers stat for unstaged
        unstaged_stats = {}
        work_numstat = self._run(["diff", "--numstat"])
        if work_numstat:
            for line in work_numstat.splitlines():
                parts = line.split("\t")
                if len(parts) >= 3:
                    add = int(parts[0]) if parts[0].isdigit() else 0
                    dels = int(parts[1]) if parts[1].isdigit() else 0
                    unstaged_stats[parts[2]] = (add, dels)

        # Porcelain v1 status
        status_out = self._run(["status", "--porcelain=v1", "-uall"])
        if status_out:
            for line in status_out.splitlines():
                if len(line) < 3:
                    continue
                index_st = line[0]
                work_st = line[1]
                path = line[3:].strip()
                if " -> " in path:
                    path = path.split(" -> ")[1]

                # Untracked
                if index_st == "?" and work_st == "?":
                    untracked.append({
                        "path": path,
                        "status": "?",
                        "lines_add": 0,
                        "lines_del": 0
                    })
                    continue

                # Staged
                if index_st in ["M", "A", "D", "R", "C"]:
                    add, dels = staged_stats.get(path, (0, 0))
                    staged.append({
                        "path": path,
                        "status": index_st,
                        "lines_add": add,
                        "lines_del": dels
                    })

                # Unstaged
                if work_st in ["M", "D", "T"]:
                    add, dels = unstaged_stats.get(path, (0, 0))
                    unstaged.append({
                        "path": path,
                        "status": work_st,
                        "lines_add": add,
                        "lines_del": dels
                    })

        return {
            "staged": staged,
            "unstaged": unstaged,
            "untracked": untracked
        }

    def stage_file(self, filepath):
        res = subprocess.run(["git", "add", filepath], cwd=self.root_path, capture_output=True, check=False)
        return res.returncode == 0

    def unstage_file(self, filepath):
        res = subprocess.run(["git", "restore", "--staged", filepath], cwd=self.root_path, capture_output=True, check=False)
        return res.returncode == 0

    def stage_all(self):
        res = subprocess.run(["git", "add", "-A"], cwd=self.root_path, capture_output=True, check=False)
        return res.returncode == 0

    def unstage_all(self):
        res = subprocess.run(["git", "reset"], cwd=self.root_path, capture_output=True, check=False)
        return res.returncode == 0

    def commit(self, message):
        res = subprocess.run(["git", "commit", "-m", message], cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout or res.stderr

    def push(self):
        branch = self.get_current_branch()
        res = subprocess.run(["git", "push", "-u", "origin", branch], cwd=self.root_path, capture_output=True, text=True, check=False)
        if res.returncode != 0:
            res = subprocess.run(["git", "push"], cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout or res.stderr

    def pull(self):
        res = subprocess.run(["git", "pull"], cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout or res.stderr

    def list_branches(self):
        out = self._run(["branch", "--list", "--format=%(refname:short)"])
        if out:
            return [b.strip() for b in out.splitlines() if b.strip()]
        return []

    def checkout_branch(self, branch_name):
        res = subprocess.run(["git", "checkout", branch_name], cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stderr or res.stdout

    def stash_save(self, message="GitPulse quick stash"):
        res = subprocess.run(["git", "stash", "push", "-m", message], cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout or res.stderr

    def stash_pop(self, index=None):
        cmd = ["git", "stash", "pop"]
        if index is not None:
            cmd.append(f"stash@{{{index}}}")
        res = subprocess.run(cmd, cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout or res.stderr

    def stash_apply(self, index=0):
        res = subprocess.run(["git", "stash", "apply", f"stash@{{{index}}}"], cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout or res.stderr

    def stash_drop(self, index=0):
        res = subprocess.run(["git", "stash", "drop", f"stash@{{{index}}}"], cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout or res.stderr

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

    def list_branches_detailed(self):
        """Returns list of branches with current flag."""
        current = self.get_current_branch()
        branches = self.list_branches()
        result = []
        for b in branches:
            result.append({
                "name": b,
                "current": (b == current)
            })
        return result

    def merge_branch(self, branch_name):
        res = subprocess.run(["git", "merge", branch_name], cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout or res.stderr

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
        res = subprocess.run(["git", "tag", "-a", tag_name, "-m", msg], cwd=self.root_path, capture_output=True, text=True, check=False)
        return res.returncode == 0, res.stdout or res.stderr

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
        return self._run(args)

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
