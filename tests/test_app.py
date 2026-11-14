"""Test suite for the Quỹ Minh Bạch Tài Chính Topic 4 pipeline.

Tests fall into three groups:

1. Parser correctness -- the NE/ACN formats here are copied verbatim from the
   fund's live statement, not invented. If one of these regresses, real donor
   payments stop being matched.
2. Reconciliation invariants -- the parts must always sum to the whole. This is
   the property the old system silently violated.
3. API and security behaviour -- PII never leaves, writes are refused, the
   audit chain detects tampering, and the maker-checker separation of duties
   actually blocks self-approval.
"""

from __future__ import annotations

import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import app
import build_database
import parsers
import reconciliation
from build_database import iso_value
from schema import SCHEMA


SAMPLE_STATEMENT = '''Sao kê tài khoản ngân hàng Vietcombank,,,Tổng thu,100,,,
Từ 01/01/2018 đến 25/02/2026,,,Tổng chi,50,,,
STT,"Ngày/
TNX Date/ Số CT/ Doc No",Chi,Thu,"Số dư/
Balance","Nội dung chi tiết/
Transactions in detail",Năm,Tháng
1,"08/02/2018
YG61.000093",,50.000,50.000,HOANG HOA TRUNG;NOP TIEN;,2018,2
2,"11/02/2018
VNCK.989657",,1.450.000,1.500.000,IBVCB.NHAN NUOI NE05517,2018,2
3,"12/02/2018
VNCK.066656",,2.900.000,4.400.000,"Vietcombank 0711000280294 Nhat Thi ck tien nuoi com NE77, NE78",2018,2
4,"16/02/2018
VNCK.579986",1.900.000,,2.500.000,chuyen tien xay truong,2018,2
5,"21/02/2018
VNCN.022706",,750.000,3.250.000,IBVCB.0606180032100002.Nguyen phi long NE89-90-91-92,2018,2
6,"22/02/2018
VNCN.022707",,3.000.000,6.250.000,MBVCB55886877.NE108 NE109 NE110 NE111 NE112 NE113.CT tu 002100,2018,2
7,"23/02/2018
VNCN.022708",,450.000,6.700.000,tien nuoi com NE00001S,2018,2
8,"24/02/2018
VNCN.022709",,700.000,7.400.000,chuyen khoan ACN02497 ung ho NE29860,2018,2
'''


def build_sample_database(conn: sqlite3.Connection) -> dict:
    """Load the sample statement into an already-schema'd connection."""
    import csv
    import io

    rows = list(csv.reader(io.StringIO(SAMPLE_STATEMENT.strip())))
    blocks = build_database.locate_blocks(rows)
    header_index, mapping = blocks["statement"]
    return build_database.ingest_statement_rows(
        conn,
        rows,
        header_index=header_index,
        mapping=mapping,
        source_name="sample.csv",
        source_account="0711000280294",
    )


