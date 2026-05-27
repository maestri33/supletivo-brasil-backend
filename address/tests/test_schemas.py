"""Tests for address schemas — Pydantic validation."""

from uuid import UUID, uuid4

import pytest

from app.exceptions import ValidationError
from app.schemas.address import AddressCreate, AddressPatch, AddressRead

pytestmark = pytest.mark.asyncio


class TestAddressCreate:
    """AddressCreate — validation of all required fields."""

    def test_valid_minimal(self):
        data = AddressCreate(
            external_id=uuid4(),
            kind="home",
            zipcode="01310100",
            street="Av Paulista",
            city="São Paulo",
            state="SP",
        )
        assert data.kind == "home"
        assert data.zipcode == "01310100"
        assert data.country == "BR"

    def test_normalizes_zipcode_with_hyphen(self):
        data = AddressCreate(
            external_id=uuid4(),
            kind="home",
            zipcode="01310-100",
            street="Rua Teste",
            city="São Paulo",
            state="SP",
        )
        assert data.zipcode == "01310100"

    def test_normalizes_kind_alias(self):
        data = AddressCreate(
            external_id=uuid4(),
            kind="casa",
            zipcode="01310100",
            street="Rua Teste",
            city="São Paulo",
            state="SP",
        )
        assert data.kind == "home"

    def test_rejects_invalid_kind(self):
        with pytest.raises(Exception):  # pydantic.ValidationError
            AddressCreate(
                external_id=uuid4(),
                kind="invalid",
                zipcode="01310100",
                street="Rua Teste",
                city="São Paulo",
                state="SP",
            )

    def test_rejects_invalid_cep(self):
        with pytest.raises(Exception):
            AddressCreate(
                external_id=uuid4(),
                kind="home",
                zipcode="123",
                street="Rua Teste",
                city="São Paulo",
                state="SP",
            )

    def test_accepts_optional_fields(self):
        data = AddressCreate(
            external_id=uuid4(),
            kind="billing",
            zipcode="20000000",
            street="Rua Billing",
            number="42",
            complement="Apto 1",
            neighborhood="Centro",
            city="Rio de Janeiro",
            state="RJ",
            country="US",
            lat="-22.9068",
            lng="-43.1729",
        )
        assert data.number == "42"
        assert data.complement == "Apto 1"
        assert data.neighborhood == "Centro"
        assert data.country == "US"

    def test_rejects_extra_fields(self):
        with pytest.raises(Exception):
            AddressCreate(
                external_id=uuid4(),
                kind="home",
                zipcode="01310100",
                street="Rua",
                city="SP",
                state="SP",
                unknown="foo",
            )


class TestAddressPatch:
    """AddressPatch — partial update validation."""

    def test_all_fields_optional(self):
        data = AddressPatch()
        assert data.model_dump(exclude_unset=True) == {}

    def test_updates_single_field(self):
        data = AddressPatch(street="Rua Nova")
        assert data.street == "Rua Nova"

    def test_updates_kind_with_alias(self):
        data = AddressPatch(kind="cobranca")
        assert data.kind == "billing"

    def test_rejects_extra(self):
        with pytest.raises(Exception):
            AddressPatch(unknown="foo")


class TestAddressRead:
    """AddressRead — from-attributes model."""

    def test_from_attributes(self):
        import datetime

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        data = AddressRead(
            id=uuid4(),
            external_id=uuid4(),
            kind="home",
            zipcode="01310100",
            street="Av Paulista",
            city="São Paulo",
            state="SP",
            country="BR",
            created_at=now,
            updated_at=now,
        )
        assert data.kind == "home"
        assert data.created_at == now
