#!/bin/bash
#
# BreakNWipe Installation Script
# Installs BreakNWipe secure data wiping utility on Ubuntu/Debian systems
#
# Python dependencies are managed with uv (https://docs.astral.sh/uv/):
# this script copies the project source into $INSTALL_DIR/src and runs
# `uv sync` there to build an isolated .venv, instead of pip-installing
# into a hand-rolled virtual environment.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/breaknwipe"
BINARY_DIR="/usr/local/bin"
CONFIG_DIR="/etc/breaknwipe"
LOG_DIR="/var/log/breaknwipe"
USER="breaknwipe"
GROUP="breaknwipe"

# Version info
BREAKNWIPE_VERSION="2.5.0"

# Functions
print_status() {
    echo -e "${BLUE} [INFO]${NC} $1"
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
        echo "Usage: sudo ./install.sh"
        exit 1
    fi
}

check_system() {
    print_status "Checking system compatibility..."

    # Check if Ubuntu/Debian
    if ! command -v apt &> /dev/null; then
        print_error "This installer is designed for Ubuntu/Debian systems with apt package manager"
        exit 1
    fi

    # Check if we're on x86_64 architecture
    if [[ $(uname -m) != "x86_64" ]]; then
        print_error "This installer requires x86_64 architecture"
        exit 1
    fi

    print_success "System compatibility check passed"
}

run_dependency_installer() {
    print_status "Installing system packages and uv..."

    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    if [[ ! -x "$script_dir/install_dependencies.sh" ]]; then
        print_error "scripts/install_dependencies.sh not found next to install.sh"
        exit 1
    fi

    "$script_dir/install_dependencies.sh"
}

# Locates a usable `uv` binary. install_dependencies.sh installs uv for the
# invoking (non-root) user via SUDO_USER, so root's PATH won't have it.
resolve_uv_bin() {
    if command -v uv &> /dev/null; then
        command -v uv
        return 0
    fi

    local candidates=(
        "/root/.local/bin/uv"
        "/home/${SUDO_USER:-}/.local/bin/uv"
        "/usr/local/bin/uv"
    )

    for candidate in "${candidates[@]}"; do
        if [[ -x "$candidate" ]]; then
            echo "$candidate"
            return 0
        fi
    done

    print_error "Could not find 'uv'. Run scripts/install_dependencies.sh first."
    exit 1
}

create_user_group() {
    print_status "Creating system user and group..."

    # Create group if it doesn't exist
    if ! getent group "$GROUP" > /dev/null 2>&1; then
        groupadd --system "$GROUP"
        print_status "Created group: $GROUP"
    fi

    # Create user if it doesn't exist
    if ! getent passwd "$USER" > /dev/null 2>&1; then
        useradd --system --gid "$GROUP" --shell /bin/false \
                --home-dir "$INSTALL_DIR" --no-create-home \
                "$USER"
        print_status "Created user: $USER"
    fi

    print_success "User and group setup complete"
}

create_directories() {
    print_status "Creating directories..."

    mkdir -p "$INSTALL_DIR"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$LOG_DIR"
    mkdir -p /var/lib/breaknwipe
    mkdir -p /var/lib/breaknwipe/certificates
    mkdir -p /var/lib/breaknwipe/reports

    # Set ownership
    chown -R "$USER:$GROUP" "$INSTALL_DIR"
    chown -R "$USER:$GROUP" "$CONFIG_DIR"
    chown -R "$USER:$GROUP" "$LOG_DIR"
    chown -R "$USER:$GROUP" /var/lib/breaknwipe

    # Set permissions
    chmod 755 "$INSTALL_DIR"
    chmod 750 "$CONFIG_DIR"
    chmod 750 "$LOG_DIR"
    chmod 750 /var/lib/breaknwipe

    print_success "Directories created"
}

install_source() {
    print_status "Installing BreakNWipe source into $INSTALL_DIR/src..."

    local repo_root
    repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

    mkdir -p "$INSTALL_DIR/src"

    rsync -a --delete \
        --exclude='.git' \
        --exclude='.venv' \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='*.egg-info' \
        --exclude='build' \
        --exclude='dist' \
        --exclude='node_modules' \
        "$repo_root"/ "$INSTALL_DIR/src/"

    print_success "Source installed to $INSTALL_DIR/src"
}