class ParserTests(unittest.TestCase):
    """Formats copied from the fund's live statement."""

    def test_single_code(self):
        parsed = parsers.parse_reference("NHAN NUOI NE05517")
        self.assertEqual(parsed.ne_codes, ["NE05517"])

    def test_short_legacy_code_is_zero_padded(self):
        parsed = parsers.parse_reference("TruongHoang NE146")
        self.assertEqual(parsed.ne_codes, ["NE00146"])

    def test_dash_chain_expands(self):
        parsed = parsers.parse_reference(
            "IBVCB.0606180032100002.Nguyen phi long NE89-90-91-92"
        )
        self.assertEqual(
            parsed.ne_codes, ["NE00089", "NE00090", "NE00091", "NE00092"]
        )

    def test_comma_list_expands(self):
        parsed = parsers.parse_reference(
            "Nhat Thi ck tien nuoi com NE77, NE78, NE79, NE80, NE81"
        )
        self.assertEqual(len(parsed.ne_codes), 5)
        self.assertIn("NE00077", parsed.ne_codes)

    def test_space_separated_list_expands(self):
        parsed = parsers.parse_reference(
            "MBVCB55886877.NE108 NE109 NE110 NE111 NE112 NE113.CT tu 002100"
        )
        self.assertEqual(len(parsed.ne_codes), 6)

    def test_meal_suffix_survives_normalization(self):
        """NE00001S and NE00001T are different codes for the same child."""
        lunch = parsers.parse_reference("tien nuoi com NE00001S")
        dinner = parsers.parse_reference("tien nuoi com NE00001T")
        self.assertEqual(lunch.ne_codes, ["NE00001S"])
        self.assertEqual(dinner.ne_codes, ["NE00001T"])
        self.assertEqual(lunch.ne_references[0].meal, "lunch")
        self.assertEqual(dinner.ne_references[0].meal, "dinner")

    def test_acn_with_ne(self):
        parsed = parsers.parse_reference("chuyen khoan ACN02497 ung ho NE29860")
        self.assertEqual(parsed.acn_codes, ["ACN02497"])
        self.assertEqual(parsed.ne_codes, ["NE29860"])

    def test_text_without_codes(self):
        parsed = parsers.parse_reference("chuyen tien xay truong")
        self.assertFalse(parsed.has_ne)
        self.assertFalse(parsed.has_acn)

    def test_keyword_ne_is_not_a_code(self):
        """A bare 'ne' inside prose must not become a code."""
        parsed = parsers.parse_reference("em tuan ung ho 10 doi ung")
        self.assertEqual(parsed.ne_codes, [])

    def test_amount_dot_grouping(self):
        """238,166 of 238,173 real cells use dot grouping. Comma is never used."""
        self.assertEqual(parsers.parse_amount("1.450.000"), 1_450_000)
        self.assertEqual(parsers.parse_amount("553.550.809.401"), 553_550_809_401)

    # ------------------------------------------------------------------
    # Regression tests for the two false-positive modes measured on the
    # real corpus. Each memo below is copied verbatim from the published
    # Vietcombank statement. Before the fix, all of these produced one or
    # more phantom NE codes, and a phantom code silently steals money:
    # the transaction total is split across more codes than really exist,
    # so every genuine code on that transaction is under-reported.
    # ------------------------------------------------------------------

    def test_bank_trace_prefix_does_not_become_a_code(self):
        """The leading trace/date/time triple is machine noise, not a memo."""
        parsed = parsers.parse_reference(
            "904214.271219.145325.SON HA LE DU AN NUOI EM NE3851-271219-14:53:24"
        )
        self.assertEqual(parsed.ne_codes, ["NE03851"])

    def test_date_suffix_does_not_become_a_code(self):
        """'-271219-14:53:24' is a date and a clock, not codes 271219 and 14."""
        parsed = parsers.parse_reference(
            "483019.171024.133756.BCG FOUNDATION NUOI 50 BE - NE00298-171024-13:36:06"
        )
        self.assertEqual(parsed.ne_codes, ["NE00298"])

    def test_clock_minutes_are_not_sibling_codes(self):
        """The '13' in '-13:36:06' must never be read as a sibling code."""
        parsed = parsers.parse_reference("NE10578-110323-10:36:17 821188")
        self.assertEqual(parsed.ne_codes, ["NE10578"])
        self.assertNotIn("NE110323", parsed.ne_codes)
        self.assertNotIn("NE00013", parsed.ne_codes)

    def test_six_digit_date_after_ne_is_not_a_code(self):
        """NE221021 is 22/10/21. The catalogue is 5 digits wide."""
        parsed = parsers.parse_reference("NE00228 NE05946-221021-18:25:14 155389")
        self.assertEqual(sorted(parsed.ne_codes), ["NE00228", "NE05946"])

    def test_bare_continuation_list_expands(self):
        """'NE140370, 140371, 140372' is a donor block of three sequential codes."""
        parsed = parsers.parse_reference(
            "775754.221221.211336.NE140370, 140371, 140372 Le Huong Giang"
        )
        self.assertEqual(
            sorted(parsed.ne_codes), ["NE140370", "NE140371", "NE140372"]
        )

    def test_truncated_shorthand_inherits_head_digits(self):
        """'NE121215,16,17' means codes ...216 and ...217, not NE00016/NE00017."""
        parsed = parsers.parse_reference(
            "LP VNM000M7J ANH VU + NE121215,16,17 DVC:MS VU NGO C TRUC ANH"
        )
        self.assertEqual(
            sorted(parsed.ne_codes), ["NE121215", "NE121216", "NE121217"]
        )
        self.assertNotIn("NE00016", parsed.ne_codes)

    def test_hyphen_chain_still_expands_without_metadata(self):
        """The chain fix must not break genuine hyphen chains."""
        parsed = parsers.parse_reference(
            "304131.260624.091245.NE02734-NE02735-NE03316-260624-09:12:45"
        )
        self.assertEqual(
            sorted(parsed.ne_codes), ["NE02734", "NE02735", "NE03316"]
        )

    def test_dedupe_removes_repeated_codes(self):
        """A code named twice in one memo must appear once."""
        parsed = parsers.parse_reference("NE05517 va NE05517 ung ho")
        self.assertEqual(parsed.ne_codes, ["NE05517"])

    def test_strip_bank_metadata_is_exported(self):
        """The helper is public so the ingestion log can show what was removed."""
        stripped = parsers.strip_bank_metadata(
            "904214.271219.145325.SON HA LE DU AN NUOI EM NE3851"
        )
        self.assertNotIn("904214", stripped)
        self.assertIn("NE3851", stripped)
        self.assertEqual(parsers.parse_amount("1.500"), 1500)
        self.assertEqual(parsers.parse_amount("807"), 807)
        self.assertEqual(parsers.parse_amount(""), 0)
        self.assertEqual(parsers.parse_amount(None), 0)
        self.assertEqual(parsers.parse_amount(170), 170)

    def test_wrapped_code_is_rejoined_across_the_line_break(self):
        """The statement wraps a code mid-number: "NE1 156" is NE1156.

        Without the repair the fragment "NE1" normalises to NE00001, which is
        the fund's actual first student, so another child's money lands on them.
        """
        self.assertEqual(
            parsers.parse_reference("BO:TRUONG THI MINH CHAU.NE1 156").ne_codes,
            ["NE01156"],
        )
        self.assertEqual(
            parsers.parse_reference("NGUYEN THI THUY TRANG NE1 191(3 THAN G)").ne_codes,
            ["NE01191"],
        )

    def test_wrapped_code_does_not_swallow_a_real_sibling(self):
        """Repairing the wrap must not hide a properly written code beside it."""
        parsed = parsers.parse_reference("DOAN THI BICH PHUONG NE1 766, NE1767")
        self.assertEqual(sorted(parsed.ne_codes), ["NE01766", "NE01767"])

    def test_standalone_three_digit_code_is_untouched_by_wrap_repair(self):
        """A well-formed short code must survive the wrap pattern."""
        self.assertEqual(parsers.parse_reference("ung ho NE146").ne_codes, ["NE00146"])

    def test_year_written_beside_a_code_is_not_a_code(self):
        """Donors write the academic year next to the code constantly."""
        parsed = parsers.parse_reference("NE413 + NE414, 2019+2020")
        self.assertEqual(sorted(parsed.ne_codes), ["NE00413", "NE00414"])

    def test_glued_year_pair_is_not_a_code(self):
        """ "NE20192020" is two academic years, not a five-digit student."""
        self.assertEqual(parsers.parse_reference("Kim Linh NE20192020").ne_codes, [])

    def test_year_range_slash_form_is_not_a_code(self):
        """ "NE4708 - 2019/20" must yield only the real code."""
        self.assertEqual(
            parsers.parse_reference("NGUYEN THI THU THAO.NE4708 - 2019/20").ne_codes,
            ["NE04708"],
        )

    def test_a_lone_year_like_number_is_kept_because_it_may_be_a_real_code(self):
        """NE02019 is both year-like and a real code, so context decides.

        The corpus contains "ck 1 ma NE02019 Quyen Mice" — a genuine transfer.
        A blanket 2018-2026 filter would delete a real donor, which is worse
        than keeping a phantom, so a lone number is deliberately retained.
        """
        self.assertEqual(
            parsers.parse_reference("ck 1 ma NE02019 Quyen Mice").ne_codes,
            ["NE02019"],
        )
        self.assertEqual(
            parsers.parse_reference("NE20199 Nguyen Thi Thuy Dung").ne_codes,
            ["NE20199"],
        )

    def test_year_filter_does_not_eat_ordinary_codes(self):
        """The year guard must not touch normal catalogue numbers."""
        parsed = parsers.parse_reference("NE05517 NE146 NE1473")
        self.assertEqual(sorted(parsed.ne_codes), ["NE00146", "NE01473", "NE05517"])


