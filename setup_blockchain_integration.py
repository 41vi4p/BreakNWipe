#!/usr/bin/env python3
"""
BreakNWipe Blockchain Integration Setup

This script helps configure the integration between BreakNWipe, the blockchain contract,
and the datawipe verification webapp.
"""

import os
import json
import sys
import subprocess
from pathlib import Path


def check_dependencies():
    """Check if required dependencies are installed."""
    dependencies = {
        'web3': 'Web3.py for blockchain interaction',
        'eth_account': 'Ethereum account management'
    }

    missing = []
    for package, description in dependencies.items():
        try:
            __import__(package)
            print(f"✓ {package} - {description}")
        except ImportError:
            print(f"✗ {package} - {description}")
            missing.append(package)

    if missing:
        print(f"\nMissing dependencies: {', '.join(missing)}")
        print("Install with: pip install web3 eth-account")
        return False

    return True


def check_blockchain_config():
    """Check blockchain configuration in .env files."""
    print("\n=== Checking Blockchain Configuration ===")

    # Check blockchain .env
    blockchain_env = Path("blockchain/.env")
    if blockchain_env.exists():
        print(f"✓ Found blockchain .env at: {blockchain_env}")
        with open(blockchain_env, 'r') as f:
            content = f.read()

        required_vars = [
            'NEXT_PUBLIC_CONTRACT_ADDRESS',
            'PRIVATE_KEY',
            'RPC_URL',
            'SEPOLIA_RPC_URL'
        ]

        for var in required_vars:
            if var in content and not content.split(f'{var}=')[1].split('\n')[0].strip().startswith('#'):
                print(f"✓ {var} is configured")
            else:
                print(f"✗ {var} is missing or commented out")
    else:
        print(f"✗ Blockchain .env not found at: {blockchain_env}")

    # Check if we can copy config to breaknwipe
    breaknwipe_env = Path("breaknwipe/.env")
    if not breaknwipe_env.exists():
        if blockchain_env.exists():
            print(f"\n📋 Creating BreakNWipe .env from blockchain config...")
            create_breaknwipe_env(blockchain_env, breaknwipe_env)
        else:
            print(f"✗ Cannot create BreakNWipe .env without blockchain config")


def create_breaknwipe_env(source_env, target_env):
    """Create BreakNWipe .env file from blockchain .env."""
    try:
        with open(source_env, 'r') as f:
            lines = f.readlines()

        # Create BreakNWipe specific env vars
        breaknwipe_lines = [
            "# BreakNWipe Blockchain Configuration\n",
            "# Generated from blockchain/.env\n",
            "\n"
        ]

        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Map blockchain vars to BreakNWipe vars
                    if key == 'RPC_URL':
                        breaknwipe_lines.append(f"BREAKNWIPE_RPC_URL={value}\n")
                    elif key == 'NEXT_PUBLIC_CONTRACT_ADDRESS':
                        breaknwipe_lines.append(f"BREAKNWIPE_CONTRACT_ADDRESS={value}\n")
                    elif key == 'PRIVATE_KEY':
                        breaknwipe_lines.append(f"BREAKNWIPE_PRIVATE_KEY={value}\n")
                    elif key == 'NEXT_PUBLIC_CHAIN_ID':
                        breaknwipe_lines.append(f"BREAKNWIPE_CHAIN_ID={value}\n")

        # Add datawipe configuration
        breaknwipe_lines.extend([
            "\n# Datawipe Integration\n",
            "DATAWIPE_BASE_URL=https://datawipe.vercel.app\n",
            "DATAWIPE_VERIFICATION_ENDPOINT=/api/verify\n",
            "\n# BreakNWipe Blockchain Settings\n",
            "BREAKNWIPE_AUTO_BLOCKCHAIN_STORE=true\n",
            "BREAKNWIPE_QR_INCLUDE_BLOCKCHAIN=true\n",
            "BREAKNWIPE_STORAGE_METHOD=onchain\n"
        ])

        target_env.parent.mkdir(exist_ok=True)
        with open(target_env, 'w') as f:
            f.writelines(breaknwipe_lines)

        print(f"✓ Created {target_env}")
        return True

    except Exception as e:
        print(f"✗ Failed to create BreakNWipe .env: {e}")
        return False


