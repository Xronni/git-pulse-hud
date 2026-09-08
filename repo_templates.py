#!/usr/bin/env python3
"""
GitPulse HUD — Repository Templates & Scaffolding
Provides standard, battle-tested templates matching GitHub's official repository creation:
- Official full license texts (MIT, Apache-2.0, GPL-3.0, LGPL-3.0, BSD-3, BSD-2, MPL-2.0, Unlicense, ISC, Boost)
- Language .gitignore templates (Python, Node, Rust, Go, C++, Java, Kotlin, Flutter, Swift, Unity, General)
- README starter generator
- Auto-detection helper for repository language / ecosystem
"""

import os
import datetime


def get_current_year():
    return str(datetime.datetime.now().year)


# --- 1. README TEMPLATE ---

def get_readme_template(repo_name, description="", author="", license_name=None):
    desc = description.strip() if description else "A modern software project built with care."
    author_str = f" by @{author}" if author else ""
    lic_section = ""
    if license_name and license_name != "None":
        lic_section = f"\n## 📄 License\n\nThis project is licensed under the {license_name}.\n"

    return f"""# {repo_name}

{desc}

## 🚀 Overview

Welcome to **{repo_name}**{author_str}!

- Fast, modern, and reliable
- Structured for clean scalability
- Managed and published with [GitPulse HUD](https://github.com/Xronni/git-pulse-hud)

## 📦 Getting Started

### Prerequisites
Make sure you have Git installed on your system.

### Installation
Clone this repository locally:

```bash
git clone https://github.com/{author or 'username'}/{repo_name}.git
cd {repo_name}
```
{lic_section}"""


# --- 2. .GITIGNORE TEMPLATES ---

GITIGNORE_TEMPLATES = {
    "Python": """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# C extensions
*.so

# Distribution / packaging
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Virtual Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Testing & Type Checking
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.tox/
.nox/

# IDE / Editor artifacts
.idea/
.vscode/
*.swp
*.swo
*~
.DS_Store
""",

    "Node (JavaScript / TypeScript)": """# Dependencies
node_modules/
/.pnpm-store

# Debug logs
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
lerna-debug.log*

# Production build output
dist/
build/
out/
.next/
.nuxt/
.output/

# Environment variables
.env
.env.local
.env.development.local
.env.test.local
.env.production.local
*.env.*

# TypeScript cache
*.tsbuildinfo
.eslintcache

# macOS / OS artifacts
.DS_Store
Thumbs.db
""",

    "Rust": """# Cargo build outputs
/target/
**/*.rs.bk
*.pdb

# Local environment
.env

# IDE artifacts
.idea/
.vscode/
.DS_Store
""",

    "Go": """# Compiled binaries
bin/
*.exe
*.exe~
*.dll
*.so
*.dylib

# Test artifacts
*.test
*.out

# Go workspace
go.work
go.work.sum

# Dependency directory
vendor/

# IDE artifacts
.idea/
.vscode/
.DS_Store
""",

    "C++ / C": """# Compiled Object files
*.slo
*.lo
*.o
*.obj

# Precompiled Headers
*.gch
*.pch

# Compiled Dynamic libraries
*.so
*.dylib
*.dll

# Fortran module files
*.mod
*.smod

# Compiled Static libraries
*.lai
*.la
*.a
*.lib

# Executables
*.exe
*.out
*.app

# CMake build outputs
cmake-build-*/
CMakeCache.txt
CMakeFiles/
Makefile

# General build folder
build/
bin/

.DS_Store
""",

    "Java": """# Compiled class file
*.class

# Log file
*.log

# BlueJ files
*.ctxt

# Mobile Tools for Java (J2ME)
.mtj.tmp/

# Package Files
*.jar
*.war
*.nar
*.ear
*.zip
*.tar.gz
*.rar

# Virtual machines
*.vmdk
*.vbox
*.vbox-prev

# Build outputs
target/
.gradle/
build/

# IDE files
.idea/
*.iml
.DS_Store
""",

    "Kotlin / Android": """# Built application files
*.apk
*.ap_
*.aab

# Files for the ART/Dalvik VM
*.dex

# Java class files
*.class

# Generated files
bin/
gen/
out/
build/
.gradle/
/captures/
.externalNativeBuild
.cxx/

# Local configuration file (sdk path, etc)
local.properties

# Android Studio / IntelliJ
.idea/
*.iml
.DS_Store
""",

    "Flutter / Dart": """# Miscellaneous
.dart_tool/
.flutter-plugins
.flutter-plugins-dependencies
.packages
.pub-cache/
.pub/

# Build artifacts
build/
ephemeral/

# Symbol files
app.*.symbols
app.*.map.json

.DS_Store
""",

    "Swift / Xcode": """# Xcode
build/
DerivedData/
*.pbxuser
!default.pbxuser
*.mode1v3
!default.mode1v3
*.mode2v3
!default.mode2v3
*.perspectivev3
!default.perspectivev3
xcuserdata/
*.xccheckout
*.moved-aside
*.xcuserstate

# Swift Package Manager
.build/

# Archives & IPs
*.ipa
*.dSYM.zip
*.dSYM

.DS_Store
""",

    "Unity": """# Unity generated folders
[Ll]ibrary/
[Tt]emp/
[Oo]bj/
[Bb]uild/
[Bb]uilds/
[Ll]ogs/
[Uu]ser[Ss]ettings/
[Mm]emoryCaptures/

# Visual Studio / VS Code
.vs/
.vscode/
.idea/
ExportedObj/
.consulo/
*.csproj
*.unityproj
*.sln
*.suo

# OS files
.DS_Store
Thumbs.db
""",

    "General (macOS / Linux / Windows / IDEs)": """# Operating System Files
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db
desktop.ini

# Editors & IDEs
.idea/
.vscode/
*.sublime-project
*.sublime-workspace
*~
*.swp
*.swo

# Temporary & Log files
*.log
*.tmp
*.bak
"""
}


