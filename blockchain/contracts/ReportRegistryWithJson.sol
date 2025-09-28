// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title ReportRegistryWithJson
/// @notice Allows storing/anchoring reports in three ways:
/// 1) storeReportHash(bytes32) -> store only a hash (recommended)
/// 2) storeReportJSON(string) -> emit JSON in an event and store hash mapping (event public)
/// 3) storeReportOnChain(string) -> store full JSON in contract storage (expensive & public)
contract ReportRegistryWithJson {
    struct ReportRecord {
        bytes32 reportHash;    // keccak256 or sha256 mapped to bytes32 (we use keccak256; if using sha256, left-pad)
        address submitter;
        uint256 timestamp;
        bool storedOnChain;    // true if JSON is stored in contract storage
        string ipfsCid;        // optional: if the report is stored on IPFS
    }

    // Mapping from hash -> record (primary source for verification)
    mapping(bytes32 => ReportRecord) private reports;

    // If you choose to store JSON on-chain, we keep it here keyed by reportHash.
    mapping(bytes32 => string) private storedJsons;

    // Enumerable list of stored hashes (useful off-chain)
    bytes32[] private reportHashes;

    // Events: cheaper to index and retrieve than storage for many use cases
    event ReportStored(
        bytes32 indexed reportHash,
        address indexed submitter,
        uint256 timestamp,
        bool storedOnChain,
        string ipfsCid
    );

    /// @dev Use with caution: emits the full JSON as an indexed event field is not possible,
    /// so we emit JSON only in a separate event when requested (non-indexed).
    event ReportJsonEmitted(
        bytes32 indexed reportHash,
        address indexed submitter,
        uint256 timestamp,
        string reportJson
    );

    /// @notice Store only the hash on-chain (recommended; cheaper & private)
    /// @param reportHash bytes32 hash of the canonicalized report (keccak256 or sha256 as bytes32)
    function storeReportHash(bytes32 reportHash) external {
        require(reportHash != bytes32(0), "empty hash");
        require(reports[reportHash].timestamp == 0, "already stored");

        // populate mapping
        reports[reportHash] = ReportRecord({
            reportHash: reportHash,
            submitter: msg.sender,
            timestamp: block.timestamp,
            storedOnChain: false,
            ipfsCid: ""
        });

        reportHashes.push(reportHash);

        emit ReportStored(reportHash, msg.sender, block.timestamp, false, "");
    }

    /// @notice Store JSON as an event (JSON appears in logs) and store only the hash in mapping
    /// @dev The event publicizes the JSON (visible to everyone). This is cheaper than storage but still public.
    /// @param reportJson The full JSON string (canonicalize first)
    function storeReportJSON(string calldata reportJson) external {
        require(bytes(reportJson).length > 0, "empty json");

        // compute hash of canonicalized JSON on-chain (we use keccak256)
        bytes32 reportHash = keccak256(bytes(reportJson));

        require(reports[reportHash].timestamp == 0, "already stored");

        reports[reportHash] = ReportRecord({
            reportHash: reportHash,
            submitter: msg.sender,
            timestamp: block.timestamp,
            storedOnChain: false,
            ipfsCid: ""
        });

        reportHashes.push(reportHash);

        // Emit a compact indexed event for quick lookup + a separate event with full JSON (non-indexed).
        emit ReportStored(reportHash, msg.sender, block.timestamp, false, "");
        emit ReportJsonEmitted(reportHash, msg.sender, block.timestamp, reportJson);
    }

    /// @notice Store full JSON in contract storage (VERY expensive & public)
    /// @dev Use only if necessary (small JSON, non-sensitive, and you accept gas cost).
    /// @param reportJson The full JSON string (canonicalize first)
    function storeReportOnChain(string calldata reportJson) external {
        require(bytes(reportJson).length > 0, "empty json");

        bytes32 reportHash = keccak256(bytes(reportJson));
        require(reports[reportHash].timestamp == 0, "already stored");

        // store JSON in mapping
        storedJsons[reportHash] = reportJson;

        reports[reportHash] = ReportRecord({
            reportHash: reportHash,
            submitter: msg.sender,
            timestamp: block.timestamp,
            storedOnChain: true,
            ipfsCid: ""
        });

        reportHashes.push(reportHash);

        emit ReportStored(reportHash, msg.sender, block.timestamp, true, "");
    }

    /// @notice Store an IPFS CID and only the hash (recommended when file size is large)
    /// @param ipfsCid CID string (e.g. "bafy...")
    /// @param reportHash bytes32 hash of the canonicalized content (keccak256 or sha256)
    function storeReportIpfs(string calldata ipfsCid, bytes32 reportHash) external {
        require(bytes(ipfsCid).length > 0, "empty cid");
        require(reportHash != bytes32(0), "empty hash");
        require(reports[reportHash].timestamp == 0, "already stored");

        reports[reportHash] = ReportRecord({
            reportHash: reportHash,
            submitter: msg.sender,
            timestamp: block.timestamp,
            storedOnChain: false,
            ipfsCid: ipfsCid
        });

        reportHashes.push(reportHash);

        emit ReportStored(reportHash, msg.sender, block.timestamp, false, ipfsCid);
    }

    /// @notice Verify if a report exists on-chain and return basic metadata
    /// @param reportHash hash to check
    /// @return exists whether present
    /// @return submitter who submitted
    /// @return timestamp when submitted
    /// @return storedOnChain whether full JSON stored in contract
    /// @return ipfsCid optional ipfs cid
    function verifyReport(bytes32 reportHash)
        external
        view
        returns (
            bool exists,
            address submitter,
            uint256 timestamp,
            bool storedOnChain,
            string memory ipfsCid
        )
    {
        ReportRecord memory r = reports[reportHash];
        if (r.timestamp == 0) {
            return (false, address(0), 0, false, "");
        }
        return (true, r.submitter, r.timestamp, r.storedOnChain, r.ipfsCid);
    }

    /// @notice If JSON was stored on-chain, return it; otherwise returns empty string.
    /// @param reportHash hash key for JSON
    function getStoredJson(bytes32 reportHash) external view returns (string memory) {
        return storedJsons[reportHash];
    }
    
    /// @notice Convenience: get total stored reports
    function getTotalReports() external view returns (uint256) {
        return reportHashes.length;
    }

    /// @notice Get report hash by index
    function getReportHashByIndex(uint256 index) external view returns (bytes32) {
        require(index < reportHashes.length, "index OOB");
        return reportHashes[index];
    }

    /// @notice Get report by its hash
    /// @param reportHash keccak256 hash of the report
    /// @return record ReportRecord associated with the hash
    function getReportByHash(bytes32 reportHash) external view returns (ReportRecord memory record) {
    require(reports[reportHash].timestamp != 0, "report does not exist");
    return reports[reportHash];
}
}
