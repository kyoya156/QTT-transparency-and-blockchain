// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @title TransparencyLedger (v3, hash only)
/// @notice Append-only record of salted hashes. Client decision (2026-11-18): nothing readable on chain.
/// Each transaction is stored as `refId -> leaf`, each starting-history day as one Merkle root.
/// refId  = HMAC of the bank's transaction id (hides it, dedupes retries).
/// leaf   = SHA-256 of salt + full record (amount, IDs, names, times, direction). The record and salt stay
///          off chain; who may read them is decided by the app's department permissions.
/// It proves a record existed unchanged at a block time. It does not prove the record is true:
/// the recorder (the listener service) is trusted to report what the bank feed said.
contract TransparencyLedger is AccessControl, Pausable {
    bytes32 public constant RECORDER_ROLE = keccak256("RECORDER_ROLE");

    struct Entry {
        bytes32 leaf;
        uint64 recordedAt;  // block timestamp
    }

    struct Batch {
        bytes32 root;
        uint32 count;
        uint64 recordedAt;
    }

    mapping(bytes32 => Entry) public entries;
    /// day as yyyymmdd, e.g. 20261117
    mapping(uint32 => Batch) public batches;

    event Recorded(bytes32 indexed refId, bytes32 leaf);
    event BatchAnchored(uint32 indexed day, bytes32 root, uint32 count);

    error AlreadyRecorded(bytes32 refId);
    error DayAlreadyAnchored(uint32 day);
    error EmptyValue();

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
    }

    /// @notice Record one transaction's salted hash. A refId can be written once.
    function record(bytes32 refId, bytes32 leaf) external onlyRole(RECORDER_ROLE) whenNotPaused {
        if (refId == bytes32(0) || leaf == bytes32(0)) revert EmptyValue();
        if (entries[refId].recordedAt != 0) revert AlreadyRecorded(refId);
        entries[refId] = Entry(leaf, uint64(block.timestamp));
        emit Recorded(refId, leaf);
    }

    /// @notice Anchor the Merkle root of a whole day, used for the starting history.
    function anchorBatch(uint32 day, bytes32 root, uint32 count) external onlyRole(RECORDER_ROLE) whenNotPaused {
        if (root == bytes32(0) || count == 0) revert EmptyValue();
        if (batches[day].recordedAt != 0) revert DayAlreadyAnchored(day);
        batches[day] = Batch(root, count, uint64(block.timestamp));
        emit BatchAnchored(day, root, count);
    }

    /// @notice True when this exact leaf was recorded under refId.
    function verify(bytes32 refId, bytes32 leaf) external view returns (bool) {
        Entry memory e = entries[refId];
        return e.recordedAt != 0 && e.leaf == leaf;
    }

    /// @notice Stop all recording, for example if the recorder key leaks. Reading still works.
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }
}
