#!/bin/bash
#
# BreakNWipe Package Builder
# Builds .deb and .rpm packages for distribution
#
# Packages are self-contained: BreakNWipe's source + all its Python dependencies
# are vendored into a uv-managed virtual environment at /opt/breaknwipe/src/.venv
# (the same layout scripts/install.sh produces for a system-wide install), which
# is then wrapped as a plain directory tree with `fpm --input-type dir`. This
# deliberately avoids fpm's `--input-type python` mechanism: it auto-detects
# install paths from whatever Python is active on the *build machine* (silently
# baking in a broken, machine-specific path if that's a conda/pyenv env instead
# of the system one -- verified to actually happen), and on modern Ubuntu/Debian
# (Python 3.12+, distutils removed from the stdlib) it additionally requires
# python3-packaging/python3-pip just to run. The dir+venv approach sidesteps all
# of that: the only real package dependencies are the system tools BreakNWipe
# shells out to (hdparm, nvme-cli, smartmontools, util-linux), not Python itself.
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
PACKAGE_VERSION="$(grep -oP "(?<=__version__ = ')[^']+" breaknwipe/__init__.py)"
PACKAGE_RELEASE="1"
MAINTAINER="CodeBreakers Team <contact@breaknwipe.org>"
DESCRIPTION="Secure data wiping utility for IT asset recycling"
URL="https://github.com/41vi4p/BreakNWipe"

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

check_build_environment() {
    print_status "Checking build environment..."

    if [[ ! -f /etc/debian_version ]]; then
        print_warning "This does not look like a Debian/Ubuntu system (/etc/debian_version missing)."
        print_warning "Packages are still buildable, but this has only been tested on Debian/Ubuntu."
        print_warning "For a fully clean build, prefer running this inside a pinned container, e.g.:"
        print_warning "  docker run --rm -v \"\$(pwd)\":/src -w /src ubuntu:24.04 bash scripts/build_packages.sh"
    fi
}

