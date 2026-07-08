# Contributing to BreakNWipe

First off, thank you for taking the time to contribute to BreakNWipe! We appreciate your help in making this tool more secure, robust, and user-friendly.

---

## 🛠️ Development Environment Setup

BreakNWipe is built as a hybrid application consisting of a **Python 3 / FastAPI** backend (which drives the CLI and interacts with the hardware layer) and a **React / Next.js** frontend.

### Prerequisites
Make sure your development machine has the following installed:
* Python (>= 3.10)
* Node.js (>= 20)
* [uv](https://docs.astral.sh/uv/) (Python package installer and dependency manager)
* System-level utility binaries (needed for hardware operations and recovery features):
  ```bash
  sudo ./scripts/install_dependencies.sh
  ```

### 1. Python Backend Setup
We use `uv` for lightning-fast, reproducible builds.
```bash
# Install dependencies and set up the virtual environment (.venv)
uv sync

# Run the CLI helper or the FastAPI web backend
sudo uv run python -m breaknwipe.cli.main --help
```

*Adding/removing Python dependencies:*
Always use `uv` to modify the environment so `pyproject.toml` and `uv.lock` are kept in sync:
```bash
uv add <package_name>
uv add --dev <dev_package_name>  # e.g., linting or formatting tools
uv remove <package_name>
```

### 2. Next.js Frontend Setup
The GUI is a statically exported Single Page Application (SPA). To run it in development mode with live hot reloading:
```bash
# 1. Start the Next.js dev server (runs on http://localhost:3000)
cd breaknwipe/breaknwipe-gui
npm install
npm run dev

# 2. In a separate terminal, start the FastAPI server (runs on http://localhost:8000)
# (In development mode, requests to API endpoints are automatically proxied to port 8000)
sudo uv run python -m breaknwipe.cli.main --gui
```

To build the static assets for production (what the FastAPI server distributes when running `--gui`):
```bash
cd breaknwipe/breaknwipe-gui
npm run build
```

---

## 📐 Code Style & Formatting

We maintain strict standards for code readability and type checking. Before submitting your changes, format and lint the codebase:

```bash
# Run auto-formatting (black, isort)
make format

# Run linters and type checkers (flake8, mypy)
make lint
```

---

## 🧪 Testing

We run standalone integration scripts to test critical capabilities like blockchain anchor validation and QR code structure integrity. Ensure these run successfully:

```bash
# Test blockchain ledger integration
uv run python tests/test_blockchain_functionality.py

# Test QR code serialization consistency
uv run python tests/test_qr_consistency.py
```

---

## 🏷️ Versioning & Changelog (Strict Rules)

**Every functional change or bug fix in this repository must increment the version.** 

When submitting a pull request:
1. **Update the version string** in two places:
   * [breaknwipe/__init__.py](file:///media/davidporathur/Data8/Projects/breaknwipe/breaknwipe/__init__.py) (`__version__ = "X.Y.Z"`)
   * [pyproject.toml](file:///media/davidporathur/Data8/Projects/breaknwipe/pyproject.toml) (`version = "X.Y.Z"`)
2. **Follow Semantic Versioning (SemVer):**
   * Patch bump (`x.y.Z`) for bug fixes, documentation, or minor maintenance.
   * Minor bump (`x.Y.0`) for new features or capabilities.
   * Major bump (`X.0.0`) for breaking changes.
3. **Log your changes** in [docs/CHANGELOG.md](file:///media/davidporathur/Data8/Projects/breaknwipe/docs/CHANGELOG.md) under the appropriate version heading, following the [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format (Added, Changed, Deprecated, Removed, Fixed, Security).
4. **Update the version badge** in [README.md](file:///media/davidporathur/Data8/Projects/breaknwipe/README.md) to reflect the new release.

---

## 🚀 Pull Request Checklist

Before submitting your pull request, please double check that:
- [ ] Your code compiles and runs without warnings.
- [ ] All linting and formatting checks pass (`make lint && make format`).
- [ ] Integration tests pass successfully.
- [ ] The version has been incremented in `pyproject.toml` and `breaknwipe/__init__.py`.
- [ ] An entry detailing your change has been added to `docs/CHANGELOG.md`.
- [ ] If changing the UI or CLI features, you have verified the behavior on real/loopback drives.
