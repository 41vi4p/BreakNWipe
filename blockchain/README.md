# BreakNWipe Blockchain — ReportRegistryWithJson

Hardhat project containing the smart contract that anchors BreakNWipe wipe certificates on the Ethereum blockchain, making them tamper-proof and independently verifiable.

## Contract: `ReportRegistryWithJson`

Deployed on **Sepolia testnet** at [`0x23183BCD67664eD995ec06FF31289A7d3b0897e3`](https://sepolia.etherscan.io/address/0x23183BCD67664eD995ec06FF31289A7d3b0897e3).

Three storage strategies, from cheapest to most expensive:

| Function | Strategy | Cost |
|----------|----------|------|
| `storeReportHash(bytes32)` | Store only the certificate hash | Cheapest |
| `storeReportJSON(string)` | Emit full JSON as an event, store the hash | Moderate |
| `storeReportOnChain(string)` | Store full JSON in contract storage | Most expensive |

Verification / lookup functions:

- `verifyReport(bytes32 reportHash)` — check that a certificate exists and get its record
- `getStoredJson(bytes32 reportHash)` — retrieve on-chain JSON (if stored with `storeReportOnChain`)
- `getTotalReports()` / `getReportHashByIndex(uint256)` / `getReportByHash(bytes32)` — enumeration helpers

> ⚠️ Everything stored on-chain (including event logs) is **public**. BreakNWipe certificates contain device serials and operator names — consider hash-only storage for privacy-sensitive deployments.

## Setup

```bash
pnpm install

# Configure credentials — never commit the real .env!
cp .env.example .env
```

Required environment variables (see `.env.example`):

- `SEPOLIA_RPC_URL` — RPC endpoint (e.g., Infura/Alchemy)
- `PRIVATE_KEY` — deployer wallet private key (needs Sepolia ETH)
- `NEXT_PUBLIC_CONTRACT_ADDRESS` — deployed contract address

## Commands

```bash
# Run tests
npx hardhat test

# Deploy to a local Hardhat node
npx hardhat node          # in one terminal
npx hardhat run scripts/deploy.ts --network localhost

# Deploy to Sepolia
npx hardhat run scripts/deploy.ts --network sepolia
```

After deploying, update the contract address in:

- `blockchain/.env` and `breaknwipe/.env`
- `blockchain_config.json` (repo root)

## Integration

See [docs/BLOCKCHAIN_INTEGRATION.md](../docs/BLOCKCHAIN_INTEGRATION.md) for the full BreakNWipe ↔ blockchain ↔ [datawipe webapp](https://datawipe.vercel.app) verification flow.
