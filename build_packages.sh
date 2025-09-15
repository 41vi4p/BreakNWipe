#!/bin/bash
#
# BreakNWipe Package Builder
# Builds .deb and .rpm packages for distribution
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PACKAGE_NAME="breaknwipe"
PACKAGE_VERSION="1.0.0"
PACKAGE_RELEASE="1"
MAINTAINER="CodeBreakers Team <contact@breaknwipe.org>"
DESCRIPTION="Secure data wiping utility for IT asset recycling"
URL="https://github.com/breaknwipe/breaknwipe"

# Directories
BUILD_DIR="$(pwd)/build"
DIST_DIR="$(pwd)/dist"
PACKAGE_DIR="$BUILD_DIR/packages"

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

check_dependencies() {
    print_status "Checking build dependencies..."

    # Check for required tools
    required_tools=("python3" "python3-setuptools" "dpkg-deb" "fpm")
    missing_tools=()

    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done

    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        print_status "Installing missing dependencies..."

        # Install missing tools
        apt update
        apt install -y python3 python3-setuptools dpkg-dev

        # Install fpm if not available
        if ! command -v fpm &> /dev/null; then
            print_status "Installing fpm (Effing Package Management)..."
            apt install -y ruby ruby-dev rubygems build-essential
            gem install --no-document fpm
        fi
    fi

    print_success "Build dependencies verified"
}

prepare_build_environment() {
    print_status "Preparing build environment..."

    # Clean previous builds
    rm -rf "$BUILD_DIR" "$DIST_DIR"
    mkdir -p "$BUILD_DIR" "$DIST_DIR" "$PACKAGE_DIR"

    # Create source distribution
    python3 setup.py sdist

    print_success "Build environment prepared"
}

build_deb_package() {
    print_status "Building Debian package..."

    local deb_dir="$PACKAGE_DIR/deb"
    mkdir -p "$deb_dir"

    # Use fpm to build .deb package
    fpm \\
        --input-type python \\
        --output-type deb \\
        --name "$PACKAGE_NAME" \\
        --version "$PACKAGE_VERSION" \\
        --iteration "$PACKAGE_RELEASE" \\
        --maintainer "$MAINTAINER" \\
        --description "$DESCRIPTION" \\
        --url "$URL" \\
        --license "MIT" \\
        --vendor "CodeBreakers Team" \\
        --category "admin" \\
        --architecture "all" \\
        --depends "python3 >= 3.8" \\
        --depends "python3-pip" \\
        --depends "smartmontools" \\
        --depends "hdparm" \\
        --depends "nvme-cli" \\
        --depends "util-linux" \\
        --package "$deb_dir" \\
        --after-install scripts/postinst \\
        --before-remove scripts/prerm \\
        --after-remove scripts/postrm \\
        --deb-suggests "parted" \\
        --deb-suggests "lsblk" \\
        setup.py

    print_success "Debian package built: $deb_dir/${PACKAGE_NAME}_${PACKAGE_VERSION}-${PACKAGE_RELEASE}_all.deb"
}

build_rpm_package() {
    print_status "Building RPM package..."

    local rpm_dir="$PACKAGE_DIR/rpm"
    mkdir -p "$rpm_dir"

    # Use fpm to build .rpm package
    fpm \\
        --input-type python \\
        --output-type rpm \\
        --name "$PACKAGE_NAME" \\
        --version "$PACKAGE_VERSION" \\
        --iteration "$PACKAGE_RELEASE" \\
        --maintainer "$MAINTAINER" \\
        --description "$DESCRIPTION" \\
        --url "$URL" \\
        --license "MIT" \\
        --vendor "CodeBreakers Team" \\
        --category "Applications/System" \\
        --architecture "noarch" \\
        --depends "python3 >= 3.8" \\
        --depends "python3-pip" \\
        --depends "smartmontools" \\
        --depends "hdparm" \\
        --depends "nvme-cli" \\
        --depends "util-linux" \\
        --package "$rpm_dir" \\
        --after-install scripts/postinst \\
        --before-remove scripts/prerm \\
        --after-remove scripts/postrm \\
        setup.py

    print_success "RPM package built: $rpm_dir/${PACKAGE_NAME}-${PACKAGE_VERSION}-${PACKAGE_RELEASE}.noarch.rpm"
}

