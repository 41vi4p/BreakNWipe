#!/bin/bash
#
# BreakNWipe Requirements Installation Script
# Installs Python packages in the conda environment (no sudo required)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
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

# Configuration
ENV_NAME="breaknwipe"

# Check if running as regular user (not root)
check_user() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should NOT be run as root"
        print_status "Run without sudo: ./install_requirements.sh"
        exit 1
    fi
}

# Find conda installation
find_conda() {
    local conda_paths=(
        "$HOME/miniconda3/bin/conda"
        "$HOME/anaconda3/bin/conda"
        "/opt/miniconda3/bin/conda"
        "/opt/anaconda3/bin/conda"
        "/usr/local/miniconda3/bin/conda"
        "/usr/local/anaconda3/bin/conda"
    )

    for conda_path in "${conda_paths[@]}"; do
        if [[ -f "$conda_path" ]]; then
            echo "$conda_path"
            return 0
        fi
    done

    # Try conda in PATH
    if command -v conda &> /dev/null; then
        echo "conda"
        return 0
    fi

    return 1
}

# Check environment setup
check_environment() {
    print_status "Checking conda environment setup..."

    # Find conda
    local conda_cmd
    if ! conda_cmd=$(find_conda); then
        print_error "Conda not found. Please install Miniconda or Anaconda first."
        print_status "You can run: sudo ./install.sh to install the system components"
        exit 1
    fi

    print_success "Found conda at: $conda_cmd"

    # Check if environment exists
    if ! "$conda_cmd" info --envs | grep -q "^$ENV_NAME\s"; then
        print_error "Conda environment '$ENV_NAME' not found"
        print_status "Please run: sudo ./install.sh first to create the environment"
        exit 1
    fi

    print_success "Conda environment '$ENV_NAME' found"

    # Store conda command for later use
    CONDA_CMD="$conda_cmd"
}

# Install requirements
install_requirements() {
    print_status "Installing Python requirements in conda environment..."

    # Check if requirements.txt exists
    if [[ ! -f "requirements.txt" ]]; then
        print_error "requirements.txt not found in current directory"
        exit 1
    fi

    # Upgrade pip first
    print_status "Upgrading pip..."
    if ! "$CONDA_CMD" run -n "$ENV_NAME" pip install --upgrade pip; then
        print_warning "Failed to upgrade pip, continuing..."
    fi

    # Install requirements
    print_status "Installing package requirements..."
    if ! "$CONDA_CMD" run -n "$ENV_NAME" pip install -r requirements.txt; then
        print_error "Failed to install requirements"
        exit 1
    fi

    print_success "Requirements installed successfully"
}

# Install BreakNWipe package
install_breaknwipe() {
    print_status "Installing BreakNWipe package..."

    # Check if setup.py exists
    if [[ ! -f "setup.py" ]]; then
        print_error "setup.py not found in current directory"
        exit 1
    fi

    # Install package in development mode
    if ! "$CONDA_CMD" run -n "$ENV_NAME" pip install -e .; then
        print_error "Failed to install BreakNWipe package"
        exit 1
    fi

    print_success "BreakNWipe package installed successfully"
}

# Verify installation
verify_installation() {
    print_status "Verifying installation..."

    # Test import
    if "$CONDA_CMD" run -n "$ENV_NAME" python -c "import breaknwipe; print('BreakNWipe version:', breaknwipe.__version__)" 2>/dev/null; then
        print_success "Package import verification passed"
    else
        print_warning "Package import verification failed"
    fi

    # Test CLI
    if "$CONDA_CMD" run -n "$ENV_NAME" python -m breaknwipe.cli.main --help &>/dev/null; then
        print_success "CLI functionality verification passed"
    else
        print_warning "CLI functionality verification failed"
    fi
}

# Show completion message
show_completion() {
    echo
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}    Requirements Installation Complete!        ${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo
    echo -e "${BLUE}What was installed:${NC}"
    echo "  • Python package requirements"
    echo "  • BreakNWipe package (development mode)"
    echo "  • All dependencies and libraries"
    echo
    echo -e "${BLUE}Next steps:${NC}"
    echo "  • System setup: ${GREEN}sudo ./install.sh${NC} (if not done already)"
    echo "  • Test CLI: ${GREEN}$CONDA_CMD run -n $ENV_NAME python -m breaknwipe.cli.main --help${NC}"
    echo "  • Run demo: ${GREEN}sudo make demo${NC}"
    echo
    echo -e "${BLUE}Environment info:${NC}"
    echo "  • Conda environment: $ENV_NAME"
    echo "  • Conda command: $CONDA_CMD"
    echo
    echo -e "${GREEN}Ready to use BreakNWipe!${NC}"
    echo
}

# Main installation process
main() {
    echo -e "${BLUE}BreakNWipe Requirements Installer${NC}"
    echo -e "${BLUE}Installing Python packages in conda environment${NC}"
    echo "=================================================="
    echo

    check_user
    check_environment
    install_requirements
    install_breaknwipe
    verify_installation
    show_completion
}

# Run main function
main "$@"