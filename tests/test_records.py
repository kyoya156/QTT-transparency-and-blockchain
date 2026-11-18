import pytest

from transparency import merkle, records

T = "2026-11-16T09:30:00+07:00"


def test_income_fields_and_anonymous_default():
    r = records.income("BANK-1", 500_000, "D-001", T)
    assert r == {"id": "BANK-1", "direction": "in", "amount": 500_000, "currency": "VND",
                 "donor_id": "D-001", "donor_name": "Anonymous", "time": T}
    assert records.income("BANK-1", 1, "D-001", T, donor_name=" Lan ")["donor_name"] == "Lan"


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
    assert a == b and a["donor_name"] == name
    assert merkle.leaf_hash(a, bytes(16)) == merkle.leaf_hash(b, bytes(16))
    # case and accents are kept as given: the bank's "PHAM THANH HUNG" stays a different record
    assert records.income("BANK-1", 1, "D-001", T, donor_name="PHAM THANH HUNG")["donor_name"] == "PHAM THANH HUNG"
