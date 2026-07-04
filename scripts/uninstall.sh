#!/bin/bash
#
# BreakNWipe Uninstallation Script
# Removes BreakNWipe secure data wiping utility from Ubuntu/Debian systems
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
DATA_DIR="/var/lib/breaknwipe"
USER="breaknwipe"
GROUP="breaknwipe"

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

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root"
        echo "Usage: sudo ./uninstall.sh"
        exit 1
    fi
}

confirm_uninstall() {
    echo -e "${YELLOW}WARNING: This will completely remove BreakNWipe from your system.${NC}"
    echo -e "${YELLOW}All configuration files, logs, and certificates will be deleted.${NC}"
    echo
    read -p "Are you sure you want to continue? [y/N]: " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi
}

stop_services() {
    print_status "Stopping BreakNWipe services..."

    # Stop systemd service if it exists and is running
    if systemctl is-active --quiet breaknwipe-daemon 2>/dev/null; then
        systemctl stop breaknwipe-daemon
        print_success "Stopped breaknwipe-daemon service"
    fi

    # Disable service
    if systemctl is-enabled --quiet breaknwipe-daemon 2>/dev/null; then
        systemctl disable breaknwipe-daemon
        print_success "Disabled breaknwipe-daemon service"
    fi
}

remove_systemd_service() {
    print_status "Removing systemd service..."

    if [[ -f /etc/systemd/system/breaknwipe-daemon.service ]]; then
        rm -f /etc/systemd/system/breaknwipe-daemon.service
        systemctl daemon-reload
        print_success "Removed systemd service file"
    fi
}

remove_binaries() {
    print_status "Removing binary files..."

    # Remove main binary
    if [[ -f "$BINARY_DIR/breaknwipe" ]]; then
        rm -f "$BINARY_DIR/breaknwipe"
        print_success "Removed $BINARY_DIR/breaknwipe"
    fi

    # Remove alias
    if [[ -L "$BINARY_DIR/bwipe" ]]; then
        rm -f "$BINARY_DIR/bwipe"
        print_success "Removed $BINARY_DIR/bwipe"
    fi
}

remove_directories() {
    print_status "Removing directories and data..."

    # Ask about data preservation
    echo
    read -p "Do you want to preserve reports and certificates? [y/N]: " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Backup data
        backup_dir="/tmp/breaknwipe_backup_$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$backup_dir"

        if [[ -d "$DATA_DIR/reports" ]]; then
            cp -r "$DATA_DIR/reports" "$backup_dir/"
            print_status "Reports backed up to $backup_dir/reports"
        fi

        if [[ -d "$DATA_DIR/certificates" ]]; then
            cp -r "$DATA_DIR/certificates" "$backup_dir/"
            print_status "Certificates backed up to $backup_dir/certificates"
        fi

        if [[ -d "$CONFIG_DIR" ]]; then
            cp -r "$CONFIG_DIR" "$backup_dir/config"
            print_status "Configuration backed up to $backup_dir/config"
        fi

        print_success "Data backed up to $backup_dir"
    fi

    # Remove directories
    directories=("$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR" "$DATA_DIR")

    for dir in "${directories[@]}"; do
        if [[ -d "$dir" ]]; then
            rm -rf "$dir"
            print_success "Removed directory: $dir"
        fi
    done
}

remove_user_group() {
    print_status "Removing system user and group..."

    # Remove user if it exists
    if getent passwd "$USER" > /dev/null 2>&1; then
        userdel "$USER"
        print_success "Removed user: $USER"
    fi

    # Remove group if it exists and is not used by other users
    if getent group "$GROUP" > /dev/null 2>&1; then
        if ! getent group "$GROUP" | grep -q ":.*[^:]"; then
            groupdel "$GROUP"
            print_success "Removed group: $GROUP"
        else
            print_warning "Group $GROUP not removed (other users exist)"
        fi
    fi
}

