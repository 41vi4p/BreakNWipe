#!/bin/bash
#
# BreakNWipe Wrapper Script
#

VENV_DIR="/home/alienware_ubuntu/Desktop/BreakNWipe/venv"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "Error: BreakNWipe requires root privileges"
    echo "Please run with sudo: sudo breaknwipe [options]"
    exit 1
fi

# Activate virtual environment and run BreakNWipe
exec "$VENV_DIR/bin/python" -m breaknwipe.cli.main "$@"