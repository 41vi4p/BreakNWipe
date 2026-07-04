# BreakNWipe Blockchain Integration

This document describes the integration between BreakNWipe, the blockchain smart contract, and the datawipe verification webapp.

## Architecture Overview

The integration consists of three main components:

1. **BreakNWipe** - Core data wiping utility that generates certificates
2. **Blockchain Contract** - Ethereum smart contract deployed on Sepolia testnet
3. **Datawipe Webapp** - Next.js webapp for QR code verification

## Components

### 1. BreakNWipe Core System

**Location**: `breaknwipe/` directory

**Key Files**:
- `breaknwipe/certificate/blockchain.py` - Blockchain integration module
- `breaknwipe/certificate/generator.py` - Enhanced certificate generator
- `breaknwipe/certificate/qr.py` - QR code generation
- `breaknwipe/certificate/report.py` - Report data models

**Features**:
- Automatically stores certificates on blockchain after wipe completion
- Generates blockchain-enhanced QR codes
- Supports both traditional and blockchain verification
- Configurable blockchain integration

### 2. Blockchain Smart Contract

**Location**: `blockchain/` directory

**Contract Details**:
- **Name**: ReportRegistryWithJson
- **Network**: Sepolia Testnet
- **Address**: `0x23183BCD67664eD995ec06FF31289A7d3b0897e3`
- **Functions**:
  - `storeReportOnChain()` - Store certificate data
  - `verifyReport()` - Verify certificate existence
  - `getStoredJson()` - Retrieve stored certificate data

**Key Files**:
- `blockchain/contracts/ReportRegistryWithJson.sol` - Smart contract source
- `blockchain/.env` - Configuration file
- `blockchain/scripts/deploy.ts` - Deployment script

### 3. Datawipe Verification Webapp