check_dependencies() {
    print_status "Checking build dependencies..."

    # Check for required tools. Note: python3 itself is NOT required on the build
    # machine -- `uv sync` provisions its own managed Python inside the vendored
    # venv. Node/npm ARE required at build time to build the Next.js GUI into a
    # static bundle (baked into the package; not needed at runtime). The rest is
    # ruby/fpm (packaging) + uv (staging the venv) + rsync/dpkg-dev for mechanics.
    required_tools=("ruby" "dpkg-deb" "fpm" "uv" "rsync" "node" "npm")
    missing_tools=()

    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done

    if [ ${#missing_tools[@]} -ne 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        print_status "Installing missing dependencies..."

        apt update
        apt install -y ruby ruby-dev rubygems build-essential dpkg-dev rsync curl ca-certificates

        if ! command -v fpm &> /dev/null; then
            print_status "Installing fpm (Effing Package Management)..."
            gem install --no-document fpm
        fi

        if ! command -v uv &> /dev/null; then
            print_status "Installing uv..."
            curl -LsSf https://astral.sh/uv/install.sh | sh
            export PATH="$HOME/.local/bin:$PATH"
        fi

        # Node 20 (via NodeSource) -- distro nodejs is often too old for Next 16.
        if ! command -v node &> /dev/null || ! command -v npm &> /dev/null; then
            print_status "Installing Node.js 20 (build-time only, for the GUI)..."
            curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
            apt install -y nodejs
        fi
    fi

    print_success "Build dependencies verified"
}

prepare_build_environment() {
    print_status "Preparing build environment..."

    # Clean previous builds
    rm -rf "$BUILD_DIR" "$DIST_DIR"
    mkdir -p "$BUILD_DIR" "$DIST_DIR" "$PACKAGE_DIR"

    # Unlike a typical fpm dir-input build, this stages content directly at its
    # real final installation path (/opt/breaknwipe, /usr/bin) rather than a
    # separate pkgroot/ tree, then has fpm package it with `-C /`. This is
    # deliberate: `uv sync` bakes some *absolute* paths in at sync time --
    # the managed-Python interpreter symlink, and the project's own editable
    # install location -- and those only resolve correctly after `apt install`
    # if the path used at build time is identical to the path used at install
    # time. Verified the hard way: staging under a separate build/pkgroot/...
    # directory produced a package that failed on a different machine with
    # "No such file or directory" (broken interpreter symlink) and then
    # "ModuleNotFoundError: No module named 'breaknwipe'" (stale editable-install
    # reference) once that first bug was fixed. Building at the real path
    # avoids both, since this always runs inside a disposable/ephemeral build
    # container where writing to /opt and /usr directly is safe.
    rm -rf /opt/breaknwipe
    mkdir -p /opt/breaknwipe/src

    print_status "Staging source + uv-managed virtual environment..."
    # node_modules/.next/out are excluded from the source copy -- the GUI is
    # rebuilt fresh below, and we don't want a stale/huge build carried over.
    rsync -a \
        --exclude='.git' --exclude='.venv' --exclude='venv' \
        --exclude='__pycache__' --exclude='*.egg-info' \
        --exclude='build' --exclude='dist' --exclude='node_modules' \
        --exclude='.next' --exclude='out' \
        ./ /opt/breaknwipe/src/

    # Build the Next.js GUI into a static bundle (breaknwipe-gui/out) that the
    # FastAPI server serves at runtime. Node is only needed here at build time;
    # node_modules and .next are stripped afterward so only `out/` ships in the
    # package.
    print_status "Building the GUI (Next.js static export)..."
    local gui_dir="/opt/breaknwipe/src/breaknwipe/breaknwipe-gui"
    (cd "$gui_dir" && npm ci && npm run build)
    rm -rf "$gui_dir/node_modules" "$gui_dir/.next"

    # Force uv to download and use its own managed Python (--managed-python,
    # ignoring any build-machine system Python) so behavior is deterministic
    # regardless of what's installed on the build host, and point its install
    # dir at the same fixed path this package always installs to.
    export UV_PYTHON_INSTALL_DIR="/opt/breaknwipe/python"
    (cd /opt/breaknwipe/src && uv sync --no-dev --managed-python)

    cat > /usr/bin/breaknwipe << 'EOF'
#!/bin/bash
exec /opt/breaknwipe/src/.venv/bin/python -m breaknwipe.cli.main "$@"
EOF
    chmod +x /usr/bin/breaknwipe
    ln -sf breaknwipe /usr/bin/bwipe

    print_success "Build environment prepared"
}

build_deb_package() {
    print_status "Building Debian package..."

    local deb_dir="$PACKAGE_DIR/deb"
    mkdir -p "$deb_dir"

    # Package the pre-built /opt/breaknwipe + /usr/bin (source + uv venv +
    # managed Python + wrapper) as a plain directory tree, built directly at
    # those real absolute paths -- see prepare_build_environment() for why.
    # No python3 dependency is declared: the venv is fully self-contained
    # (uv's own managed Python is vendored in), and its compiled extensions
    # (numpy, cryptography, pydantic-core, ...) are architecture-specific,
    # hence --architecture amd64 rather than the old "all".
    fpm \
        --input-type dir \
        --output-type deb \
        --name "$PACKAGE_NAME" \
        --version "$PACKAGE_VERSION" \
        --iteration "$PACKAGE_RELEASE" \
        --maintainer "$MAINTAINER" \
        --description "$DESCRIPTION" \
        --url "$URL" \
        --license "GPL-3.0-or-later" \
        --vendor "CodeBreakers Team" \
        --category "admin" \
        --architecture "amd64" \
        --depends "smartmontools" \
        --depends "hdparm" \
        --depends "nvme-cli" \
        --depends "util-linux" \
        --depends "parted" \
        --depends "cloud-guest-utils" \
        --depends "lvm2" \
        --depends "xfsprogs" \
        --depends "ntfs-3g" \
        --depends "btrfs-progs" \
        --depends "sleuthkit" \
        --depends "testdisk" \
        --package "$deb_dir" \
        --after-install scripts/postinst \
        --before-remove scripts/prerm \
        --after-remove scripts/postrm \
        --deb-suggests "parted" \
        --deb-suggests "lsblk" \
        -C / opt/breaknwipe usr/bin/breaknwipe usr/bin/bwipe

    print_success "Debian package built: $deb_dir/${PACKAGE_NAME}_${PACKAGE_VERSION}-${PACKAGE_RELEASE}_amd64.deb"
}

build_rpm_package() {
    print_status "Building RPM package..."

    if ! command -v rpmbuild &> /dev/null; then
        print_warning "rpmbuild not found, skipping RPM package (install 'rpm' to enable this)"
        return 0
    fi

    local rpm_dir="$PACKAGE_DIR/rpm"
    mkdir -p "$rpm_dir"

    # Same self-contained /opt/breaknwipe + /usr/bin as build_deb_package --
    # see its comment above.
    fpm \
        --input-type dir \
        --output-type rpm \
        --name "$PACKAGE_NAME" \
        --version "$PACKAGE_VERSION" \
        --iteration "$PACKAGE_RELEASE" \
        --maintainer "$MAINTAINER" \
        --description "$DESCRIPTION" \
        --url "$URL" \
        --license "GPL-3.0-or-later" \
        --vendor "CodeBreakers Team" \
        --category "Applications/System" \
        --architecture "x86_64" \
        --depends "smartmontools" \
        --depends "hdparm" \
        --depends "nvme-cli" \
        --depends "util-linux" \
        --depends "parted" \
        --depends "cloud-guest-utils" \
        --depends "lvm2" \
        --depends "xfsprogs" \
        --depends "ntfs-3g" \
        --depends "btrfs-progs" \
        --depends "sleuthkit" \
        --depends "testdisk" \
        --package "$rpm_dir" \
        --after-install scripts/postinst \
        --before-remove scripts/prerm \
        --after-remove scripts/postrm \
        -C / opt/breaknwipe usr/bin/breaknwipe usr/bin/bwipe

    print_success "RPM package built: $rpm_dir/${PACKAGE_NAME}-${PACKAGE_VERSION}-${PACKAGE_RELEASE}.x86_64.rpm"
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
    useradd --system --gid breaknwipe --shell /bin/false \
            --home-dir /opt/breaknwipe --no-create-home \
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

# Shell completion, generated dynamically from the actual Click command tree
# (cli/main.py pins prog_name='breaknwipe' so this works regardless of how
# the vendored venv's python is invoked). /etc/bash_completion.d is
# bash-completion's legacy "compat" drop-in dir -- still actively scanned if
# bash-completion is installed, but not guaranteed to already exist.
if [ -d /usr/share/bash-completion ]; then
    mkdir -p /etc/bash_completion.d
    if _BREAKNWIPE_COMPLETE=bash_source /opt/breaknwipe/src/.venv/bin/python -m breaknwipe.cli.main > /etc/bash_completion.d/breaknwipe 2>/dev/null; then
        echo 'complete -o nosort -F _breaknwipe_completion bwipe 2>/dev/null || true' >> /etc/bash_completion.d/breaknwipe
    else
        rm -f /etc/bash_completion.d/breaknwipe
    fi
fi

echo "BreakNWipe installation completed successfully"
echo "Run 'sudo breaknwipe --interactive' to get started"
EOF

    # Pre-removal script
    cat > "$scripts_dir/prerm" << 'EOF'
#!/bin/bash
# BreakNWipe pre-removal script

set -e
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

        rm -f /etc/bash_completion.d/breaknwipe
        ;;
esac
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
        cp scripts/install.sh "$appdir/usr/bin/breaknwipe"
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

    # Create checksums for all packages. Excludes repository/ since that's a
    # copy of these same files created later by create_repository_metadata()
    # -- without the exclusion this would checksum each package twice.
    find . -not -path "*/repository/*" \( -name "*.deb" -o -name "*.rpm" -o -name "*.AppImage" \) | while read -r file; do
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
        find . -name "*.sha256" -exec cat {} \;
    } > "checksums.txt"

    cd - > /dev/null
    print_success "Checksums created"
}

create_repository_metadata() {
    print_status "Creating repository metadata..."

    local repo_dir="$PACKAGE_DIR/repository"
    mkdir -p "$repo_dir/deb" "$repo_dir/rpm"

    # Copy packages to repository structure. Search only the specific deb/rpm
    # output dirs (not all of $PACKAGE_DIR) so this doesn't recurse into
    # $repo_dir itself, which lives nested under $PACKAGE_DIR/repository.
    find "$PACKAGE_DIR/deb" -maxdepth 1 -name "*.deb" -exec cp {} "$repo_dir/deb/" \;
    find "$PACKAGE_DIR/rpm" -maxdepth 1 -name "*.rpm" -exec cp {} "$repo_dir/rpm/" \; 2>/dev/null || true

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

    find "$PACKAGE_DIR" -not -path "*/repository/*" \( -name "*.deb" -o -name "*.rpm" -o -name "*.AppImage" \) | while read -r file; do
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
    echo -e "  • Debian/Ubuntu: ${GREEN}sudo dpkg -i breaknwipe_*.deb${NC}"
    echo -e "  • Red Hat/Fedora: ${GREEN}sudo rpm -i breaknwipe-*.rpm${NC}"
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

    check_build_environment
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