setup_venv() {
    print_status "Setting up Python environment with uv..."

    local uv_bin
    uv_bin="$(resolve_uv_bin)"

    if ! (cd "$INSTALL_DIR/src" && "$uv_bin" sync --no-dev); then
        print_error "uv sync failed"
        exit 1
    fi

    chown -R "$USER:$GROUP" "$INSTALL_DIR/src"

    print_success "Python environment ready at $INSTALL_DIR/src/.venv"
}

create_wrapper_script() {
    print_status "Creating wrapper script..."

    local venv_python="$INSTALL_DIR/src/.venv/bin/python"

    cat > "$BINARY_DIR/breaknwipe" << EOF
#!/bin/bash
#
# BreakNWipe Wrapper Script (auto-generated by scripts/install.sh)
#

if [[ \$EUID -ne 0 ]]; then
    echo "Error: BreakNWipe requires root privileges"
    echo "Please run with sudo: sudo breaknwipe [options]"
    exit 1
fi

exec "$venv_python" -m breaknwipe.cli.main "\$@"
EOF

    chmod +x "$BINARY_DIR/breaknwipe"

    # Create short alias
    ln -sf "$BINARY_DIR/breaknwipe" "$BINARY_DIR/bwipe"

    print_success "Wrapper script created"
}

create_config_files() {
    print_status "Creating configuration files..."

    # Main configuration
    cat > "$CONFIG_DIR/breaknwipe.conf" << EOF
# BreakNWipe Configuration File

[general]
log_level = INFO
log_file = $LOG_DIR/breaknwipe.log
reports_dir = /var/lib/breaknwipe/reports
certificates_dir = /var/lib/breaknwipe/certificates

[security]
enable_signatures = true
signature_algorithm = RSA-2048
certificate_validity_days = 3650

[defaults]
default_algorithm = nist-clear
verify_by_default = true
generate_certificate = true
certificate_formats = pdf,json

[performance]
max_concurrent_wipes = 4
default_block_size = 65536
progress_update_interval = 5

[compliance]
enforce_standards = true
require_verification = false
audit_logging = true
EOF

    # Logging configuration
    cat > "$CONFIG_DIR/logging.conf" << EOF
[loggers]
keys=root,breaknwipe

[handlers]
keys=fileHandler,consoleHandler

[formatters]
keys=detailed,simple

[logger_root]
level=INFO
handlers=fileHandler

[logger_breaknwipe]
level=INFO
handlers=fileHandler,consoleHandler
qualname=breaknwipe
propagate=0

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=detailed
args=('$LOG_DIR/breaknwipe.log', 'a')

[handler_consoleHandler]
class=StreamHandler
level=INFO
formatter=simple
args=(sys.stdout,)

[formatter_detailed]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
datefmt=%Y-%m-%d %H:%M:%S

[formatter_simple]
format=%(levelname)s: %(message)s
EOF

    # Set ownership and permissions
    chown -R "$USER:$GROUP" "$CONFIG_DIR"
    chmod 640 "$CONFIG_DIR"/*.conf

    print_success "Configuration files created"
}

create_systemd_service() {
    print_status "Creating systemd service..."

    cat > /etc/systemd/system/breaknwipe-daemon.service << EOF
[Unit]
Description=BreakNWipe Daemon
Documentation=https://breaknwipe.readthedocs.io/
After=network.target

[Service]
Type=simple
User=$USER
Group=$GROUP
WorkingDirectory=$INSTALL_DIR/src
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$INSTALL_DIR/src/.venv/bin/python -m breaknwipe.daemon
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$LOG_DIR /var/lib/breaknwipe

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=breaknwipe

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    systemctl daemon-reload

    print_success "Systemd service created"
}

create_logrotate_config() {
    print_status "Setting up log rotation..."

    cat > /etc/logrotate.d/breaknwipe << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 $USER $GROUP
    postrotate
        systemctl reload-or-restart breaknwipe-daemon 2>/dev/null || true
    endscript
}
EOF

    print_success "Log rotation configured"
}

setup_bash_completion() {
    print_status "Setting up bash completion..."

    # Create bash completion script
    cat > /etc/bash_completion.d/breaknwipe << 'EOF'
# BreakNWipe bash completion

_breaknwipe() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    opts="--help --version --interactive --list-devices --verbose wipe info list-algorithms batch verify-certificate"

    case ${prev} in
        --device|-d)
            COMPREPLY=( $(compgen -W "$(ls /dev/sd* /dev/nvme* 2>/dev/null)" -- ${cur}) )
            return 0
            ;;
        --algorithm|-a)
            COMPREPLY=( $(compgen -W "nist-clear nist-purge dod-3pass dod-7pass gutmann random zeros custom" -- ${cur}) )
            return 0
            ;;
        --output|-o)
            COMPREPLY=( $(compgen -d -- ${cur}) )
            return 0
            ;;
    esac

    COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    return 0
}

complete -F _breaknwipe breaknwipe
complete -F _breaknwipe bwipe
EOF

    print_success "Bash completion setup complete"
}

create_desktop_entry() {
    print_status "Creating desktop entry..."

    cat > /usr/share/applications/breaknwipe.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=BreakNWipe
GenericName=Secure Data Wiping
Comment=Secure data wiping utility for IT asset recycling
Exec=sudo breaknwipe --gui
Icon=security-high
Terminal=true
Categories=System;Security;
Keywords=wipe;secure;erase;data;sanitization;
StartupNotify=false
NoDisplay=false
EOF

    print_success "Desktop entry created"
}

run_post_install_checks() {
    print_status "Running post-installation checks..."

    # Check if binary is accessible
    if ! command -v breaknwipe &> /dev/null; then
        print_warning "breaknwipe command not found in PATH"
    else
        print_success "breaknwipe command is accessible"
    fi

    # Check virtual environment
    if [[ -d "$INSTALL_DIR/src/.venv" ]]; then
        print_success "Python environment exists at $INSTALL_DIR/src/.venv"
    else
        print_warning "Python environment not found at $INSTALL_DIR/src/.venv"
    fi

    # Check the package imports correctly
    if "$INSTALL_DIR/src/.venv/bin/python" -c "import breaknwipe" &>/dev/null; then
        print_success "breaknwipe package imports correctly"
    else
        print_warning "breaknwipe package failed to import from $INSTALL_DIR/src/.venv"
    fi

    # Check directories exist
    for dir in "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR" "/var/lib/breaknwipe" "$INSTALL_DIR/src/.venv"; do
        if [[ -d "$dir" ]]; then
            print_success "Directory exists: $dir"
        else
            print_warning "Directory missing: $dir"
        fi
    done

    # Check permissions
    if [[ -w "$LOG_DIR" ]]; then
        print_success "Log directory is writable"
    else
        print_warning "Log directory permission issue"
    fi
}

show_completion_message() {
    echo
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}       BreakNWipe Installation Complete!       ${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo
    echo -e "${BLUE}Installation Summary:${NC}"
    echo "  • Source + Python environment: $INSTALL_DIR/src (managed by uv)"
    echo "  • Configuration files: $CONFIG_DIR"
    echo "  • Log files: $LOG_DIR"
    echo "  • Reports directory: /var/lib/breaknwipe/reports"
    echo
    echo -e "${BLUE}Usage:${NC}"
    echo "  • Interactive mode: ${GREEN}sudo breaknwipe --interactive${NC}"
    echo "  • Web GUI: ${GREEN}sudo breaknwipe --gui${NC}"
    echo "  • List devices: ${GREEN}sudo breaknwipe --list-devices${NC}"
    echo "  • Wipe device: ${GREEN}sudo breaknwipe wipe --device /dev/sdX --algorithm nist-clear${NC}"
    echo "  • Get help: ${GREEN}breaknwipe --help${NC}"
    echo
    echo -e "${BLUE}Additional Commands:${NC}"
    echo "  • Short alias: ${GREEN}sudo bwipe${NC} (equivalent to breaknwipe)"
    echo "  • Service status: ${GREEN}sudo systemctl status breaknwipe-daemon${NC}"
    echo "  • View logs: ${GREEN}sudo journalctl -u breaknwipe-daemon${NC}"
    echo
    echo -e "${YELLOW}Note:${NC} to update after pulling new code, re-run this script -- it"
    echo "re-syncs the source and Python environment via uv each time."
    echo
    echo -e "${GREEN}Installation completed successfully!${NC}"
    echo
}

# Main installation process
main() {
    echo -e "${BLUE}BreakNWipe v$BREAKNWIPE_VERSION Installer${NC}"
    echo -e "${BLUE}Secure Data Wiping for IT Asset Recycling${NC}"
    echo "=============================================="
    echo

    check_root
    check_system
    run_dependency_installer
    create_user_group
    create_directories
    install_source
    setup_venv
    create_wrapper_script
    create_config_files
    create_systemd_service
    create_logrotate_config
    setup_bash_completion
    create_desktop_entry
    run_post_install_checks
    show_completion_message
}

# Run main function
main "$@"
