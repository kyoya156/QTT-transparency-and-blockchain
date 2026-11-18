// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/// @title TransparencyLedger (v2)
/// @notice Append-only record of money in, money out and daily batch roots.
/// v2 publishes the non-sensitive fields in plain text (amount, currency, bank time, donor ID,
/// recipient ID and type) next to the salted hash (`leaf`) of the full record.
/// `donorName` is an optional slot: the listener sends "" until the client decides names may be public.
/// Anything written here is public and permanent. Recipient IDs must be codes, never people's names.
/// It proves a record existed unchanged at a block time. It does not prove the record is true:
/// the recorder (the listener service) is trusted to report what the bank feed said.
contract TransparencyLedger is AccessControl, Pausable {
    bytes32 public constant RECORDER_ROLE = keccak256("RECORDER_ROLE");

    enum Direction { None, In, Out }

    struct Entry {
        bytes32 leaf;       // salted hash of the full record, kept off-chain
        uint128 amount;     // smallest currency unit, e.g. VND
        uint64 txTime;      // bank time of the transaction (unix seconds)
        uint64 recordedAt;  // block timestamp
        Direction direction;
    }

    struct IncomeData {
        uint128 amount;
        uint64 txTime;
        string currency;
        string donorId;
        string donorName;   // "" until names are approved for publication
    }

    struct ExpenseData {
        uint128 amount;
        uint64 txTime;
        string currency;
        string recipientId;
        string recipientType; // e.g. "child", "supplier"; "unassigned" until decided
    }

    struct Batch {
        bytes32 root;
        uint32 count;
        uint64 recordedAt;
    }

    /// refId = HMAC of the bank's transaction id. Dedupes webhook retries on-chain.
    mapping(bytes32 => Entry) public entries;
    /// day as yyyymmdd, e.g. 20261117
    mapping(uint32 => Batch) public batches;

    event Income(bytes32 indexed refId, bytes32 leaf, uint128 amount, string currency, uint64 txTime,
                 string donorId, string donorName);
    event Expense(bytes32 indexed refId, bytes32 leaf, uint128 amount, string currency, uint64 txTime,
                  string recipientId, string recipientType);
    event BatchAnchored(uint32 indexed day, bytes32 root, uint32 count);

    error AlreadyRecorded(bytes32 refId);
    error DayAlreadyAnchored(uint32 day);
    error EmptyValue();

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
    }

    function recordIncome(bytes32 refId, bytes32 leaf, IncomeData calldata d)
        external onlyRole(RECORDER_ROLE) whenNotPaused
    {
        if (bytes(d.donorId).length == 0) revert EmptyValue();
        _record(refId, leaf, d.amount, d.txTime, bytes(d.currency).length, Direction.In);
        emit Income(refId, leaf, d.amount, d.currency, d.txTime, d.donorId, d.donorName);
    }

    function recordExpense(bytes32 refId, bytes32 leaf, ExpenseData calldata d)
        external onlyRole(RECORDER_ROLE) whenNotPaused
    {
        if (bytes(d.recipientId).length == 0) revert EmptyValue();
        _record(refId, leaf, d.amount, d.txTime, bytes(d.currency).length, Direction.Out);
        emit Expense(refId, leaf, d.amount, d.currency, d.txTime, d.recipientId, d.recipientType);
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

    function _record(bytes32 refId, bytes32 leaf, uint128 amount, uint64 txTime, uint256 currencyLen, Direction d)
        private
    {
        if (refId == bytes32(0) || leaf == bytes32(0) || amount == 0 || txTime == 0 || currencyLen == 0) {
            revert EmptyValue();
        }
        if (entries[refId].direction != Direction.None) revert AlreadyRecorded(refId);
        entries[refId] = Entry(leaf, amount, txTime, uint64(block.timestamp), d);
    }
}
