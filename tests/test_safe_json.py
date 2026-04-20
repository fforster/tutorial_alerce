from src.services.safe_json import safe_json_loads


def test_preserves_lsst_oid_as_string():
    raw = '{"oid": 1234567890123456789}'
    result = safe_json_loads(raw)
    assert result == {"oid": "1234567890123456789"}


def test_normal_int_unchanged():
    result = safe_json_loads('{"n": 42, "float": 1.5}')
    assert result == {"n": 42, "float": 1.5}


def test_array_of_big_ints():
    result = safe_json_loads("[1234567890123456789, 9876543210987654321]")
    assert result == ["1234567890123456789", "9876543210987654321"]


def test_negative_big_int():
    result = safe_json_loads('{"oid": -1234567890123456789}')
    assert result == {"oid": "-1234567890123456789"}


def test_string_containing_digits_untouched():
    # 16-digit *string* value should remain a string, quotes preserved.
    result = safe_json_loads('{"label": "1234567890123456"}')
    assert result == {"label": "1234567890123456"}


def test_bytes_input():
    result = safe_json_loads(b'{"oid": 1234567890123456789}')
    assert result == {"oid": "1234567890123456789"}
