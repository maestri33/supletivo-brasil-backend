"""Tests for address validators — pure functions, no DB needed."""

import pytest

from app.exceptions import ValidationError
from app.validators.address_fields import validate_country, validate_kind, validate_state
from app.validators.zipcode import validate_zipcode


class TestValidateZipcode:
    """validate_zipcode — normalizes CEP to 8 digits."""

    def test_strips_non_digits(self):
        assert validate_zipcode("01310-100") == "01310100"

    def test_accepts_plain_digits(self):
        assert validate_zipcode("01310100") == "01310100"

    def test_raises_on_none(self):
        with pytest.raises(ValidationError, match="obrigatório"):
            validate_zipcode(None)

    def test_raises_on_empty(self):
        with pytest.raises(ValidationError, match="obrigatório"):
            validate_zipcode("")

    def test_raises_on_short(self):
        with pytest.raises(ValidationError, match="8 dígitos"):
            validate_zipcode("123")

    def test_raises_on_all_same_digits(self):
        with pytest.raises(ValidationError, match="inválido"):
            validate_zipcode("11111111")

    def test_accepts_max_cep(self):
        assert validate_zipcode("99999999") == "99999999"


class TestValidateKind:
    """validate_kind — normalizes kind aliases."""

    def test_accepts_home(self):
        assert validate_kind("home") == "home"

    def test_accepts_billing(self):
        assert validate_kind("billing") == "billing"

    def test_accepts_shipping(self):
        assert validate_kind("shipping") == "shipping"

    def test_normalizes_portuguese_aliases(self):
        assert validate_kind("casa") == "home"
        assert validate_kind("residencial") == "home"
        assert validate_kind("cobranca") == "billing"
        assert validate_kind("cobrança") == "billing"
        assert validate_kind("entrega") == "shipping"
        assert validate_kind("envio") == "shipping"

    def test_case_insensitive(self):
        assert validate_kind("HOME") == "home"
        assert validate_kind("Casa") == "home"

    def test_raises_on_none(self):
        with pytest.raises(ValidationError, match="obrigatório"):
            validate_kind(None)

    def test_raises_on_invalid(self):
        with pytest.raises(ValidationError, match="inválido"):
            validate_kind("foo")


class TestValidateState:
    """validate_state — 2-letter Brazilian state code."""

    def test_accepts_all_valid_uf(self):
        for uf in ["SP", "RJ", "MG", "DF", "BA", "RS", "PR", "SC", "AM", "PA"]:
            assert validate_state(uf) == uf

    def test_normalizes_case(self):
        assert validate_state("sp") == "SP"
        assert validate_state("Sp") == "SP"

    def test_raises_on_none(self):
        with pytest.raises(ValidationError, match="obrigatório"):
            validate_state(None)

    def test_raises_on_invalid(self):
        with pytest.raises(ValidationError, match="inválido"):
            validate_state("XYZ")

    def test_raises_on_short(self):
        with pytest.raises(ValidationError, match="inválido"):
            validate_state("S")


class TestValidateCountry:
    """validate_country — ISO-3166-1 alpha-2."""

    def test_defaults_to_br(self):
        assert validate_country(None) == "BR"
        assert validate_country("") == "BR"

    def test_normalizes_case(self):
        assert validate_country("us") == "US"
        assert validate_country("BR") == "BR"

    def test_raises_on_long(self):
        with pytest.raises(ValidationError, match="inválido"):
            validate_country("USA")

    def test_raises_on_numeric(self):
        with pytest.raises(ValidationError, match="inválido"):
            validate_country("12")
