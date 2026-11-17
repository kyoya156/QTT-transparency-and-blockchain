// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @title TransparencyLedger
/// @notice Append-only record of money in, money out and daily batch roots.
/// Only salted hashes are stored. No names, amounts or account numbers ever reach the chain.
/// It proves a record existed unchanged at a block time. It does not prove the record is true:
/// the recorder (the listener service) is trusted to report what the bank feed said.
contract TransparencyLedger is AccessControl, Pausable {
    bytes32 public constant RECORDER_ROLE = keccak256("RECORDER_ROLE");

    enum Direction { None, In, Out }

    struct Entry {
        bytes32 leaf;       // salted hash of the full record, kept off-chain
        uint64 recordedAt;  // block timestamp
        Direction direction;
    }

    struct Batch {
        bytes32 root;
        uint32 count;
        uint64 recordedAt;
    }

    /// refId = keccak/HMAC of the bank's transaction id. Dedupes webhook retries on-chain.
    mapping(bytes32 => Entry) public entries;
    /// day as yyyymmdd, e.g. 20261117
    mapping(uint32 => Batch) public batches;

    event Income(bytes32 indexed refId, bytes32 leaf);
    event Expense(bytes32 indexed refId, bytes32 leaf);
    event BatchAnchored(uint32 indexed day, bytes32 root, uint32 count);

    error AlreadyRecorded(bytes32 refId);
    error DayAlreadyAnchored(uint32 day);
    error EmptyValue();

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
    }

    function recordIncome(bytes32 refId, bytes32 leaf) external onlyRole(RECORDER_ROLE) whenNotPaused {
        _record(refId, leaf, Direction.In);
        emit Income(refId, leaf);
    }

    function recordExpense(bytes32 refId, bytes32 leaf) external onlyRole(RECORDER_ROLE) whenNotPaused {
        _record(refId, leaf, Direction.Out);
        emit Expense(refId, leaf);
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
        return e.direction != Direction.None && e.leaf == leaf;
    }

    /// @notice Stop all recording, for example if the recorder key leaks. Reading still works.
    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) { _pause(); }
    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) { _unpause(); }

    function _record(bytes32 refId, bytes32 leaf, Direction d) private {
        if (refId == bytes32(0) || leaf == bytes32(0)) revert EmptyValue();
        if (entries[refId].direction != Direction.None) revert AlreadyRecorded(refId);
        entries[refId] = Entry(leaf, uint64(block.timestamp), d);
    }
}
