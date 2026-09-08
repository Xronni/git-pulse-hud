# Contributing to GitPulse HUD

Thank you for your interest in contributing to **GitPulse HUD**! 🎉

We welcome contributions of all kinds: bug reports, feature requests, documentation improvements, translations, and code changes.

---

## 🛠️ Local Development Setup

### System Prerequisites
- **Linux** (Ubuntu 22.04+, Debian 12+, Arch Linux, Fedora)
- **Python 3.10 or higher**
- **Git**

Install development dependencies:

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-cairo git

# Arch Linux
sudo pacman -S python python-gobject gtk4 libadwaita python-cairo git

# Fedora
sudo dnf install python3 python3-gobject gtk4 libadwaita python3-cairo git
```

### Running Locally
```bash
git clone https://github.com/Xronni/git-pulse-hud.git
cd git-pulse-hud
./run.sh
```

---

## 🧪 Automated Testing & Verification

Before submitting a Pull Request, verify that your changes pass all automated checks:

```bash
./test.sh
```

The verification suite checks system dependencies, assets, translation parity, git engine functionality, pre-commit secret scanning, and cairo vector visualizations.

---

## 🌍 Adding or Updating Translations (i18n)

GitPulse HUD supports bilingual localization (`EN` and `RU`) in [`i18n.py`](i18n.py):
1. When introducing a new UI string, add it to both the `en` and `ru` dictionaries.
2. Run `./test.sh` to ensure 100% dictionary parity.

---

## 📦 Pull Request Guidelines

1. Fork the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-improvement
   ```
2. Make your changes following the existing code style.
3. Write clear, Conventional Commit messages (`feat: ...`, `fix: ...`, `docs: ...`).
4. Run `./test.sh` and ensure all tests pass.
5. Push your branch and open a Pull Request with a clear description of the problem solved.
