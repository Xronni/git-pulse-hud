#!/usr/bin/env python3
"""
GitPulse HUD — GitHub Telemetry & Insights
Fetches public repository metrics (Stars, Forks, Issues, Releases, Asset Downloads, Reactions)
and traffic analytics (Page Views, Unique Visitors, Referrers) via GitHub API.
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime


class GitHubTelemetry:
    def __init__(self, token=None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")

    def set_token(self, token):
        self.token = token.strip()

    def _make_request(self, endpoint):
        """Helper to call GitHub API with optional auth token."""
        url = f"https://api.github.com{endpoint}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "GitPulse-HUD/1.0")
        req.add_header("Accept", "application/vnd.github.v3+json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data, None
        except urllib.error.HTTPError as e:
            err_msg = e.reason
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                err_msg = err_body.get("message", e.reason)
            except Exception:
                pass
            return None, f"HTTP {e.code}: {err_msg}"
        except Exception as e:
            return None, str(e)

    def fetch_full_insights(self, owner, repo):
        """
        Gathers all metrics requested:
        - repo metadata (stars, forks, open issues, watchers, license)
        - releases & exact asset downloads & release reactions
        - traffic page views & unique visitors (needs token with push/admin access)
        - traffic top referrers (needs token)
        - issue reactions
        """
        results = {
            "owner": owner,
            "repo": repo,
            "repo_url": f"https://github.com/{owner}/{repo}",
            "stars": 0,
            "forks": 0,
            "open_issues": 0,
            "watchers": 0,
            "description": "",
            "views_total": 0,
            "views_uniques": 0,
            "views_history": [],
            "referrers": [],
            "releases": [],
            "total_downloads": 0,
            "reactions": {
                "+1": 0,
                "-1": 0,
                "laugh": 0,
                "hooray": 0,
                "confused": 0,
                "heart": 0,
                "rocket": 0,
                "eyes": 0,
                "total": 0
            },
            "has_traffic_access": False,
            "error": None
        }

        # 1. Base repo stats
        repo_data, err = self._make_request(f"/repos/{owner}/{repo}")
        if err:
            results["error"] = err
            return results

        results["stars"] = repo_data.get("stargazers_count", 0)
        results["forks"] = repo_data.get("forks_count", 0)
        results["open_issues"] = repo_data.get("open_issues_count", 0)
        results["watchers"] = repo_data.get("subscribers_count", repo_data.get("watchers_count", 0))
        results["description"] = repo_data.get("description") or ""

        # 2. Releases & Asset Downloads & Reactions
        releases_data, _ = self._make_request(f"/repos/{owner}/{repo}/releases?per_page=15")
        if releases_data and isinstance(releases_data, list):
            for rel in releases_data:
                tag = rel.get("tag_name", "Release")
                rel_name = rel.get("name") or tag
                published_at = rel.get("published_at", "")[:10]
                assets = []
                rel_downloads = 0

                for a in rel.get("assets", []):
                    d_count = a.get("download_count", 0)
                    rel_downloads += d_count
                    results["total_downloads"] += d_count
                    assets.append({
                        "name": a.get("name"),
                        "size_bytes": a.get("size", 0),
                        "downloads": d_count,
                        "content_type": a.get("content_type", "")
                    })

                # Extract release reactions
                rx = rel.get("reactions", {})
                rel_rx_total = rx.get("total_count", 0)
                results["reactions"]["total"] += rel_rx_total
                for k in ["+1", "heart", "rocket", "hooray", "eyes", "laugh"]:
                    results["reactions"][k] += rx.get(k, 0)

                results["releases"].append({
                    "name": rel_name,
                    "tag": tag,
                    "date": published_at,
                    "downloads": rel_downloads,
                    "assets": assets,
                    "reactions": rx
                })

        # 3. Traffic: Page Views & Unique Visitors (14 days)
        views_data, err_views = self._make_request(f"/repos/{owner}/{repo}/traffic/views")
        if views_data and not err_views:
            results["has_traffic_access"] = True
            results["views_total"] = views_data.get("count", 0)
            results["views_uniques"] = views_data.get("uniques", 0)
            raw_views = views_data.get("views", [])
            for v in raw_views:
                timestamp = v.get("timestamp", "")
                date_str = timestamp[:10]
                results["views_history"].append({
                    "date": date_str,
                    "count": v.get("count", 0),
                    "uniques": v.get("uniques", 0)
                })

        # 4. Traffic: Top Referrers
        referrers_data, err_ref = self._make_request(f"/repos/{owner}/{repo}/traffic/popular/referrers")
        if referrers_data and isinstance(referrers_data, list):
            results["has_traffic_access"] = True
            for ref in referrers_data:
                results["referrers"].append({
                    "site": ref.get("referrer", "Unknown"),
                    "views": ref.get("count", 0),
                    "uniques": ref.get("uniques", 0)
                })

        return results


if __name__ == "__main__":
    import sys
    telemetry = GitHubTelemetry()
    owner = "Xronni"
    repo = "spotify-mini-player"
    print(f"Fetching public insights for {owner}/{repo}...")
    data = telemetry.fetch_full_insights(owner, repo)
    print("Stars:", data["stars"])
    print("Forks:", data["forks"])
    print("Open Issues:", data["open_issues"])
    print("Total Downloads:", data["total_downloads"])
    print("Releases Count:", len(data["releases"]))
    print("Has Traffic Access:", data["has_traffic_access"])
    if data["releases"]:
        print("First Release Assets:", data["releases"][0]["assets"])
