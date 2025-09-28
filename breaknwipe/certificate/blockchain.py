"""
Blockchain Integration Module

Provides blockchain functionality for storing and verifying wipe certificates
on Ethereum-compatible networks (Sepolia testnet).
"""

import os
import json
import logging
import time
from typing import Optional, Dict, Any, Union
from pathlib import Path

try:
    from web3 import Web3
    from eth_account import Account
    import requests
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    Web3 = None
    Account = None

from .report import WipeReport

logger = logging.getLogger(__name__)


class BlockchainConfig:
    """Configuration for blockchain operations."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize blockchain configuration."""
        self.rpc_url = None
        self.contract_address = None
        self.private_key = None
        self.chain_id = None
        self.gas_limit = 500000
        self.gas_price_gwei = 20

        # Load configuration from environment or file
        self._load_config(config_path)

    def _load_config(self, config_path: Optional[str] = None):
        """Load configuration from environment variables or config file."""
        # Try environment variables first
        self.rpc_url = os.getenv('BREAKNWIPE_RPC_URL', os.getenv('RPC_URL'))
        self.contract_address = os.getenv('BREAKNWIPE_CONTRACT_ADDRESS',
                                        os.getenv('NEXT_PUBLIC_CONTRACT_ADDRESS'))
        self.private_key = os.getenv('BREAKNWIPE_PRIVATE_KEY', os.getenv('PRIVATE_KEY'))
        self.chain_id = os.getenv('BREAKNWIPE_CHAIN_ID', os.getenv('NEXT_PUBLIC_CHAIN_ID', '11155111'))

        # Load from config file if provided
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)

                self.rpc_url = config.get('rpc_url', self.rpc_url)
                self.contract_address = config.get('contract_address', self.contract_address)
                self.private_key = config.get('private_key', self.private_key)
                self.chain_id = config.get('chain_id', self.chain_id)
                self.gas_limit = config.get('gas_limit', self.gas_limit)
                self.gas_price_gwei = config.get('gas_price_gwei', self.gas_price_gwei)

            except Exception as e:
                logger.warning(f"Failed to load blockchain config from {config_path}: {e}")

        # Convert chain_id to int
        if isinstance(self.chain_id, str):
            self.chain_id = int(self.chain_id)

    def is_configured(self) -> bool:
        """Check if blockchain is properly configured."""
        return bool(
            self.rpc_url and
            self.contract_address and
            self.private_key and
            self.chain_id
        )

    def get_missing_config(self) -> list:
        """Get list of missing configuration items."""
        missing = []
        if not self.rpc_url:
            missing.append('rpc_url')
        if not self.contract_address:
            missing.append('contract_address')
        if not self.private_key:
            missing.append('private_key')
        if not self.chain_id:
            missing.append('chain_id')
        return missing


