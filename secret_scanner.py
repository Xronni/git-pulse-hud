#!/usr/bin/env python3
"""
GitPulse HUD — Pre-Commit Secret Scanner
Lightweight, high-speed local security analysis to prevent credential and token leaks.
"""

import re
import os

SECRET_PATTERNS = [
    ("GitHub Personal Access Token", re.compile(r"ghp_[A-Za-z0-9_]{36,}")),
    ("GitHub Fine-Grained Token", re.compile(r"github_pat_[A-Za-z0-9_]{82,}")),
    ("OpenAI API Key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("Anthropic API Key", re.compile(r"sk-ant-[A-Za-z0-9_-]{32,}")),
    ("AWS Access Key", re.compile(r"\b(AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}\b")),
    ("Private Key", re.compile(r"-----BEGIN (RSA|EC|OPENSSH|DSA|PGP)?\s*PRIVATE KEY-----")),
    ("Google API Key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("Slack API Token", re.compile(r"xox[baprs]-[0-9A-Za-z]{10,}")),
    ("Generic API Secret", re.compile(r"""(?:api_key|client_secret|access_token|secret_key)\s*[:=]\s*['"][a-zA-Z0-9_\-]{24,}['"]""", re.IGNORECASE))
]

SENSITIVE_FILES = [
    r"^\.env(?:\.local|\.production|\.development)?$",
    r"^.*\.pem$",
    r"^.*\.key$",
    r"^id_rsa$",
    r"^id_ed25519$",
    r"^credentials\.json$"
]


def mask_secret(secret_str):
    """Masks secret to prevent showing sensitive keys in cleartext."""
    if len(secret_str) <= 8:
        return "****"
    return secret_str[:4] + "••••••••" + secret_str[-4:]


def scan_staged_files(git_engine):
    """
    Scans currently staged files and diffs.
    Returns: (is_clean: bool, findings: list of dicts)
    """
    if not git_engine or not git_engine.is_valid():
        return True, []

    status = git_engine.get_status_files()
    staged = status.get("staged", [])
    if not staged:
        return True, []

    findings = []

    for item in staged:
        filepath = item.get("path", "")
        basename = os.path.basename(filepath)

        # 1. Filename checks
        for pat in SENSITIVE_FILES:
            if re.match(pat, basename, re.IGNORECASE):
                findings.append({
                    "file": filepath,
                    "line": 0,
                    "rule": "Sensitive Configuration File",
                    "preview": f"File '{basename}' is known to contain private configuration."
                })
                break

        # 2. Diff line inspection
        diff_text = git_engine.get_file_diff(filepath, staged=True)
        if not diff_text:
            continue

        line_num = 0
        for raw_line in diff_text.splitlines():
            if raw_line.startswith("@@"):
                m = re.search(r"\+(\d+)", raw_line)
                if m:
                    line_num = int(m.group(1)) - 1
                continue

            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                line_num += 1
                content = raw_line[1:].strip()
                for rule_name, regex in SECRET_PATTERNS:
                    match = regex.search(content)
                    if match:
                        secret_val = match.group(0)
                        findings.append({
                            "file": filepath,
                            "line": line_num,
                            "rule": rule_name,
                            "preview": mask_secret(secret_val)
                        })
                        break
            elif not raw_line.startswith("-"):
                line_num += 1

    is_clean = (len(findings) == 0)
    return is_clean, findings


if __name__ == "__main__":
    mock_sample = "ghp_" + ("A" * 36)
    has_match = any(reg.search(mock_sample) for _, reg in SECRET_PATTERNS)
    sys.exit(0 if has_match else 1)
