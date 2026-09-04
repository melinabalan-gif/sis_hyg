from uuid import UUID

from hys_api.core.request_id import normalize_request_id


def test_valid_request_id_is_canonicalized() -> None:
    value = "00000000-0000-0000-0000-000000000099"
    assert normalize_request_id(value) == value


def test_invalid_request_id_is_replaced() -> None:
    generated = normalize_request_id("contenido-no-confiable")
    assert str(UUID(generated)) == generated