**Location**: separate repository — live at [datawipe.vercel.app](https://datawipe.vercel.app)

**Features**:
- QR code scanning using device camera
- Supports both encrypted and JSON QR formats
- Blockchain verification integration
- Automatic certificate upload to blockchain
- Mobile-friendly responsive design

**Key Files**:
- `datawipe/src/app/page.tsx` - Main QR scanner page
- `datawipe/src/app/report/page.tsx` - Certificate display page
- `datawipe/src/actions/BlockReport.ts` - Blockchain interaction
- `datawipe/src/actions/ProcessQRResult.ts` - QR processing logic

## Setup Instructions

### Prerequisites

1. **Python 3.8+** with pip
2. **Node.js 18+** with npm/pnpm
3. **Ethereum wallet** with Sepolia testnet ETH

### 1. Install BreakNWipe Dependencies

```bash
# Install blockchain dependencies
pip install web3 eth-account requests

# Or install BreakNWipe with blockchain support
pip install -e ".[blockchain]"
```

### 2. Configure Environment Variables

**For BreakNWipe** (create `breaknwipe/.env`):
```env
# Blockchain Configuration
BREAKNWIPE_RPC_URL=https://sepolia.infura.io/v3/YOUR_PROJECT_ID
BREAKNWIPE_CONTRACT_ADDRESS=0x23183BCD67664eD995ec06FF31289A7d3b0897e3
BREAKNWIPE_PRIVATE_KEY=0xYOUR_PRIVATE_KEY
BREAKNWIPE_CHAIN_ID=11155111

# Datawipe Integration
DATAWIPE_BASE_URL=https://datawipe.vercel.app

# Features
BREAKNWIPE_AUTO_BLOCKCHAIN_STORE=true
BREAKNWIPE_QR_INCLUDE_BLOCKCHAIN=true
```

**For Blockchain Project** (already configured in `blockchain/.env`):
```env
NEXT_PUBLIC_RPC_URL=https://sepolia.infura.io/v3/YOUR_PROJECT_ID
NEXT_PUBLIC_CONTRACT_ADDRESS=0x23183BCD67664eD995ec06FF31289A7d3b0897e3
PRIVATE_KEY=0xYOUR_PRIVATE_KEY
NEXT_PUBLIC_CHAIN_ID=11155111
```

**For Datawipe Webapp** (copy from blockchain/.env or set as environment variables):
```env
NEXT_PUBLIC_RPC_URL=https://sepolia.infura.io/v3/YOUR_PROJECT_ID
NEXT_PUBLIC_CONTRACT_ADDRESS=0x23183BCD67664eD995ec06FF31289A7d3b0897e3
RPC_URL=https://sepolia.infura.io/v3/YOUR_PROJECT_ID
PRIVATE_KEY=0xYOUR_PRIVATE_KEY
```

### 3. Deploy and Test

```bash
# 1. Run the setup script
python scripts/setup_blockchain_integration.py

# 2. Test the integration
python tests/test_blockchain_functionality.py

# 3. Start the datawipe webapp
cd datawipe
npm install
npm run dev
```

## Usage Workflow

### 1. Data Wiping with Blockchain Storage

```python
from breaknwipe.certificate.generator import CertificateGenerator
from breaknwipe.certificate.report import WipeReport

# Create certificate generator with blockchain enabled
generator = CertificateGenerator(enable_blockchain=True)

# Generate certificate (automatically stores on blockchain)
files = generator.generate_certificate(
    report=your_wipe_report,
    include_qr=True,
    store_on_blockchain=True
)

# Files will include blockchain transaction details
print(files['blockchain_result'])
```

### 2. QR Code Structure

**Traditional QR Code**:
```json
{
  "type": "breaknwipe_certificate",
  "version": "1.0",
  "report_id": "uuid",
  "device_serial": "SERIAL123",
  "success": true,
  "algorithm": "nist-clear",
  "timestamp": 1234567890,
  "hash": "certificate_hash",
  "verify_url": "https://verify.breaknwipe.org/uuid"
}
```

**Blockchain-Enhanced QR Code**:
```json
{
  "type": "breaknwipe_blockchain_certificate",
  "version": "2.0",
  "report_id": "uuid",
  "device_serial": "SERIAL123",
  "success": true,
  "algorithm": "nist-clear",
  "timestamp": 1234567890,
  "operator": "John Doe",
  "blockchain": {
    "network": "sepolia",
    "contract": "0x23183BCD67664eD995ec06FF31289A7d3b0897e3",
    "hash": "0xreport_hash",
    "tx_hash": "0xtransaction_hash",
    "verified": true
  },
  "verify_url": "https://datawipe.vercel.app?hash=0xreport_hash"
}
```

### 3. Verification Process

1. **QR Code Scanning**: User scans QR code with datawipe webapp
2. **Data Processing**: App extracts certificate data and blockchain hash
3. **Blockchain Verification**: App queries smart contract to verify certificate
4. **Display Results**: Shows verification status and certificate details

## Configuration Options

### BreakNWipe Configuration

- `BREAKNWIPE_AUTO_BLOCKCHAIN_STORE`: Automatically store certificates on blockchain (default: true)
- `BREAKNWIPE_QR_INCLUDE_BLOCKCHAIN`: Include blockchain data in QR codes (default: true)
- `BREAKNWIPE_STORAGE_METHOD`: Storage method - "hash", "json", or "onchain" (default: "onchain")

### Blockchain Configuration

- **Gas Limit**: 500,000 (configurable)
- **Gas Price**: 20 gwei (configurable)
- **Network**: Sepolia testnet (configurable)

## Troubleshooting

### Common Issues

1. **"Blockchain not configured"**
   - Check environment variables
   - Ensure private key and RPC URL are set
   - Verify contract address

2. **"Transaction failed"**
   - Check account has sufficient ETH for gas
   - Verify network connection
   - Check contract is deployed and accessible

3. **"QR code not recognized"**
   - Ensure QR contains valid JSON
   - Check QR code format version
   - Verify camera permissions in browser

### Testing

```bash
# Test blockchain connection
python -c "
from breaknwipe.certificate.blockchain import BlockchainCertificateStore
store = BlockchainCertificateStore()
print(store.get_network_info())
"

# Test certificate generation
python tests/test_blockchain_functionality.py
```

## Security Considerations

1. **Private Key Security**: Store private keys securely, never commit to git
2. **Gas Costs**: Monitor gas prices and set reasonable limits
3. **Network Reliability**: Implement fallbacks for network issues
4. **Data Privacy**: Consider what data is stored on-chain (public)

## Development

### Adding New Features

1. **Extend Blockchain Module**: Add new functions to `blockchain.py`
2. **Update QR Format**: Modify QR data structure in `generator.py`
3. **Enhance Webapp**: Add new verification features in datawipe components

### Testing

```bash
# Unit tests
pytest breaknwipe/tests/

# Integration tests
python tests/test_blockchain_functionality.py

# E2E tests
cd datawipe && npm test
```

## Support

For issues and support:
- BreakNWipe: Check project documentation
- Blockchain: Review Sepolia testnet status
- Datawipe: Check webapp logs and browser console

## License

This integration maintains the same license as the individual components.