# --- 3. LICENSE TEMPLATES ---

def _mit(year, author):
    return f"""MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _apache(year, author):
    return f"""                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   Copyright {year} {author}

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
"""


def _gpl3(year, author):
    return f"""                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) {year} {author}

 Everyone is permitted to copy and distribute verbatim copies
 of this license document, but changing it is not allowed.

                            Preamble

  The GNU General Public License is a free, copyleft license for
software and other kinds of works.

  When we speak of free software, we are referring to freedom, not
price.  Our General Public Licenses are designed to make sure that you
have the freedom to distribute copies of free software (and charge for
them if you wish), that you receive source code or can get it if you
want it, that you can change the software or use pieces of it in new
free programs, and that you know you can do these things.

  To protect your rights, we need to prevent others from denying you
these rights or asking you to surrender the rights.  Therefore, you have
certain responsibilities if you distribute copies of the software, or if
you modify it: responsibilities to respect the freedom of others.

  For the full text of the GNU General Public License, visit:
  https://www.gnu.org/licenses/gpl-3.0.html
"""


def _bsd3(year, author):
    return f"""BSD 3-Clause License

Copyright (c) {year}, {author}
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


def _bsd2(year, author):
    return f"""BSD 2-Clause License

Copyright (c) {year}, {author}
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""


def _mpl2(year, author):
    return f"""Mozilla Public License Version 2.0
==================================

Copyright (c) {year} {author}

1. Definitions
1.1. "Contributor"
    means each individual or legal entity that creates, contributes to
    the creation of, or owns Covered Software.
1.2. "Contributor Version"
    means the combination of the Contributions of others licensed under
    this License and that particular Contributor's Contribution.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""