create_package_scripts() {
    print_status "Creating package scripts..."

    local scripts_dir="scripts"
    mkdir -p "$scripts_dir"

    # Post-installation script
    cat > "$scripts_dir/postinst" << 'EOF'
#!/bin/bash
# BreakNWipe post-installation script

set -e

# Create system user and group
if ! getent group breaknwipe > /dev/null 2>&1; then
    groupadd --system breaknwipe
fi

if ! getent passwd breaknwipe > /dev/null 2>&1; then
    useradd --system --gid breaknwipe --shell /bin/false \\
            --home-dir /opt/breaknwipe --no-create-home \\
            breaknwipe
fi

# Create directories
mkdir -p /etc/breaknwipe
mkdir -p /var/log/breaknwipe
mkdir -p /var/lib/breaknwipe/reports
mkdir -p /var/lib/breaknwipe/certificates

# Set ownership and permissions
chown -R breaknwipe:breaknwipe /var/log/breaknwipe
chown -R breaknwipe:breaknwipe /var/lib/breaknwipe
chmod 750 /etc/breaknwipe
chmod 750 /var/log/breaknwipe
chmod 750 /var/lib/breaknwipe

# Enable and start service if systemd is available
if command -v systemctl > /dev/null 2>&1; then
    systemctl daemon-reload
    systemctl enable breaknwipe-daemon || true
fi

echo "BreakNWipe installation completed successfully"
echo "Run 'sudo breaknwipe --interactive' to get started"
EOF

    # Pre-removal script
    cat > "$scripts_dir/prerm" << 'EOF'
#!/bin/bash
# BreakNWipe pre-removal script

set -e

# Stop service if running
if command -v systemctl > /dev/null 2>&1; then
    systemctl stop breaknwipe-daemon || true
    systemctl disable breaknwipe-daemon || true
fi
EOF

    # Post-removal script
    cat > "$scripts_dir/postrm" << 'EOF'
#!/bin/bash
# BreakNWipe post-removal script

set -e

case "$1" in
    remove|purge)
        # Remove system user and group
        if getent passwd breaknwipe > /dev/null 2>&1; then
            userdel breaknwipe || true
        fi

        if getent group breaknwipe > /dev/null 2>&1; then
            groupdel breaknwipe || true
        fi

        # Remove directories if purging
        if [ "$1" = "purge" ]; then
            rm -rf /var/log/breaknwipe
            rm -rf /var/lib/breaknwipe
            rm -rf /etc/breaknwipe
        fi
        ;;
esac

# Reload systemd if available
if command -v systemctl > /dev/null 2>&1; then
    systemctl daemon-reload || true
