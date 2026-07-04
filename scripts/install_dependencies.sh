#!/bin/bash
#
# BreakNWipe Dependency Installer
# Installs the OS-level packages BreakNWipe needs (device tools, build
# headers) plus the `uv` Python package manager. Python dependencies
# themselves are NOT installed by this script -- after it finishes, run
# `uv sync` from the project directory to create .venv and install them.
#

set -e

# Colors for output
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
        print_error "This script must be run as root (it installs system packages via apt)"
        echo "Usage: sudo ./scripts/install_dependencies.sh"
        exit 1
    fi
}

check_system() {
    print_status "Checking system compatibility..."

    if ! command -v apt &> /dev/null; then
        print_error "This installer is designed for Ubuntu/Debian systems with apt package manager"
        exit 1
    fi

    print_success "System compatibility check passed"
}

install_system_packages() {
    print_status "Installing system dependencies..."

    if ! apt update; then
        print_error "Failed to update package lists"
        exit 1
    fi

    local packages=(
        "wget"
        "curl"
        "rsync"
        "smartmontools"
        "hdparm"
        "nvme-cli"
        "util-linux"
        "parted"
        "build-essential"
        "libssl-dev"
        "libffi-dev"
    )

    for package in "${packages[@]}"; do
        print_status "Installing $package..."
        if ! apt install -y "$package"; then
            print_warning "Failed to install $package, continuing..."
        fi
    done

    print_success "System dependencies installation completed"
}

# Installs uv for the user who invoked sudo (so `uv sync` afterwards works
# without needing root), falling back to the current user if not run via sudo.
install_uv() {
    print_status "Checking for uv (Python package manager)..."

    if command -v uv &> /dev/null; then
        print_success "uv already installed: $(uv --version)"
        return 0
    fi

    print_status "Installing uv..."

    if [[ -n "$SUDO_USER" ]]; then
        su - "$SUDO_USER" -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi

    print_success "uv installed to ~/.local/bin"
    print_warning "Restart your shell (or run 'source ~/.bashrc') so 'uv' is on PATH"
}

show_completion() {
    echo
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}    System Dependencies Installed!             ${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo
    echo -e "${BLUE}What was installed:${NC}"
    echo "  • smartmontools, hdparm, nvme-cli, util-linux, parted"
    echo "  • build-essential, libssl-dev, libffi-dev"
    echo "  • uv (Python package/dependency manager)"
    echo
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. cd into the BreakNWipe project directory (if not already there)"
    echo "  2. ${GREEN}uv sync${NC}                                    # installs Python deps into .venv"
    echo "  3. ${GREEN}sudo uv run python -m breaknwipe.cli.main --interactive${NC}"
    echo
    echo -e "${BLUE}For a full system-wide install instead (systemd service, dedicated user):${NC}"
    echo "  ${GREEN}sudo ./scripts/install.sh${NC}  (calls this script automatically)"
    echo
}

main() {
    echo -e "${BLUE}BreakNWipe Dependency Installer${NC}"
    echo -e "${BLUE}System packages + uv; Python deps come from 'uv sync'${NC}"
    echo "=================================================="
    echo

    check_root
    check_system
    install_system_packages
    install_uv
    show_completion
}

main "$@"