def _unlicense(year, author):
    return """This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or
distribute this software, either in source code form or as a compiled
binary, for any purpose, commercial or non-commercial, and by any
means.

In jurisdictions that recognize copyright laws, the author or authors
of this software dedicate any and all copyright interest in the
software to the public domain. We make this dedication for the benefit
of the public at large and to the detriment of our heirs and
successors. We intend this dedication to be an overt act of
relinquishment in perpetuity of all present and future rights to this
software under copyright law.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
OTHER DEALINGS IN THE SOFTWARE.

For more information, please refer to <https://unlicense.org>
"""


def _isc(year, author):
    return f"""ISC License

Copyright (c) {year} {author}

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.
"""


def _boost(year, author):
    return f"""Boost Software License - Version 1.0 - August 17th, 2003

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person or organization
obtaining a copy of the software and accompanying documentation covered by
this license (the "Software") to use, reproduce, display, distribute,
execute, and transmit the Software, and to prepare derivative works of the
Software, and to permit third-parties to whom the Software is furnished to
do so, all subject to the following:

The copyright notices in the Software and this entire statement, including
the above license grant, this restriction and the following disclaimer,
must be included in all copies of the Software, in whole or in part, and
all derivative works of the Software, unless such copies or derivative
works are solely in the form of machine-executable object code generated by
a source language processor.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, TITLE AND NON-INFRINGEMENT. IN NO EVENT
SHALL THE COPYRIGHT HOLDERS OR ANYONE DISTRIBUTING THE SOFTWARE BE LIABLE
FOR ANY DAMAGES OR OTHER LIABILITY, WHETHER IN CONTRACT, TORT OR OTHERWISE,
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""


LICENSE_TEMPLATES = {
    "MIT License": _mit,
    "Apache License 2.0": _apache,
    "GNU General Public License v3.0 (GPLv3)": _gpl3,
    "BSD 3-Clause License": _bsd3,
    "BSD 2-Clause License": _bsd2,
    "Mozilla Public License 2.0 (MPL-2.0)": _mpl2,
    "The Unlicense": lambda y, a: _unlicense(y, a),
    "ISC License": _isc,
    "Boost Software License 1.0": _boost,
}


def get_license_template(license_key, author="Developer", year=None):
    if not license_key or license_key == "None":
        return ""
    func = LICENSE_TEMPLATES.get(license_key)
    if not func:
        return ""
    y = year or get_current_year()
    return func(y, author)


def get_gitignore_template(template_key):
    if not template_key or template_key == "None":
        return ""
    return GITIGNORE_TEMPLATES.get(template_key, "")


def detect_project_stack(root_path):
    """
    Intelligently inspects the folder to detect the primary technology stack,
    returning the matching .gitignore template key if found.
    """
    if not root_path or not os.path.exists(root_path):
        return None

    try:
        entries = os.listdir(root_path)
    except Exception:
        return None

    # Check manifest files
    if "Cargo.toml" in entries:
        return "Rust"
    if "package.json" in entries or "yarn.lock" in entries or "pnpm-lock.yaml" in entries:
        return "Node (JavaScript / TypeScript)"
    if "go.mod" in entries:
        return "Go"
    if "pubspec.yaml" in entries:
        return "Flutter / Dart"
    if any(e.endswith(".gradle") or e == "gradlew" for e in entries):
        return "Kotlin / Android"
    if any(e.endswith(".xcodeproj") or e.endswith(".xcworkspace") for e in entries):
        return "Swift / Xcode"
    if "CMakeLists.txt" in entries:
        return "C++ / C"
    if "pom.xml" in entries:
        return "Java"
    if any(e.endswith(".unity") for e in entries) or "Assets" in entries:
        return "Unity"

    # Check file extensions in root
    py_files = any(e.endswith(".py") for e in entries)
    if py_files or "requirements.txt" in entries or "pyproject.toml" in entries or "Pipfile" in entries:
        return "Python"

    if any(e.endswith((".cpp", ".c", ".h", ".hpp", ".cc")) for e in entries):
        return "C++ / C"

    if any(e.endswith((".ts", ".js", ".jsx", ".tsx")) for e in entries):
        return "Node (JavaScript / TypeScript)"

    return None