fi
EOF

    chmod +x "$scripts_dir"/*
    print_success "Package scripts created"
}

build_appimage() {
    print_status "Building AppImage..."

    # AppImage is more complex and requires appimagetool
    if command -v appimagetool &> /dev/null; then
        local appdir="$PACKAGE_DIR/BreakNWipe.AppDir"
        mkdir -p "$appdir"

        # Create AppDir structure
        mkdir -p "$appdir/usr/bin"
        mkdir -p "$appdir/usr/share/applications"
        mkdir -p "$appdir/usr/share/icons/hicolor/256x256/apps"

        # Copy files
        cp install.sh "$appdir/usr/bin/breaknwipe"
        cp breaknwipe.desktop "$appdir/usr/share/applications/" 2>/dev/null || true

        # Create AppRun
        cat > "$appdir/AppRun" << 'EOF'
#!/bin/bash
exec "$APPDIR/usr/bin/breaknwipe" "$@"
EOF
        chmod +x "$appdir/AppRun"

        # Build AppImage
        appimagetool "$appdir" "$PACKAGE_DIR/BreakNWipe-${PACKAGE_VERSION}-x86_64.AppImage"

        print_success "AppImage created: BreakNWipe-${PACKAGE_VERSION}-x86_64.AppImage"
    else
        print_warning "appimagetool not found, skipping AppImage creation"
    fi
}

create_checksums() {
    print_status "Creating checksums..."

    cd "$PACKAGE_DIR"

    # Create checksums for all packages
    find . -name "*.deb" -o -name "*.rpm" -o -name "*.AppImage" | while read -r file; do
        if [[ -f "$file" ]]; then
            sha256sum "$file" > "${file}.sha256"
            md5sum "$file" > "${file}.md5"
        fi
    done

    # Create combined checksum file
    {
        echo "# BreakNWipe $PACKAGE_VERSION Package Checksums"
        echo "# Generated on $(date)"
        echo ""
        find . -name "*.sha256" -exec cat {} \\;
    } > "checksums.txt"

    cd - > /dev/null
    print_success "Checksums created"
}

create_repository_metadata() {
    print_status "Creating repository metadata..."

    local repo_dir="$PACKAGE_DIR/repository"
    mkdir -p "$repo_dir/deb" "$repo_dir/rpm"

    # Copy packages to repository structure
    find "$PACKAGE_DIR" -name "*.deb" -exec cp {} "$repo_dir/deb/" \\;
    find "$PACKAGE_DIR" -name "*.rpm" -exec cp {} "$repo_dir/rpm/" \\;

    # Create APT repository (basic)
    cd "$repo_dir/deb"
    if command -v dpkg-scanpackages &> /dev/null; then
        dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz
        print_success "Created APT repository metadata"
    fi

    # Create YUM repository
    cd ../rpm
    if command -v createrepo &> /dev/null; then
        createrepo .
        print_success "Created YUM repository metadata"
    fi

    cd - > /dev/null
}

show_build_summary() {
    echo
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}         Package Build Complete!               ${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo
    echo -e "${BLUE}Built packages:${NC}"

    find "$PACKAGE_DIR" -name "*.deb" -o -name "*.rpm" -o -name "*.AppImage" | while read -r file; do
        if [[ -f "$file" ]]; then
            size=$(du -h "$file" | cut -f1)
            echo "  • $(basename "$file") ($size)"
        fi
    done

    echo
    echo -e "${BLUE}Package locations:${NC}"
    echo "  • Debian packages: $PACKAGE_DIR/deb/"
    echo "  • RPM packages: $PACKAGE_DIR/rpm/"
    echo "  • Repository: $PACKAGE_DIR/repository/"
    echo
    echo -e "${BLUE}Installation commands:${NC}"
    echo "  • Debian/Ubuntu: ${GREEN}sudo dpkg -i breaknwipe_*.deb${NC}"
    echo "  • Red Hat/Fedora: ${GREEN}sudo rpm -i breaknwipe-*.rpm${NC}"
    echo
    echo -e "${BLUE}Repository setup:${NC}"
    echo "  • For APT: Copy deb/ contents to your repository"
    echo "  • For YUM: Copy rpm/ contents to your repository"
    echo
    echo -e "${GREEN}All packages built successfully!${NC}"
    echo
}

# Main build process
main() {
    echo -e "${BLUE}BreakNWipe Package Builder${NC}"
    echo -e "${BLUE}Building distribution packages...${NC}"
    echo "=================================="
    echo

    check_dependencies
    prepare_build_environment
    create_package_scripts
    build_deb_package
    build_rpm_package
    build_appimage
    create_checksums
    create_repository_metadata
    show_build_summary
}

# Run main function
main "$@"