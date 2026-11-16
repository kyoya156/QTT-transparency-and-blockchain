"""Integrity layer for the financial-transparency feature.

Daily batch of ledger records -> salted Merkle root -> anchored in an append-only log.
It proves a record existed unchanged at a point in time. It does not prove the record is true.
"""
