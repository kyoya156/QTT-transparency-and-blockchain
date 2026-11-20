import pytest

from transparency import merkle, records

T = "2026-11-16T09:30:00+07:00"


def test_income_fields_and_anonymous_default():
    r = records.income("BANK-1", 500_000, "D-001", T)
    assert r == {"id": "BANK-1", "direction": "in", "amount": 500_000, "currency": "VND",
                 "donor_id": "D-001", "donor_name": "Anonymous", "time": T}
    assert records.income("BANK-1", 1, "D-001", T, donor_name=" Lan ")["donor_name"] == "LAN"


def test_expense_type_open_until_data_is_cleaned():
    r = records.expense("BANK-2", 200_000, "R-017", T)
    assert r["recipient_type"] == "unassigned" and r["recipient_id"] == "R-017"
    assert records.expense("BANK-2", 1, "R-017", T, recipient_type="Child")["recipient_type"] == "child"


@pytest.mark.parametrize("bad", [
    lambda: records.income("BANK-1", 0, "D-1", T),
    lambda: records.income("BANK-1", 1.5, "D-1", T),
    lambda: records.income("BANK-1", 1, "", T),
    lambda: records.income("", 1, "D-1", T),
    lambda: records.income("BANK-1", 1, "D-1", "2026-11-16T09:30:00"),  # no timezone
    lambda: records.expense("BANK-2", 1, " ", T),
])
def test_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        bad()


def test_any_field_change_changes_the_leaf():
    salt = bytes(16)
    r = records.income("BANK-1", 500_000, "D-001", T, donor_name="Lan")
    base = merkle.leaf_hash(r, salt)
    for k, v in [("amount", 500_001), ("donor_name", "Lam"), ("donor_id", "D-002"), ("time", "2026-11-16T09:31:00+07:00")]:
        assert merkle.leaf_hash({**r, k: v}, salt) != base


def test_vietnamese_full_name_hashes_the_same_in_any_unicode_form():
    import unicodedata

    from transparency import merkle
    name = "Phạm Thanh Hùng"
    nfc, nfd = unicodedata.normalize("NFC", name), unicodedata.normalize("NFD", name)
    assert nfc != nfd                                    # different bytes, same look
    a = records.income("BANK-1", 1, "D-001", T, donor_name=nfc)
    b = records.income("BANK-1", 1, "D-001", T, donor_name="  " + nfd.replace(" ", "   ") + " ")
    assert a == b and a["donor_name"] == "PHAM THANH HUNG"
    assert merkle.leaf_hash(a, bytes(16)) == merkle.leaf_hash(b, bytes(16))
    # plain text, no diacritics (owner 2026-11-20): the bank's "PHAM THANH HUNG" is the same name
    assert records.income("BANK-1", 1, "D-001", T, donor_name="PHAM THANH HUNG") == a
    assert records.plain_name("Đỗ Thị Ánh") == "DO THI ANH"


H = "0x" + "ab" * 32


def test_link_adds_seq_prev_balance_source():
    r = records.link(records.income("B-1", 500, "D-1", T), 1, records.GENESIS, 1000, H)
    assert (r["seq"], r["prev"], r["balance"], r["source_hash"]) == (1, records.GENESIS, 1500, H)
    out = records.link(records.expense("B-2", 200, "R-1", T), 2, H, r["balance"], H)
    assert out["balance"] == 1300 and records.balance_before(out) == 1500


@pytest.mark.parametrize("bad", [
    lambda: records.link(records.income("B", 1, "D", T), 0, records.GENESIS, 0, H),
    lambda: records.link(records.income("B", 1, "D", T), 1, H, 0, H),          # first must link to GENESIS
    lambda: records.link(records.income("B", 1, "D", T), 2, "0x12", 0, H),
    lambda: records.link(records.income("B", 1, "D", T), 2, H, 0, "abc"),
])
def test_link_rejects_bad_values(bad):
    with pytest.raises(ValueError):
        bad()


def test_bank_time_in_the_future_is_refused():
    import datetime
    now = datetime.datetime.fromisoformat("2026-11-16T02:30:00+00:00")   # = 09:30 +07:00
    records.check_not_future(records.income("B", 1, "D", "2026-11-16T09:31:00+07:00"), now)   # within slack
    with pytest.raises(ValueError):
        records.check_not_future(records.income("B", 1, "D", "2026-11-16T09:40:00+07:00"), now)


def test_hide_name_keeps_only_a_salted_hash():
    ns = bytes(range(16))
    pub, name = records.hide_name(records.income("B", 1, "D", T, donor_name="Phạm Thanh Hùng"), ns)
    assert name == "PHAM THANH HUNG" and "donor_name" not in pub
    assert pub["donor_name_hash"] == records.name_hash("PHAM THANH HUNG", ns)
    assert records.hide_name(records.income("B", 1, "D", T, donor_name="X"), bytes(16))[0]["donor_name_hash"] \
        != pub["donor_name_hash"]
    out = records.expense("B", 1, "R", T)
    assert records.hide_name(out, None) == (out, None)
    with pytest.raises(ValueError):
        records.hide_name(records.income("B", 1, "D", T), None)       # money in needs a name salt
