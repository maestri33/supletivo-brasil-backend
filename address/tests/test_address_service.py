"""Tests for address service — unit tests for address_service.py."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFound, ValidationError
from app.models.address import Address
from app.schemas.address import AddressCreate, AddressPatch

pytestmark = pytest.mark.asyncio

TEST_EXTERNAL_ID = UUID("00000000-0000-0000-0000-000000000001")


class TestCreateAddress:
    """create_address — CRUD create with FK validation."""

    async def test_creates_address(self, session: AsyncSession):
        from app.services.address_service import create_address

        data = AddressCreate(
            external_id=TEST_EXTERNAL_ID,
            kind="home",
            zipcode="01310100",
            street="Av Paulista",
            number="1000",
            neighborhood="Bela Vista",
            city="São Paulo",
            state="SP",
        )
        result = await create_address(session, data)

        assert result.external_id == TEST_EXTERNAL_ID
        assert result.kind == "home"
        assert result.street == "Av Paulista"
        assert result.zipcode == "01310100"
        assert result.id is not None

    async def test_creates_with_minimal_fields(self, session: AsyncSession):
        from app.services.address_service import create_address

        data = AddressCreate(
            external_id=TEST_EXTERNAL_ID,
            kind="billing",
            zipcode="70000000",
            street="Rua Teste",
            city="Brasília",
            state="DF",
        )
        result = await create_address(session, data)
        assert result.country == "BR"  # default
        assert result.number is None
        assert result.complement is None

    async def test_defaults_country_to_br(self, session: AsyncSession):
        from app.services.address_service import create_address

        data = AddressCreate(
            external_id=TEST_EXTERNAL_ID,
            kind="shipping",
            zipcode="20000000",
            street="Rua Exemplo",
            city="Rio de Janeiro",
            state="RJ",
        )
        result = await create_address(session, data)
        assert result.country == "BR"


class TestGetAddress:
    """get_address — CRUD read by ID."""

    async def test_returns_existing_address(self, session: AsyncSession):
        from app.services.address_service import create_address, get_address

        data = AddressCreate(
            external_id=TEST_EXTERNAL_ID,
            kind="home",
            zipcode="01310100",
            street="Av Paulista",
            number="1000",
            city="São Paulo",
            state="SP",
        )
        created = await create_address(session, data)
        result = await get_address(session, created.id)
        assert result.id == created.id
        assert result.street == "Av Paulista"

    async def test_raises_not_found_for_missing_id(self, session: AsyncSession):
        from app.services.address_service import get_address

        fake_id = uuid4()
        with pytest.raises(NotFound, match=str(fake_id)):
            await get_address(session, fake_id)


class TestListAddresses:
    """list_addresses — listing with filters."""

    async def test_returns_all_without_filter(self, session: AsyncSession):
        from app.services.address_service import create_address, list_addresses

        for i in range(3):
            await create_address(
                session,
                AddressCreate(
                    external_id=TEST_EXTERNAL_ID,
                    kind="home" if i % 2 == 0 else "billing",
                    zipcode=f"0100000{i}",
                    street=f"Rua {i}",
                    city="São Paulo",
                    state="SP",
                ),
            )
        results = await list_addresses(session)
        assert len(results) >= 3

    async def test_filters_by_kind(self, session: AsyncSession):
        from app.services.address_service import create_address, list_addresses

        await create_address(
            session,
            AddressCreate(
                external_id=TEST_EXTERNAL_ID,
                kind="home",
                zipcode="01000001",
                street="Rua Home",
                city="São Paulo",
                state="SP",
            ),
        )
        await create_address(
            session,
            AddressCreate(
                external_id=TEST_EXTERNAL_ID,
                kind="billing",
                zipcode="01000002",
                street="Rua Billing",
                city="São Paulo",
                state="SP",
            ),
        )
        homes = await list_addresses(session, kind="home")
        assert all(a.kind == "home" for a in homes)

    async def test_respects_limit_and_offset(self, session: AsyncSession):
        from app.services.address_service import create_address, list_addresses

        for i in range(5):
            await create_address(
                session,
                AddressCreate(
                    external_id=TEST_EXTERNAL_ID,
                    kind="home",
                    zipcode=f"0100000{i}",
                    street=f"Rua {i}",
                    city="São Paulo",
                    state="SP",
                ),
            )
        first_two = await list_addresses(session, limit=2, offset=0)
        assert len(first_two) == 2
        assert first_two[0] != first_two[1]


class TestCurrentByKind:
    """current_by_kind — latest address of a kind."""

    async def test_returns_most_recent(self, session: AsyncSession):
        from app.services.address_service import create_address, current_by_kind

        addr1 = await create_address(
            session,
            AddressCreate(
                external_id=TEST_EXTERNAL_ID,
                kind="home",
                zipcode="01000001",
                street="Rua Velha",
                city="São Paulo",
                state="SP",
            ),
        )
        addr2 = await create_address(
            session,
            AddressCreate(
                external_id=TEST_EXTERNAL_ID,
                kind="home",
                zipcode="01000002",
                street="Rua Nova",
                city="São Paulo",
                state="SP",
            ),
        )
        current = await current_by_kind(session, TEST_EXTERNAL_ID, "home")
        assert current.id == addr2.id
        assert current.street == "Rua Nova"

    async def test_raises_not_found_for_missing_kind(self, session: AsyncSession):
        from app.services.address_service import current_by_kind

        with pytest.raises(NotFound, match="shipping"):
            await current_by_kind(session, TEST_EXTERNAL_ID, "shipping")


class TestPatchAddress:
    """patch_address — partial update."""

    async def test_updates_fields(self, session: AsyncSession):
        from app.services.address_service import create_address, patch_address

        created = await create_address(
            session,
            AddressCreate(
                external_id=TEST_EXTERNAL_ID,
                kind="home",
                zipcode="01000001",
                street="Rua Antiga",
                city="São Paulo",
                state="SP",
            ),
        )
        updated = await patch_address(
            session,
            created.id,
            AddressPatch(street="Rua Nova", number="999"),
        )
        assert updated.street == "Rua Nova"
        assert updated.number == "999"
        assert updated.zipcode == "01000001"  # unchanged

    async def test_noop_when_no_updates(self, session: AsyncSession):
        from app.services.address_service import create_address, patch_address

        created = await create_address(
            session,
            AddressCreate(
                external_id=TEST_EXTERNAL_ID,
                kind="home",
                zipcode="01000001",
                street="Rua Teste",
                city="São Paulo",
                state="SP",
            ),
        )
        updated = await patch_address(session, created.id, AddressPatch())
        assert updated.id == created.id
        assert updated.street == "Rua Teste"

    async def test_raises_not_found(self, session: AsyncSession):
        from app.services.address_service import patch_address

        fake_id = uuid4()
        with pytest.raises(NotFound):
            await patch_address(session, fake_id, AddressPatch(street="X"))


class TestDeleteAddress:
    """delete_address — CRUD delete."""

    async def test_deletes_existing(self, session: AsyncSession):
        from app.services.address_service import create_address, delete_address, get_address

        created = await create_address(
            session,
            AddressCreate(
                external_id=TEST_EXTERNAL_ID,
                kind="home",
                zipcode="01000001",
                street="Rua Delete",
                city="São Paulo",
                state="SP",
            ),
        )
        await delete_address(session, created.id)
        with pytest.raises(NotFound):
            await get_address(session, created.id)

    async def test_raises_not_found(self, session: AsyncSession):
        from app.services.address_service import delete_address

        with pytest.raises(NotFound):
            await delete_address(session, uuid4())
