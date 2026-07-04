#!/bin/bash
#
# BreakNWipe Quickstart Installer
#
# Clones BreakNWipe and runs the full system installer (scripts/install.sh) in
# one step -- no manual `git clone` required. Meant to be run standalone,
# without an existing local checkout:
#
#   curl -fsSL https://raw.githubusercontent.com/41vi4p/BreakNWipe/main/scripts/quickstart.sh | sudo bash
#
# Review the script before piping it into a root shell, as with any
# curl-to-bash installer. To inspect first:
#
#   curl -fsSL https://raw.githubusercontent.com/41vi4p/BreakNWipe/main/scripts/quickstart.sh -o quickstart.sh
#   less quickstart.sh
#   sudo bash quickstart.sh
#

set -e

REPO_URL="${REPO_URL:-https://github.com/41vi4p/BreakNWipe.git}"
BRANCH="${BRANCH:-main}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        echo "Usage: curl -fsSL <url> | sudo bash"
        exit 1
    fi
}

check_system() {
    if ! command -v apt &> /dev/null; then
        print_error "This installer is designed for Ubuntu/Debian systems with apt package manager"
        exit 1
    fi
}

ensure_git() {
    if command -v git &> /dev/null; then
        return 0
    fi

    print_status "Installing git..."
    apt update
    apt install -y git
}

clone_repo() {
    CLONE_DIR="$(mktemp -d /tmp/breaknwipe-quickstart.XXXXXX)"
    print_status "Cloning BreakNWipe (branch: $BRANCH) into $CLONE_DIR..."

    if ! git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$CLONE_DIR"; then
        print_error "Failed to clone $REPO_URL"
        exit 1
    fi

    print_success "Repository cloned"
}

cleanup() {
    if [[ -n "${CLONE_DIR:-}" && -d "$CLONE_DIR" ]]; then
        rm -rf "$CLONE_DIR"
    fi
}

run_installer() {
    print_status "Handing off to scripts/install.sh..."
    chmod +x "$CLONE_DIR/scripts/install.sh" "$CLONE_DIR/scripts/install_dependencies.sh"
    "$CLONE_DIR/scripts/install.sh"
}

main() {
    echo -e "${BLUE}BreakNWipe Quickstart Installer${NC}"
    echo -e "${BLUE}Clones the repo and runs the full system installer${NC}"
    echo "=================================================="
    echo

    trap cleanup EXIT

    check_root
    check_system
    ensure_git
    clone_repo
    run_installer
}

main "$@"