remove_config_files() {
    print_status "Removing configuration files..."

    # Remove logrotate config
    if [[ -f /etc/logrotate.d/breaknwipe ]]; then
        rm -f /etc/logrotate.d/breaknwipe
        print_success "Removed logrotate configuration"
    fi

    # Remove bash completion
    if [[ -f /etc/bash_completion.d/breaknwipe ]]; then
        rm -f /etc/bash_completion.d/breaknwipe
        print_success "Removed bash completion"
    fi

    # Remove desktop entry
    if [[ -f /usr/share/applications/breaknwipe.desktop ]]; then
        rm -f /usr/share/applications/breaknwipe.desktop
        print_success "Removed desktop entry"
    fi
}

clean_package_cache() {
    print_status "Cleaning package cache..."

    # Remove pip cache related to BreakNWipe
    if command -v pip3 &> /dev/null; then
        pip3 cache purge 2>/dev/null || true
    fi

    print_success "Package cache cleaned"
}

remove_dependencies() {
    echo
    read -p "Remove system dependencies that were installed for BreakNWipe? [y/N]: " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Removing system dependencies..."

        print_warning "This will remove packages that might be used by other applications"
        echo "Packages to remove: smartmontools hdparm nvme-cli python3-dev build-essential"
        echo
        read -p "Continue with dependency removal? [y/N]: " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            apt remove --autoremove -y \
                smartmontools \
                hdparm \
                nvme-cli \
                python3-dev \
                build-essential \
                libssl-dev \
                libffi-dev 2>/dev/null || true

            print_success "System dependencies removed"
        else
            print_status "Skipped dependency removal"
        fi
    fi
}

cleanup_temp_files() {
    print_status "Cleaning up temporary files..."

    # Remove any temporary QR codes
    find /tmp -name "qr_*.png" -user root -delete 2>/dev/null || true

    # Remove any temporary certificates
    find /tmp -name "breaknwipe_*" -user root -delete 2>/dev/null || true

    print_success "Temporary files cleaned up"
}

verify_removal() {
    print_status "Verifying removal..."

    # Check if command still exists
    if command -v breaknwipe &> /dev/null; then
        print_warning "breaknwipe command still found in PATH"
    else
        print_success "breaknwipe command removed from PATH"
    fi

    # Check if directories were removed
    for dir in "$INSTALL_DIR" "$CONFIG_DIR" "$LOG_DIR" "$DATA_DIR"; do
        if [[ -d "$dir" ]]; then
            print_warning "Directory still exists: $dir"
        else
            print_success "Directory removed: $dir"
        fi
    done

    # Check if service was removed
    if systemctl is-active --quiet breaknwipe-daemon 2>/dev/null; then
        print_warning "Service still running"
    else
        print_success "Service stopped and removed"
    fi
}

show_completion_message() {
    echo
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}      BreakNWipe Uninstallation Complete!      ${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo
    echo -e "${BLUE}What was removed:${NC}"
    echo "  • BreakNWipe application files"
    echo "  • Configuration files"
    echo "  • Log files"
    echo "  • System service"
    echo "  • Binary commands (breaknwipe, bwipe)"
    echo "  • Bash completion"
    echo "  • Desktop entry"
    echo "  • System user and group"
    echo

    if [[ -n "$backup_dir" && -d "$backup_dir" ]]; then
        echo -e "${YELLOW}Important:${NC}"
        echo "  • Your data has been backed up to: $backup_dir"
        echo "  • You can safely delete this backup when no longer needed"
        echo
    fi

    echo -e "${BLUE}Manual cleanup (if needed):${NC}"
    echo "  • Check for any remaining BreakNWipe processes: ps aux | grep breaknwipe"
    echo "  • Remove any custom configurations you may have created"
    echo "  • Clear bash history if it contains sensitive commands"
    echo
    echo -e "${GREEN}BreakNWipe has been successfully removed from your system.${NC}"
    echo
}

# Main uninstallation process
main() {
    echo -e "${BLUE}BreakNWipe Uninstaller${NC}"
    echo -e "${BLUE}Secure Data Wiping Utility Removal${NC}"
    echo "====================================="
    echo

    check_root
    confirm_uninstall
    stop_services
    remove_systemd_service
    remove_binaries
    remove_directories
    remove_user_group
    remove_config_files
    clean_package_cache
    remove_dependencies
    cleanup_temp_files
    verify_removal
    show_completion_message
}

# Run main function
main "$@"