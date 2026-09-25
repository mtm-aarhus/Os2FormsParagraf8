"""Tests for robot_framework/process.py — validering af submission_uuid.

submission_uuid flyder uescapet ind i et OData-filter
(src/sharepoint_client.py) og i en URL-sti (src/os2forms_client.py, som baerer
api-key-headeren). Et vellagt uuid skal derfor afvises tidligt, foer det
naar nogen af de to steder — se robot_framework/process.py::_validate_submission_uuid.
"""

import pytest

from robot_framework import process
from robot_framework.exceptions import BusinessError


VALID_UUID = "12345678-90ab-cdef-1234-567890abcdef"


def test_valid_uuid_passes_validation():
    # Skal ikke kaste noget.
    process._validate_submission_uuid(VALID_UUID)  # pylint: disable=protected-access


@pytest.mark.parametrize("bad_value", [
    "",
    "not-a-uuid",
    VALID_UUID + "'",  # apostrof — bryder OData-filteret
    "../../../admin",  # sti-traversal mod os2forms-URL'en
    VALID_UUID + "/../other-endpoint",
    "1234",
    VALID_UUID.upper() + "x",  # 37 tegn
    None,
])
def test_invalid_uuid_is_rejected_with_business_error(bad_value):
    with pytest.raises(BusinessError):
        process._validate_submission_uuid(bad_value)  # pylint: disable=protected-access


def test_rejection_message_names_the_shape_not_the_value():
    malicious = "'; DROP TABLE x; --"

    with pytest.raises(BusinessError) as excinfo:
        process._validate_submission_uuid(malicious)  # pylint: disable=protected-access

    message = str(excinfo.value)
    assert malicious not in message
    assert "36" in message  # facon-beskrivelsen naevner den forventede laengde


def test_valid_uuid_uppercase_is_accepted():
    # Hex-tegn kan komme i begge cases fra kilden.
    process._validate_submission_uuid(VALID_UUID.upper())  # pylint: disable=protected-access
