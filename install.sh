#!/bin/bash
#
# BreakNWipe Installation Script
# Installs BreakNWipe secure data wiping utility on Ubuntu/Debian systems
#

set -e

# Colors for output
RED=' \\033[0;31m '
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

# Configuration
BINARY_DIR="/usr/local/bin"
CONFIG_DIR="/etc/breaknwipe"
LOG_DIR="/var/log/breaknwipe"
USER="breaknwipe"
GROUP="breaknwipe"

# Version info
BREAKNWIPE_VERSION="1.0.0"

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

    # Check Python version
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
        print_error "Python 3.8 or higher is required"
        exit 1
    fi

    print_success "System compatibility check passed"
}

install_dependencies() {
    print_status "Installing system dependencies..."

    apt update

    # System packages
    apt install -y smartmontools \\
        hdparm \\
        nvme-cli \\
        util-linux \\
        parted \\
        lsblk \\
        build-essential \\
        python3-dev \\
        libssl-dev \\
        libffi-dev

    print_success "System dependencies installed"
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
        useradd --system --gid "$GROUP" --shell /bin/false \\
                --home-dir "$INSTALL_DIR" --no-create-home \\
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

install_python_environment() {
    print_status "Setting up Python virtual environment..."

    # Create virtual environment
    

    # Activate venv and install packages
    conda activate breaknwipe

    

    # Install BreakNWipe package
    pip install -e .

    deactivate

    # Set ownership
    chown -R "$USER:$GROUP" "$INSTALL_DIR/venv"

    print_success "Python environment setup complete"
}

create_wrapper_script() {
    print_status "Creating wrapper script..."

    cat > "$BINARY_DIR/breaknwipe" << 'EOF'
#!/bin/bash
#
# BreakNWipe Wrapper Script
#

INSTALL_DIR="/opt/breaknwipe"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "Error: BreakNWipe requires root privileges"
    echo "Please run with sudo: sudo breaknwipe [options]"
    exit 1
fi

# Activate virtual environment and run BreakNWipe
source "$INSTALL_DIR/venv/bin/activate"
exec python -m breaknwipe.cli.main "$@"
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
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$INSTALL_DIR/venv/bin/python -m breaknwipe.daemon
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
Exec=sudo breaknwipe --interactive
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

    # Check Python environment
    if source "$INSTALL_DIR/venv/bin/activate" && python -c "import breaknwipe" 2>/dev/null; then
        print_success "Python package installation verified"
        deactivate
    else
        print_warning "Python package verification failed"
    fi

    # Check directories exist
    for dir in "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR" "/var/lib/breaknwipe"; do
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
    echo "  • Installation directory: $INSTALL_DIR"
    echo "  • Configuration files: $CONFIG_DIR"
    echo "  • Log files: $LOG_DIR"
    echo "  • Reports directory: /var/lib/breaknwipe/reports"
    echo
    echo -e "${BLUE}Usage:${NC}"
    echo "  • Interactive mode: ${GREEN}sudo breaknwipe --interactive${NC}"
    echo "  • List devices: ${GREEN}sudo breaknwipe --list-devices${NC}"
    echo "  • Wipe device: ${GREEN}sudo breaknwipe wipe --device /dev/sdX --algorithm nist-clear${NC}"
    echo "  • Get help: ${GREEN}breaknwipe --help${NC}"
    echo
    echo -e "${BLUE}Additional Commands:${NC}"
    echo "  • Short alias: ${GREEN}sudo bwipe${NC} (equivalent to breaknwipe)"
    echo "  • Service status: ${GREEN}sudo systemctl status breaknwipe-daemon${NC}"
    echo "  • View logs: ${GREEN}sudo journalctl -u breaknwipe-daemon${NC}"
    echo
    echo -e "${YELLOW}Important Notes:${NC}"
    echo "  • BreakNWipe requires root privileges to access storage devices"
    echo "  • Always verify device paths before running wipe operations"
    echo "  • Configuration files are located in $CONFIG_DIR"
    echo "  • Check the documentation for advanced usage"
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
    install_dependencies
    create_user_group
    create_directories
    install_python_environment
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
