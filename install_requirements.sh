#!/bin/bash
#
# BreakNWipe Requirements Installation Script
# Installs Python packages in a virtual environment (no sudo required)
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

#!/bin/bash
#
# BreakNWipe Requirements Installation Script
# Installs Python packages in a virtual environment (no sudo required)
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
VENV_DIR="venv"
PYTHON_CMD="python3.10"

# Check if running as regular user (optional - allows root)
check_user() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root - this is allowed but not recommended for development"
        print_status "Consider running as regular user for better security"
    else
        print_status "Running as regular user - good for security"
    fi
}

# Check Python 3.10 availability
check_python() {
    print_status "Checking Python 3.10 availability..."

    if ! command -v "$PYTHON_CMD" &> /dev/null; then
        print_error "Python 3.10 not found. Please install Python 3.10 first."
        print_status "You can install it with: sudo apt install python3.10 python3.10-venv"
        exit 1
    fi

    # Check version
    local python_version
    python_version=$("$PYTHON_CMD" --version 2>&1 | grep -oP 'Python \K[0-9]+\.[0-9]+')
    if [[ "$python_version" != "3.10" ]]; then
        print_warning "Found Python $python_version, but Python 3.10 is recommended"
        print_status "Continuing with available Python version..."
    fi

    print_success "Found Python: $("$PYTHON_CMD" --version)"
}

# Create virtual environment
create_venv() {
    print_status "Creating virtual environment..."

    if [[ -d "$VENV_DIR" ]]; then
        print_warning "Virtual environment already exists at $VENV_DIR"
        read -p "Remove existing venv and create new one? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$VENV_DIR"
        else
            print_status "Using existing virtual environment"
            return 0
        fi
    fi

    if ! "$PYTHON_CMD" -m venv "$VENV_DIR"; then
        print_error "Failed to create virtual environment"
        exit 1
    fi

    print_success "Virtual environment created at $VENV_DIR"
}

# Activate virtual environment and get paths
setup_venv() {
    print_status "Setting up virtual environment..."

    # Activate venv
    source "$VENV_DIR/bin/activate"

    # Store Python executable path
    PYTHON_EXECUTABLE="$VENV_DIR/bin/python"

    print_success "Virtual environment activated"
}

# Install requirements
install_requirements() {
    print_status "Installing Python requirements in virtual environment..."

    # Check if requirements.txt exists
    if [[ ! -f "requirements.txt" ]]; then
        print_error "requirements.txt not found in current directory"
        exit 1
    fi

    # Upgrade pip first
    print_status "Upgrading pip..."
    if ! "$PYTHON_EXECUTABLE" -m pip install --upgrade pip; then
        print_warning "Failed to upgrade pip, continuing..."
    fi

    # Install requirements
    print_status "Installing package requirements..."
    if ! "$PYTHON_EXECUTABLE" -m pip install -r requirements.txt; then
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

    # Make sure we have the latest setuptools and pip
    print_status "Updating setuptools and pip..."
    if ! "$PYTHON_EXECUTABLE" -m pip install --upgrade setuptools pip wheel; then
        print_warning "Failed to update setuptools, continuing anyway..."
    fi

    # Check if pyproject.toml exists and use different installation method if it does
    if [[ -f "pyproject.toml" ]]; then
        print_status "Found pyproject.toml, using PEP 517 installation..."
        if ! "$PYTHON_EXECUTABLE" -m pip install -e .; then
            print_error "Failed to install BreakNWipe package using pyproject.toml"
            exit 1
        fi
    else
        # Install package in development mode using modern pip method
        print_status "Installing in editable mode (may show deprecation warnings - this is normal)..."

        # Try multiple installation methods in order of preference
        if ! "$PYTHON_EXECUTABLE" -m pip install --use-pep517 -e .; then
            print_warning "Modern installation failed, trying with config settings..."
            if ! "$PYTHON_EXECUTABLE" -m pip install -e . --config-settings editable_mode=compat; then
                print_warning "Config settings method failed, trying legacy method..."
                if ! "$PYTHON_EXECUTABLE" -m pip install -e .; then
                    print_error "All installation methods failed for BreakNWipe package"
                    exit 1
                fi
            fi
        fi
    fi

    print_success "BreakNWipe package installed successfully"
}

# Verify installation
verify_installation() {
    print_status "Verifying installation..."

    # Test import
    if "$PYTHON_EXECUTABLE" -c "import breaknwipe; print('BreakNWipe version:', breaknwipe.__version__)" 2>/dev/null; then
        print_success "Package import verification passed"
    else
        print_warning "Package import verification failed"
    fi

    # Test CLI
    if "$PYTHON_EXECUTABLE" -m breaknwipe.cli.main --help &>/dev/null; then
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
    echo "  • Activate venv: ${GREEN}source venv/bin/activate${NC}"
    echo "  • Test CLI: ${GREEN}python -m breaknwipe.cli.main --help${NC}"
    echo "  • Run demo: ${GREEN}sudo make demo${NC}"
    echo
    echo -e "${BLUE}Environment info:${NC}"
    echo "  • Virtual environment: $VENV_DIR"
    echo "  • Python executable: $PYTHON_EXECUTABLE"
    echo "  • Python version: $("$PYTHON_EXECUTABLE" --version)"
    echo
    echo -e "${GREEN}Ready to use BreakNWipe!${NC}"
    echo
}

# Main installation process
main() {
    echo -e "${BLUE}BreakNWipe Requirements Installer${NC}"
    echo -e "${BLUE}Installing Python packages in virtual environment${NC}"
    echo "=================================================="
    echo

    check_user
    check_python
    create_venv
    setup_venv
    install_requirements
    install_breaknwipe
    verify_installation
    show_completion
}

# Run main function
main "$@"