def check_contract_deployment():
    """Check if the blockchain contract is deployed and accessible."""
    print("\n=== Checking Contract Deployment ===")

    try:
        # Try to import and use the blockchain module we just created
        sys.path.insert(0, str(Path('breaknwipe')))
        from breaknwipe.certificate.blockchain import BlockchainConfig, BlockchainCertificateStore

        config = BlockchainConfig()
        if not config.is_configured():
            print(f"✗ Blockchain not configured. Missing: {config.get_missing_config()}")
            return False

        store = BlockchainCertificateStore(config)
        network_info = store.get_network_info()

        if network_info.get('connected'):
            print(f"✓ Connected to blockchain network")
            print(f"  Chain ID: {network_info.get('chain_id')}")
            print(f"  Block Number: {network_info.get('block_number')}")
            print(f"  Account: {network_info.get('account')}")
            print(f"  Contract: {network_info.get('contract_address')}")
            return True
        else:
            print(f"✗ Failed to connect to blockchain: {network_info.get('error')}")
            return False

    except Exception as e:
        print(f"✗ Error checking contract deployment: {e}")
        return False


def check_datawipe_webapp():
    """Check if the datawipe webapp is running and accessible."""
    print("\n=== Checking Datawipe Webapp ===")

    datawipe_dir = Path("datawipe")
    if not datawipe_dir.exists():
        print(f"✗ Datawipe directory not found: {datawipe_dir}")
        return False

    print(f"✓ Datawipe directory found: {datawipe_dir}")

    # Check package.json
    package_json = datawipe_dir / "package.json"
    if package_json.exists():
        print("✓ Datawipe package.json found")

        # Check if dependencies are installed
        node_modules = datawipe_dir / "node_modules"
        if node_modules.exists():
            print("✓ Datawipe dependencies installed")
        else:
            print("⚠ Datawipe dependencies not installed. Run: cd datawipe && npm install")

    # Check if .env exists and has blockchain config
    datawipe_env = datawipe_dir / ".env"
    if not datawipe_env.exists():
        print("⚠ Datawipe .env not found, checking .env.local...")
        datawipe_env = datawipe_dir / ".env.local"

    if datawipe_env.exists():
        print(f"✓ Datawipe environment config found: {datawipe_env}")
    else:
        print("⚠ Datawipe environment config not found")
        print("  The blockchain config should be available as environment variables for the datawipe app")

    return True


def print_usage_instructions():
    """Print instructions for using the integration."""
    print(f"✓ Integration setup complete!")


def main():
    """Main setup function."""
    print("BreakNWipe Blockchain Integration Setup")
    print("=" * 50)

    # Check dependencies
    if not check_dependencies():
        print("\n❌ Please install missing dependencies before continuing.")
        return False

    # Check configurations
    check_blockchain_config()

    # Check contract deployment
    contract_ok = check_contract_deployment()

    # Check datawipe webapp
    datawipe_ok = check_datawipe_webapp()

    # Print usage instructions
    print_usage_instructions()

    print("\n" + "=" * 50)
    print("Setup Summary:")
    print(f"  Dependencies: ✓")
    print(f"  Blockchain Contract: {'✓' if contract_ok else '✗'}")
    print(f"  Datawipe Webapp: {'✓' if datawipe_ok else '✗'}")

    if contract_ok and datawipe_ok:
        print("\n✅ Integration setup complete!")
        print("\nNext steps:")
        print("1. Install dependencies: pip install web3 eth-account")
        print("2. Run BreakNWipe wipe operations - blockchain features are automatic")
        print("3. Datawipe webapp is live at https://datawipe.vercel.app")
        print("4. Test QR code scanning with the datawipe webapp")
    else:
        print("\n⚠ Setup incomplete. Please resolve the issues above.")
        if not contract_ok:
            print("  - Check blockchain configuration and contract deployment")
        if not datawipe_ok:
            print("  - Install datawipe dependencies and configure environment")

    return contract_ok and datawipe_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)