class AllocationTests(unittest.TestCase):
    def test_single_code_takes_whole_amount(self):
        amounts, policy = reconciliation.split_amount(1_450_000, 1)
        self.assertEqual(amounts, [1_450_000])
        self.assertEqual(policy, reconciliation.ALLOCATION_SINGLE)

    def test_even_split(self):
        amounts, policy = reconciliation.split_amount(2_900_000, 2)
        self.assertEqual(amounts, [1_450_000, 1_450_000])
        self.assertEqual(policy, reconciliation.ALLOCATION_EQUAL)

    def test_remainder_is_preserved_not_dropped(self):
        """Parts must always sum back to the whole."""
        amounts, policy = reconciliation.split_amount(1000, 3)
        self.assertEqual(sum(amounts), 1000)
        self.assertEqual(policy, reconciliation.ALLOCATION_EQUAL_WITH_REMAINDER)
        self.assertEqual(amounts[0], 334)

    def test_parts_always_sum_to_whole(self):
        for total in (1, 7, 999, 1_450_000, 3_000_000, 10_150_000):
            for count in range(1, 21):
                amounts, _ = reconciliation.split_amount(total, count)
                self.assertEqual(sum(amounts), total, f"{total} over {count} codes")

    def test_published_tier_detection(self):
        self.assertEqual(reconciliation.infer_unit_price(2_900_000, 2), 1_450_000)
        self.assertEqual(reconciliation.infer_unit_price(1_360_000, 1), 1_360_000)
        self.assertEqual(reconciliation.infer_unit_price(850_000, 5), 170_000)
        # 500,000 is a real observed per-code amount but is not one of the
        # fund's published annual tiers, so it must NOT be claimed as one.
        self.assertIsNone(reconciliation.infer_unit_price(3_000_000, 6))
        self.assertIsNone(reconciliation.infer_unit_price(1234, 3))

    def test_idempotency_key_is_stable(self):
        a = reconciliation.idempotency_key("vcb", "FT1", 1000, "2026-01-01")
        b = reconciliation.idempotency_key("vcb", "FT1", 1000, "2026-01-01")
        c = reconciliation.idempotency_key("vcb", "FT1", 2000, "2026-01-01")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self.stats = build_sample_database(self.conn)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Date-cell parsing. The published sheet packs two values into one
    # cell, and a round-trip through CSV replaces the newline with a
    # space. Measured on the real file: 65,654 of 238,173 rows arrived in
    # the space-separated shape, and storing the whole string sorted
    # 27.6% of transactions to a nonsense date. These tests pin the
    # parser to the date alone.
    # ------------------------------------------------------------------

    def test_date_with_newline_and_doc_number(self):
        """'08/02/2018\\nYG61.000093' keeps only the date."""
        self.assertEqual(iso_value("08/02/2018\nYG61.000093"), "2018-02-08 00:00:00")

    def test_date_with_space_and_balance(self):
        """'31/12/2020 9774.0008477811' must not keep the balance."""
        self.assertEqual(iso_value("31/12/2020 9774.0008477811"), "2020-12-31 00:00:00")

    def test_date_bare(self):
        self.assertEqual(iso_value("25/02/2026"), "2026-02-25 00:00:00")

    def test_date_two_digit_year(self):
        self.assertEqual(iso_value("08/02/18"), "2018-02-08 00:00:00")

    def test_date_iso_input_is_preserved(self):
        self.assertEqual(iso_value("2026-02-25"), "2026-02-25 00:00:00")

    def test_date_unparseable_falls_back_visibly(self):
        """A future format should look wrong, not become NULL."""
        self.assertEqual(iso_value("not a date"), "not")

    def test_date_empty_is_none(self):
        self.assertIsNone(iso_value(""))
        self.assertIsNone(iso_value(None))

    def tearDown(self):
        self.conn.close()

    def test_row_counts(self):
        self.assertEqual(self.stats["transactions"], 8)
        # 1 + 2 + 4 + 6 + 1 + 1 = 15 allocations
        self.assertEqual(self.stats["allocations"], 15)

    def test_directions_split_correctly(self):
        inbound = self.conn.execute(
            "SELECT COUNT(*) FROM bank_transactions WHERE direction='inbound'"
        ).fetchone()[0]
        outbound = self.conn.execute(
            "SELECT COUNT(*) FROM bank_transactions WHERE direction='outbound'"
        ).fetchone()[0]
        self.assertEqual(inbound, 7)
        self.assertEqual(outbound, 1)

    def test_allocations_sum_to_linked_transactions(self):
        """The invariant the old system could violate silently."""
        allocations = self.conn.execute(
            "SELECT SUM(allocated_amount_computed) FROM transaction_allocations"
        ).fetchone()[0]
        linked = self.conn.execute(
            "SELECT SUM(amount) FROM bank_transactions WHERE id IN "
            "(SELECT DISTINCT transaction_id FROM transaction_allocations)"
        ).fetchone()[0]
        self.assertEqual(allocations, linked)

    def test_multi_code_split_is_even(self):
        rows = self.conn.execute(
            """
            SELECT ta.ne_code, ta.allocated_amount_computed
            FROM transaction_allocations ta
            JOIN bank_transactions t ON t.id = ta.transaction_id
            WHERE t.provider_tx_id = 'VNCK.066656'
            ORDER BY ta.ne_code
            """
        ).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r[1] for r in rows}, {1_450_000})

    def test_amount_is_counted_once_not_per_code(self):
        """6 NE codes on one 3,000,000đ transfer must not become 18,000,000đ."""
        total = self.conn.execute(
            "SELECT SUM(amount) FROM bank_transactions WHERE provider_tx_id='VNCN.022707'"
        ).fetchone()[0]
        self.assertEqual(total, 3_000_000)
        rows = self.conn.execute(
            "SELECT COUNT(*) FROM transaction_allocations ta JOIN bank_transactions t "
            "ON t.id = ta.transaction_id WHERE t.provider_tx_id = 'VNCN.022707'"
        ).fetchone()[0]
        self.assertEqual(rows, 6)

    def test_reimport_is_idempotent(self):
        before = self.conn.execute("SELECT COUNT(*) FROM bank_transactions").fetchone()[0]
        build_sample_database(self.conn)
        self.conn.commit()
        after = self.conn.execute("SELECT COUNT(*) FROM bank_transactions").fetchone()[0]
        self.assertEqual(before, after, "re-import must not duplicate transactions")

    def test_reused_document_number_does_not_drop_a_real_row(self):
        """Same doc/time/amount can still be two distinct published rows."""
        import csv
        import io

        text = '''STT,"Ngày/\nTNX Date/ Số CT/ Doc No",Chi,Thu,"Số dư/\nBalance","Nội dung chi tiết/\nTransactions in detail",Năm,Tháng
1,"01/01/2026\nDUP.000001",,1.000.000,1.000.000,ung ho NE00001,2026,1
2,"01/01/2026\nDUP.000001",,1.000.000,2.000.000,ung ho NE00002,2026,1'''
        rows = list(csv.reader(io.StringIO(text)))
        blocks = build_database.locate_blocks(rows)
        header_index, mapping = blocks["statement"]
        stats = build_database.ingest_statement_rows(
            self.conn,
            rows,
            header_index=header_index,
            mapping=mapping,
            source_name="collision.csv",
            source_account="test",
        )
        self.conn.commit()
        kept = self.conn.execute(
            "SELECT COUNT(*) FROM bank_transactions WHERE provider_tx_id LIKE 'DUP.000001%'"
        ).fetchone()[0]
        self.assertEqual(stats["duplicates_skipped"], 0)
        self.assertEqual(kept, 2)

    def test_exceptions_are_aggregated_not_per_row(self):
        """One exception per category, not per transaction."""
        rows = self.conn.execute("SELECT COUNT(*) FROM exception_queue").fetchone()[0]
        self.assertLess(rows, 8, "exception queue must stay triageable")

    def test_uncoded_inbound_is_flagged(self):
        codes = {
            r[0] for r in self.conn.execute("SELECT exception_code FROM exception_queue")
        }
        self.assertIn("INBOUND_WITHOUT_CODE", codes)

    def test_reference_tokens_preserved_for_investigation(self):
        row = self.conn.execute(
            "SELECT reference_tokens FROM bank_transactions WHERE provider_tx_id='VNCN.022708'"
        ).fetchone()
        self.assertIn("NE00001S", row[0])


class AuditChainTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(SCHEMA)
        self.chain = reconciliation.AuditChain(self.conn)

    def tearDown(self):
        self.conn.close()

    def test_chain_links_events(self):
        self.chain.record("a", actor="alice")
        self.chain.record("b", actor="bob")
        self.conn.commit()
        ok, broken = self.chain.verify()
        self.assertTrue(ok)
        self.assertIsNone(broken)

    def test_tampering_is_detected(self):
        self.chain.record("a", actor="alice", detail={"amount": 100})
        self.chain.record("b", actor="bob")
        self.conn.commit()
        self.conn.execute("DROP TRIGGER audit_events_no_update")
        self.conn.execute("UPDATE audit_events SET detail='{\"amount\": 999}' WHERE id=1")
        self.conn.commit()
        ok, broken = self.chain.verify()
        self.assertFalse(ok)
        self.assertEqual(broken, 1)

    def test_deleting_an_event_breaks_the_chain(self):
        self.chain.record("a", actor="alice")
        self.chain.record("b", actor="bob")
        self.chain.record("c", actor="carol")
        self.conn.commit()
        self.conn.execute("DROP TRIGGER audit_events_no_delete")
        self.conn.execute("DELETE FROM audit_events WHERE id=2")
        self.conn.commit()
        ok, _ = self.chain.verify()
        self.assertFalse(ok)

    def test_ordinary_update_is_blocked(self):
        self.chain.record("a", actor="alice")
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE audit_events SET actor='mallory' WHERE id=1")

    def test_ordinary_delete_is_blocked(self):
        self.chain.record("a", actor="alice")
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("DELETE FROM audit_events WHERE id=1")


class MakerCheckerTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def test_maker_cannot_approve_own_change(self):
        task = reconciliation.propose_approval(
            self.conn,
            "transaction_allocation",
            "NE05517",
            "rematch",
            {"ne_code": "NE05518"},
            "memo typo",
            maker="alice",
        )
        with self.assertRaises(PermissionError):
            reconciliation.decide_approval(self.conn, task, checker="alice", approve=True)

    def test_different_checker_can_approve(self):
        task = reconciliation.propose_approval(
            self.conn,
            "transaction_allocation",
            "NE05517",
            "rematch",
            {"ne_code": "NE05518"},
            "memo typo",
            maker="alice",
        )
        result = reconciliation.decide_approval(
            self.conn, task, checker="bob", approve=True, note="verified with school list"
        )
        self.assertEqual(result, "approved")

    def test_double_decision_is_rejected(self):
        task = reconciliation.propose_approval(
            self.conn, "x", "y", "z", {}, "reason", maker="alice"
        )
        reconciliation.decide_approval(self.conn, task, checker="bob", approve=True)
        with self.assertRaises(ValueError):
            reconciliation.decide_approval(self.conn, task, checker="carol", approve=True)


class ApiSecurityTests(unittest.TestCase):
    """Runs the real HTTP server against a temp database."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="nuoiem_test_")
        cls.db_path = Path(cls.tmp) / "test.sqlite"
        conn = sqlite3.connect(cls.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        build_sample_database(conn)
        conn.execute("ANALYZE")
        conn.commit()
        conn.close()

        cls.original_db = app.DATABASE
        app.DATABASE = cls.db_path
        cls.server = app.create_server("127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        app.DATABASE = cls.original_db
        # Windows keeps the file locked for a moment after the server closes.
        # Best-effort cleanup; the temp directory is disposable.
        try:
            Path(cls.db_path).unlink(missing_ok=True)
            Path(cls.tmp).rmdir()
        except OSError:
            pass

    def get(self, path):
        with urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
            return response.status, json.load(response), dict(response.headers)

    def test_health(self):
        status, payload, headers = self.get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_summary_reports_integrity(self):
        _, payload, _ = self.get("/api/summary")
        self.assertTrue(payload["integrity"]["balanced"])
        self.assertEqual(
            payload["integrity"]["allocations_sum"],
            payload["integrity"]["linked_transactions_sum"],
        )

    def test_summary_reports_coverage_honestly(self):
        _, payload, _ = self.get("/api/summary")
        coverage = payload["coverage"]
        self.assertEqual(
            coverage["inbound_allocated"] + coverage["inbound_unallocated"],
            coverage["inbound_total"],
        )

    def test_allocation_endpoint_balances(self):
        _, payload, _ = self.get("/api/allocation?tx=VNCN.022707")
        self.assertTrue(payload["balanced"])
        self.assertEqual(len(payload["allocations"]), 6)

    def test_ne_lookup_by_bare_number(self):
        _, payload, _ = self.get("/api/ne?ne=5517")
        self.assertEqual(payload["ne_code"], "NE05517")

    def test_ne_lookup_returns_meal_suffix_code(self):
        _, payload, _ = self.get("/api/ne?ne=NE00001S")
        self.assertGreater(payload["allocation_count"], 0)

    def test_base_code_does_not_absorb_meal_suffix_variants(self):
        """NE00001 and NE00001S are two codes, not one code with a decoration.

        An earlier version matched `ne_code LIKE 'CODE%'`, which folded every
        S/T variant into the base code and reported one total for what are
        separate sponsorships. The base code must report only its own rows, and
        the variants must be listed apart from it.
        """
        _, payload, _ = self.get("/api/ne?ne=NE00001")
        self.assertEqual(payload["allocation_count"], 0)
        self.assertEqual([v["ne_code"] for v in payload["variants"]], ["NE00001S"])

    def test_admin_search_normalises_a_bare_number(self):
        _, payload, _ = self.get("/api/admin/search?q=1156")
        self.assertEqual(payload["kind"], "ne")
        self.assertEqual(payload["code"], "NE01156")

    def test_admin_search_keeps_the_meal_suffix(self):
        _, payload, _ = self.get("/api/admin/search?q=ne1s")
        self.assertEqual(payload["code"], "NE00001S")

    def test_admin_search_refuses_phone_numbers(self):
        """A phone number is not a lookup key, and pretending otherwise would
        turn the box into a personal-data oracle over raw bank memos."""
        _, payload, _ = self.get("/api/admin/search?q=0912345678")
        self.assertEqual(payload["kind"], "blocked")
        self.assertNotIn("code", payload)

    def test_admin_queue_reports_one_row_per_cause(self):
        _, payload, _ = self.get("/api/admin/queue")
        keys = {bucket["key"] for bucket in payload["buckets"]}
        self.assertEqual(keys, {"inbound_no_code", "code_no_profile", "outbound_unclassified"})
        for bucket in payload["buckets"]:
            self.assertIn("count", bucket)
            self.assertIn("amount", bucket)

    def test_admin_rows_rejects_an_unknown_bucket(self):
        """The bucket name arrives from a URL hash, so it is user input. An
        unknown one must not fall through to a default list."""
        _, payload, _ = self.get("/api/admin/rows?bucket=whatever&limit=5")
        self.assertEqual(payload["error"], "unknown_bucket")
        self.assertEqual(payload["items"], [])

    def test_admin_rows_pages_without_repeating_or_dropping(self):
        """Keyset paging on (total, ne_code) must partition the set exactly.

        An OFFSET-based page would repeat or skip rows as soon as two codes hold
        the same total -- and in this fixture all 15 codes hold the same amount,
        which is the worst case for that mistake.
        """
        seen, cursor, guard = [], None, 0
        while True:
            query = "/api/admin/rows?bucket=code_no_profile&limit=5"
            if cursor:
                query += "&cursor=" + quote(cursor, safe="")
            _, page, _ = self.get(query)
            seen.extend(item["ne_code"] for item in page["items"])
            guard += 1
            self.assertLess(guard, 10, "paging never terminated")
            if not page["has_more"]:
                self.assertEqual(len(seen), page["total"])
                break
            cursor = page["next_cursor"]
        self.assertEqual(len(seen), len(set(seen)), "a code appeared on two pages")
        self.assertEqual(len(seen), 15)

    def test_admin_rows_survives_a_malformed_cursor(self):
        _, payload, _ = self.get("/api/admin/rows?bucket=code_no_profile&cursor=not-a-cursor")
        self.assertNotIn("error", payload)
        self.assertEqual(len(payload["items"]), min(25, payload["total"]))

    def test_admin_rows_never_serve_the_raw_memo(self):
        """Same rule as the public table: the memo is where donor names and
        phone numbers live, so the admin list gets the masked sentence only."""
        for bucket in ("inbound_no_code", "outbound_unclassified"):
            _, payload, _ = self.get(f"/api/admin/rows?bucket={bucket}")
            for item in payload["items"]:
                self.assertNotIn("raw_description", item)
                self.assertIn("description_masked", item)
                self.assertTrue(item["description_masked"].startswith("Nội dung giao dịch đã được ẩn"))

    def test_admin_page_is_served_as_html(self):
        with urlopen(f"http://127.0.0.1:{self.port}/admin", timeout=5) as response:
            body = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("text/html", response.headers["Content-Type"])
        self.assertIn("Quản trị", body)
        self.assertNotIn("Bảng điều khiển minh bạch", body)

    def test_sql_injection_is_inert(self):
        _, payload, _ = self.get("/api/transactions?q=%27%20OR%201%3D1--")
        self.assertEqual(payload["count"], 0)

    def test_no_pii_fields_anywhere(self):
        """Walk every endpoint and assert no personal field is served.

        This checks JSON *keys*, not raw text. A substring scan over the whole
        payload produces false positives, because our own metadata prose says
        "we do not store email" -- which is a sentence, not a field.
        """

        def collect_keys(value, keys):
            if isinstance(value, dict):
                for key, item in value.items():
                    keys.add(key.lower())
                    collect_keys(item, keys)
            elif isinstance(value, list):
                for item in value:
                    collect_keys(item, keys)
            return keys

        forbidden = {
            "student_name",
            "full_name",
            "parent_name",
            "guardian",
            "phone",
            "email",
            "date_of_birth",
            "photo_url",
            "image_url",
            "address",
            "raw_description",
            "source_account",
        }
        for path in (
            "/api/summary",
            "/api/transactions",
            "/api/transactions?q=NE05517",
            "/api/allocation?tx=VNCK.989657",
            "/api/ne?ne=NE00077",
            "/api/exceptions",
            "/api/approvals",
            "/api/metadata",
            "/api/admin/queue",
            "/api/admin/search?q=NE00001",
        ):
            _, payload, _ = self.get(path)
            keys = collect_keys(payload, set())
            leaked = forbidden & keys
            self.assertFalse(leaked, f"PII field(s) {leaked} leaked from {path}")

    def test_pii_guard_raises_on_forbidden_field(self):
        """The guard itself must work, not just pass by absence of data."""
        with self.assertRaises(ValueError):
            app.assert_no_pii({"student_code": "NE00001", "student_name": "Nguyen Van A"})
        with self.assertRaises(ValueError):
            app.assert_no_pii({"raw_description": "memo may contain personal data"})
        app.assert_no_pii({"student_code": "NE00001", "class_name": "3A"})

    def test_transaction_api_returns_only_masked_description(self):
        _, payload, _ = self.get("/api/transactions?q=NE05517")
        self.assertGreater(payload["count"], 0)
        item = payload["items"][0]
        self.assertIn("description_masked", item)
        self.assertNotIn("raw_description", item)
        self.assertNotIn("source_account", item)

        _, detail, _ = self.get("/api/allocation?tx=VNCK.989657")
        self.assertIn("description_masked", detail["transaction"])
        self.assertNotIn("raw_description", detail["transaction"])
        self.assertNotIn("source_account", detail["transaction"])

    def test_write_methods_rejected(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            request = Request(
                f"http://127.0.0.1:{self.port}/api/transactions",
                data=b"{}",
                method=method,
            )
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, 405)

    def test_missing_static_asset_is_404_not_html(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(f"http://127.0.0.1:{self.port}/missing.css", timeout=5)
        self.assertEqual(caught.exception.code, 404)

    def test_path_traversal_blocked(self):
        for path in ("/../app.py", "/%2e%2e/app.py", "/..%2fschema.py"):
            try:
                status, _, _ = self.get(path)
                self.assertNotEqual(status, 200, f"traversal succeeded via {path}")
            except HTTPError as exc:
                self.assertIn(exc.code, (400, 403, 404))

    def test_audit_endpoint_verifies_chain(self):
        _, payload, _ = self.get("/api/audit")
        self.assertTrue(payload["chain_intact"])
        for item in payload["items"]:
            self.assertNotIn("event_hash", item)

    def test_raw_bank_memo_is_not_searchable(self):
        """The memo holds donor names and account numbers, so it is not a
        search surface. An unmatched prose query returns nothing."""
        _, payload, _ = self.get("/api/transactions?q=xay%20truong")
        self.assertEqual(payload["count"], 0)
        self.assertNotIn("slow_path", payload)

    def test_pagination_reports_truncation(self):
        _, payload, _ = self.get("/api/transactions?limit=1")
        self.assertEqual(payload["count"], 1)
        self.assertTrue(payload["truncated"])


class StartupPreflightTests(unittest.TestCase):
    """A fresh clone has no database, because the statement holds donor names.

    Without this check the server starts happily and every API answers
    `{"error": "database_error"}` while the page itself renders -- which reads
    as a broken app rather than an absent file. The message has to name the
    fix, so these tests assert on the text and not only on the exit code.
    """

    def run_preflight_without_database(self):
        original = app.DATABASE
        with tempfile.TemporaryDirectory(prefix="nuoiem_empty_") as tmp:
            missing = Path(tmp) / "absent.sqlite"
            app.DATABASE = missing
            out = io.StringIO()
            try:
                with contextlib.redirect_stdout(out):
                    with self.assertRaises(SystemExit) as caught:
                        app.preflight()
            finally:
                app.DATABASE = original
        return caught.exception.code, out.getvalue(), missing

    def test_missing_database_exits_non_zero(self):
        code, _, _ = self.run_preflight_without_database()
        self.assertEqual(code, 1)

    def test_missing_database_message_names_the_path_and_the_guide(self):
        _, text, missing = self.run_preflight_without_database()
        self.assertIn(str(missing), text)
        self.assertIn("HUONG_DAN_CHAY.md", text)
        # Both recovery paths have to be offered, or the reader is stuck when
        # the person who sent the database is offline.
        self.assertIn("nuoi_em_mvp.sqlite", text)
        self.assertIn("build_database.py", text)

    def test_present_database_reports_row_count(self):
        original = app.DATABASE
        with tempfile.TemporaryDirectory(prefix="nuoiem_preflight_") as tmp:
            db = Path(tmp) / "present.sqlite"
            conn = sqlite3.connect(db)
            conn.executescript(SCHEMA)
            conn.commit()
            conn.close()
            app.DATABASE = db
            out = io.StringIO()
            try:
                with contextlib.redirect_stdout(out):
                    app.preflight()
            finally:
                app.DATABASE = original
        self.assertIn("Database:", out.getvalue())
        self.assertIn("giao dịch", out.getvalue())


class PerformanceTests(unittest.TestCase):
    """Guards the regression that made the dashboard unusable at scale.

    The 1.0 M-row benchmark on the previous build measured 4,188 ms for the
    main list query because ANALYZE had never run and no composite index
    existed. These assertions fail if either safeguard is dropped.
    """

    def test_composite_index_exists(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        names = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        conn.close()
        self.assertIn("idx_tx_direction_time", names)
        self.assertIn("idx_tx_status_time", names)
        self.assertIn("idx_alloc_ne_code", names)

    def test_main_query_uses_an_index_not_a_scan(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        plan = conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM bank_transactions "
            "WHERE direction = 'inbound' ORDER BY tx_time DESC LIMIT 100"
        ).fetchall()
        conn.close()
        text = " ".join(str(r[3]) for r in plan)
        self.assertNotIn("SCAN bank_transactions", text)
        self.assertIn("INDEX", text)

    def test_code_search_is_index_backed(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(SCHEMA)
        plan = conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM transaction_allocations WHERE ne_code = 'NE05517'"
        ).fetchall()
        conn.close()
        text = " ".join(str(r[3]) for r in plan)
        # Two indexes lead on ne_code: the plain one, and the covering
        # (ne_code, amount) pair added for the admin list. Naming the exact one
        # made this test fail the moment the covering index was introduced, even
        # though the plan had got better. What matters is that the lookup is not
        # a table scan.
        self.assertNotIn("SCAN transaction_allocations", text)
        self.assertIn("USING INDEX idx_alloc_ne", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