class BlockchainCertificateStore:
    """Stores and retrieves certificates from blockchain."""

    def __init__(self, config: Optional[BlockchainConfig] = None):
        """Initialize blockchain certificate store."""
        if not WEB3_AVAILABLE:
            raise ImportError("web3 and eth_account packages required for blockchain functionality")

        self.config = config or BlockchainConfig()
        self.web3 = None
        self.contract = None
        self.account = None

        # Load contract ABI
        self.contract_abi = self._load_contract_abi()

        if self.config.is_configured():
            self._initialize_connection()

    def _load_contract_abi(self) -> list:
        """Load contract ABI from the blockchain project."""
        abi_paths = [
            # Check in blockchain folder
            Path(__file__).parent.parent.parent / "blockchain" / "artifacts" / "contracts" / "ReportRegistryWithJson.sol" / "ReportRegistryWithJson.json",
            # Check in datawipe folder
            Path(__file__).parent.parent.parent / "datawipe" / "src" / "lib" / "ABI" / "ReportRegistryWithJson.json",
        ]

        for abi_path in abi_paths:
            if abi_path.exists():
                try:
                    with open(abi_path, 'r') as f:
                        artifact = json.load(f)
                        # Handle both artifact format and direct ABI format
                        if 'abi' in artifact:
                            return artifact['abi']
                        elif isinstance(artifact, list):
                            return artifact
                except Exception as e:
                    logger.debug(f"Failed to load ABI from {abi_path}: {e}")
                    continue

        # Fallback minimal ABI
        logger.warning("Using fallback contract ABI")
        return [
            {
                "inputs": [{"internalType": "string", "name": "reportJson", "type": "string"}],
                "name": "storeReportOnChain",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [{"internalType": "bytes32", "name": "reportHash", "type": "bytes32"}],
                "name": "verifyReport",
                "outputs": [
                    {"internalType": "bool", "name": "exists", "type": "bool"},
                    {"internalType": "address", "name": "submitter", "type": "address"},
                    {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                    {"internalType": "bool", "name": "storedOnChain", "type": "bool"},
                    {"internalType": "string", "name": "ipfsCid", "type": "string"}
                ],
                "stateMutability": "view",
                "type": "function"
            }
        ]

    def _initialize_connection(self):
        """Initialize Web3 connection and contract."""
        try:
            # Initialize Web3
            self.web3 = Web3(Web3.HTTPProvider(self.config.rpc_url))

            if not self.web3.is_connected():
                raise ConnectionError("Failed to connect to blockchain network")

            # Initialize account
            self.account = Account.from_key(self.config.private_key)

            # Initialize contract
            self.contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(self.config.contract_address),
                abi=self.contract_abi
            )

            logger.info(f"Blockchain connection initialized - Chain ID: {self.config.chain_id}")

        except Exception as e:
            logger.error(f"Failed to initialize blockchain connection: {e}")
            raise

    def store_certificate(self, report: WipeReport, storage_method: str = "hash") -> Dict[str, Any]:
        """
        Store certificate on blockchain.

        Args:
            report: WipeReport to store
            storage_method: "hash" (only hash), "json" (full JSON), "onchain" (expensive)

        Returns:
            Dictionary with transaction details
        """
        if not self.config.is_configured():
            raise ValueError(f"Blockchain not configured. Missing: {self.config.get_missing_config()}")

        if not self.web3 or not self.contract:
            self._initialize_connection()

        try:
            # Convert report to JSON
            report_data = self._prepare_report_data(report)
            report_json = json.dumps(report_data, separators=(',', ':'), sort_keys=True)

            # Calculate hash
            report_hash = Web3.keccak(text=report_json)

            # Check if already exists
            try:
                exists_result = self.contract.functions.verifyReport(report_hash).call()
                if exists_result[0]:  # exists
                    return {
                        'success': True,
                        'already_exists': True,
                        'report_hash': report_hash.hex(),
                        'transaction_hash': None,
                        'timestamp': exists_result[2]
                    }
            except Exception as e:
                logger.debug(f"Error checking existing report: {e}")

            # Prepare transaction based on storage method
            if storage_method == "onchain":
                # Store full JSON on-chain (expensive)
                function_call = self.contract.functions.storeReportOnChain(report_json)
            else:
                # Default to hash-only storage (we'll implement this if the contract supports it)
                function_call = self.contract.functions.storeReportOnChain(report_json)

            # Estimate gas
            try:
                gas_estimate = function_call.estimate_gas({
                    'from': self.account.address
                })
                gas_limit = min(gas_estimate + 50000, self.config.gas_limit)
            except Exception as e:
                logger.warning(f"Gas estimation failed: {e}, using default")
                gas_limit = self.config.gas_limit

            # Get current gas price
            try:
                gas_price = self.web3.eth.gas_price
            except:
                gas_price = Web3.to_wei(self.config.gas_price_gwei, 'gwei')

            # Build transaction
            transaction = function_call.build_transaction({
                'from': self.account.address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': self.web3.eth.get_transaction_count(self.account.address),
                'chainId': self.config.chain_id
            })

            # Sign and send transaction
            signed_txn = self.web3.eth.account.sign_transaction(transaction, self.config.private_key)
            tx_hash = self.web3.eth.send_raw_transaction(signed_txn.rawTransaction)

            # Wait for confirmation
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)

            if receipt.status == 1:
                logger.info(f"Certificate stored on blockchain: {tx_hash.hex()}")
                return {
                    'success': True,
                    'already_exists': False,
                    'report_hash': report_hash.hex(),
                    'transaction_hash': tx_hash.hex(),
                    'block_number': receipt.blockNumber,
                    'gas_used': receipt.gasUsed,
                    'timestamp': int(time.time())
                }
            else:
                raise Exception(f"Transaction failed with status: {receipt.status}")

        except Exception as e:
            logger.error(f"Failed to store certificate on blockchain: {e}")
            return {
                'success': False,
                'error': str(e),
                'report_hash': None,
                'transaction_hash': None
            }

    def verify_certificate(self, report_hash: str) -> Dict[str, Any]:
        """
        Verify certificate exists on blockchain.

        Args:
            report_hash: Hash of the report to verify

        Returns:
            Verification result dictionary
        """
        if not self.config.is_configured():
            raise ValueError(f"Blockchain not configured. Missing: {self.config.get_missing_config()}")

        if not self.web3 or not self.contract:
            self._initialize_connection()

        try:
            # Ensure hash is bytes32 format
            if isinstance(report_hash, str):
                if report_hash.startswith('0x'):
                    hash_bytes = bytes.fromhex(report_hash[2:])
                else:
                    hash_bytes = bytes.fromhex(report_hash)
            else:
                hash_bytes = report_hash

            # Call contract
            result = self.contract.functions.verifyReport(hash_bytes).call()

            return {
                'exists': result[0],
                'submitter': result[1],
                'timestamp': result[2],
                'stored_on_chain': result[3],
                'ipfs_cid': result[4] if len(result) > 4 else "",
                'block_verified': True
            }

        except Exception as e:
            logger.error(f"Failed to verify certificate on blockchain: {e}")
            return {
                'exists': False,
                'error': str(e),
                'block_verified': False
            }

    def _prepare_report_data(self, report: WipeReport) -> Dict[str, Any]:
        """Prepare report data for blockchain storage."""
        # Create a compact report suitable for blockchain
        return {
            'report_id': report.report_id,
            'device_model': report.device_info.model if report.device_info else 'Unknown',
            'device_serial': report.device_info.serial if report.device_info else 'Unknown',
            'algorithm': report.algorithm_used or 'Unknown',
            'success': report.success,
            'completed_at': time.strftime('%Y-%m-%dT%H:%M:%S.%fZ', time.gmtime(report.end_time)),
            'operator': report.operator or 'System',
            'verification_url': f'https://verify.breaknwipe.org/{report.report_id}',
            'certificate_hash': report.certificate_hash,
            'software_version': report.software_version
        }

    def get_verification_url(self, report_id: str) -> str:
        """Get verification URL for the datawipe system."""
        # This should point to your hosted datawipe application
        datawipe_base_url = os.getenv('DATAWIPE_BASE_URL', 'https://datawipe.vercel.app')
        return f"{datawipe_base_url}?data={report_id}"

    def create_blockchain_qr_data(self, report: WipeReport, blockchain_result: Dict[str, Any]) -> Dict[str, Any]:
        """Create QR data that includes blockchain verification information."""
        qr_data = {
            'type': 'breaknwipe_blockchain_certificate',
            'version': '2.0',
            'report_id': report.report_id,
            'device_serial': report.device_info.serial if report.device_info else 'Unknown',
            'success': report.success,
            'algorithm': report.algorithm_used,
            'timestamp': int(report.end_time),
            'operator': report.operator or 'System',
            'blockchain': {
                'network': 'sepolia',
                'contract': self.config.contract_address,
                'hash': blockchain_result.get('report_hash'),
                'tx_hash': blockchain_result.get('transaction_hash'),
                'verified': blockchain_result.get('success', False)
            },
            'verify_url': self.get_verification_url(report.report_id)
        }

        return qr_data

    def get_network_info(self) -> Dict[str, Any]:
        """Get blockchain network information."""
        if not self.web3:
            return {'connected': False}

        try:
            return {
                'connected': self.web3.is_connected(),
                'chain_id': self.web3.eth.chain_id,
                'block_number': self.web3.eth.block_number,
                'account': self.account.address if self.account else None,
                'contract_address': self.config.contract_address
            }
        except Exception as e:
            logger.error(f"Failed to get network info: {e}")
            return {'connected': False, 'error': str(e)}