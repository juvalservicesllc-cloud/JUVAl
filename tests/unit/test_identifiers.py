import pytest

from juval.domain.identifiers import is_valid_asin, is_valid_ean, is_valid_gtin, is_valid_upc


@pytest.mark.parametrize("asin", ["B0EXAMPLE1", "1234567890", "ABCDEFGHIJ"])
def test_valid_asin_shapes(asin):
    assert is_valid_asin(asin)


@pytest.mark.parametrize("asin", ["short", "toolongasinvalue", "b0exampl1", "B0-EXAMP1"])
def test_invalid_asin_shapes(asin):
    assert not is_valid_asin(asin)


@pytest.mark.parametrize("upc", ["036000291452", "049000042566"])
def test_valid_upc_checksums(upc):
    assert is_valid_upc(upc)


@pytest.mark.parametrize("upc", ["036000291451", "12345", "notanumber12"])
def test_invalid_upc(upc):
    assert not is_valid_upc(upc)


@pytest.mark.parametrize("ean", ["4006381333931", "5901234123457", "40170725"])
def test_valid_ean_checksums(ean):
    assert is_valid_ean(ean)


@pytest.mark.parametrize("ean", ["4006381333930", "123"])
def test_invalid_ean(ean):
    assert not is_valid_ean(ean)


def test_valid_gtin_accepts_valid_upc_and_ean():
    assert is_valid_gtin("036000291452")
    assert is_valid_gtin("4006381333931")


def test_invalid_gtin_wrong_length():
    assert not is_valid_gtin("123456")
