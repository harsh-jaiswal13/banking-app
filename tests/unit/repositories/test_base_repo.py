"""
Tests for BaseRepository (app/repositories/base.py)

We test every CRUD method using the User model as the concrete implementation
since BaseRepository is generic and needs a real model to work against.

These tests hit a REAL SQLite database (in-memory).
There are no mocks here — we are testing actual SQL behavior.
"""

import pytest
from app.repositories.base import BaseRepository
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_repo(db_session):
    return BaseRepository(User, db_session)


def user_data(
    email="test@example.com",
    phone="9876543210",
    full_name="Test User",
    password_hash="hashed_pw",
):
    return {"email": email, "phone": phone,
            "full_name": full_name, "password_hash": password_hash}


# ---------------------------------------------------------------------------
# create()
# ---------------------------------------------------------------------------

class TestBaseCreate:

    @pytest.mark.asyncio
    async def test_create_returns_model_instance(self, db_session):
        """create() must return the model object, not a dict or None"""
        repo = make_repo(db_session)
        result = await repo.create(user_data())

        assert result is not None
        assert isinstance(result, User)

    @pytest.mark.asyncio
    async def test_create_assigns_auto_primary_key(self, db_session):
        """DB must auto-assign a positive integer primary key"""
        repo = make_repo(db_session)
        result = await repo.create(user_data())

        assert result.user_id is not None
        assert result.user_id > 0

    @pytest.mark.asyncio
    async def test_create_persists_all_fields_correctly(self, db_session):
        """Every field in the input dict must appear on the returned object"""
        repo = make_repo(db_session)
        result = await repo.create(user_data(email="john@example.com", full_name="John"))

        assert result.email == "john@example.com"
        assert result.full_name == "John"
        assert result.phone == "9876543210"

    @pytest.mark.asyncio
    async def test_create_multiple_records_get_unique_ids(self, db_session):
        """Two separate creates must never share the same primary key"""
        repo = make_repo(db_session)
        u1 = await repo.create(user_data(email="a@x.com", phone="1111111111"))
        u2 = await repo.create(user_data(email="b@x.com", phone="2222222222"))

        assert u1.user_id != u2.user_id


# ---------------------------------------------------------------------------
# get()
# ---------------------------------------------------------------------------

class TestBaseGet:

    @pytest.mark.asyncio
    async def test_get_returns_correct_record(self, db_session):
        """get(id) must return exactly the record with that ID"""
        repo = make_repo(db_session)
        created = await repo.create(user_data())

        fetched = await repo.get(created.user_id)

        assert fetched is not None
        assert fetched.user_id == created.user_id
        assert fetched.email == created.email

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing_id(self, db_session):
        """
        Nonexistent ID → None.
        Must NOT raise an exception — callers check for None.
        """
        repo = make_repo(db_session)

        result = await repo.get(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_right_user_among_many(self, db_session):
        """get() must not return the wrong record when multiple exist"""
        repo = make_repo(db_session)
        await repo.create(user_data(email="a@x.com", phone="1111111111"))
        u2 = await repo.create(user_data(email="b@x.com", phone="2222222222"))

        fetched = await repo.get(u2.user_id)

        assert fetched.email == "b@x.com"


# ---------------------------------------------------------------------------
# get_multi()
# ---------------------------------------------------------------------------

class TestBaseGetMulti:

    @pytest.mark.asyncio
    async def test_get_multi_returns_all_records_by_default(self, db_session):
        """No skip/limit → all records returned"""
        repo = make_repo(db_session)
        await repo.create(user_data(email="a@x.com", phone="1111111111"))
        await repo.create(user_data(email="b@x.com", phone="2222222222"))
        await repo.create(user_data(email="c@x.com", phone="3333333333"))

        results = await repo.get_multi()

        assert len(list(results)) == 3

    @pytest.mark.asyncio
    async def test_get_multi_skip_offsets_results(self, db_session):
        """skip=1 must skip exactly 1 record"""
        repo = make_repo(db_session)
        await repo.create(user_data(email="a@x.com", phone="1111111111"))
        await repo.create(user_data(email="b@x.com", phone="2222222222"))
        await repo.create(user_data(email="c@x.com", phone="3333333333"))

        results = await repo.get_multi(skip=1)

        assert len(list(results)) == 2

    @pytest.mark.asyncio
    async def test_get_multi_limit_caps_results(self, db_session):
        """limit=2 must return at most 2 records"""
        repo = make_repo(db_session)
        await repo.create(user_data(email="a@x.com", phone="1111111111"))
        await repo.create(user_data(email="b@x.com", phone="2222222222"))
        await repo.create(user_data(email="c@x.com", phone="3333333333"))

        results = await repo.get_multi(limit=2)

        assert len(list(results)) == 2

    @pytest.mark.asyncio
    async def test_get_multi_filter_returns_matching_only(self, db_session):
        """filters={"full_name": "Alice"} must exclude non-Alice records"""
        repo = make_repo(db_session)
        await repo.create(user_data(email="alice@x.com", phone="1111111111", full_name="Alice"))
        await repo.create(user_data(email="bob@x.com", phone="2222222222", full_name="Bob"))

        results = await repo.get_multi(filters={"full_name": "Alice"})
        results = list(results)

        assert len(results) == 1
        assert results[0].full_name == "Alice"

    @pytest.mark.asyncio
    async def test_get_multi_returns_empty_list_for_empty_table(self, db_session):
        """Empty DB → empty list, not None"""
        repo = make_repo(db_session)

        results = await repo.get_multi()

        assert list(results) == []


# ---------------------------------------------------------------------------
# count()
# ---------------------------------------------------------------------------

class TestBaseCount:

    @pytest.mark.asyncio
    async def test_count_returns_correct_total(self, db_session):
        """count() must match exact number of records in the table"""
        repo = make_repo(db_session)
        await repo.create(user_data(email="a@x.com", phone="1111111111"))
        await repo.create(user_data(email="b@x.com", phone="2222222222"))

        total = await repo.count()

        assert total == 2

    @pytest.mark.asyncio
    async def test_count_returns_zero_for_empty_table(self, db_session):
        """Empty table → count() = 0, not None"""
        repo = make_repo(db_session)

        total = await repo.count()

        assert total == 0

    @pytest.mark.asyncio
    async def test_count_with_filter_counts_matching_only(self, db_session):
        """count(filters=...) must count only records matching all filters"""
        repo = make_repo(db_session)
        await repo.create(user_data(email="a@x.com", phone="1111111111", full_name="Alice"))
        await repo.create(user_data(email="b@x.com", phone="2222222222", full_name="Alice"))
        await repo.create(user_data(email="c@x.com", phone="3333333333", full_name="Bob"))

        alice_count = await repo.count(filters={"full_name": "Alice"})

        assert alice_count == 2

    @pytest.mark.asyncio
    async def test_count_increments_after_create(self, db_session):
        """count() must go up by 1 after each create()"""
        repo = make_repo(db_session)

        assert await repo.count() == 0

        await repo.create(user_data(email="a@x.com", phone="1111111111"))
        assert await repo.count() == 1

        await repo.create(user_data(email="b@x.com", phone="2222222222"))
        assert await repo.count() == 2


# ---------------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------------

class TestBaseUpdate:

    @pytest.mark.asyncio
    async def test_update_changes_specified_fields(self, db_session):
        """Fields in the update dict must be changed"""
        repo = make_repo(db_session)
        user = await repo.create(user_data(full_name="Old Name"))

        updated = await repo.update(user, {"full_name": "New Name"})

        assert updated.full_name == "New Name"

    @pytest.mark.asyncio
    async def test_update_leaves_unspecified_fields_unchanged(self, db_session):
        """Fields NOT in the update dict must not be touched"""
        repo = make_repo(db_session)
        user = await repo.create(user_data(email="stay@x.com"))

        await repo.update(user, {"full_name": "New Name"})

        assert user.email == "stay@x.com"

    @pytest.mark.asyncio
    async def test_update_persists_to_database(self, db_session):
        """
        Re-fetching the record after update must return the new value.
        This confirms the change was committed to DB, not just in memory.
        """
        repo = make_repo(db_session)
        user = await repo.create(user_data())
        await repo.update(user, {"full_name": "Persisted"})

        refetched = await repo.get(user.user_id)

        assert refetched.full_name == "Persisted"

    @pytest.mark.asyncio
    async def test_update_ignores_nonexistent_fields(self, db_session):
        """
        Fields not on the model must be silently skipped — no AttributeError.
        BaseRepository checks hasattr() before setattr().
        """
        repo = make_repo(db_session)
        user = await repo.create(user_data())

        # Should not crash even though "fake_column" isn't on User model
        updated = await repo.update(user, {"fake_column": "x", "full_name": "OK"})

        assert updated.full_name == "OK"


# ---------------------------------------------------------------------------
# delete()
# ---------------------------------------------------------------------------

class TestBaseDelete:

    @pytest.mark.asyncio
    async def test_delete_returns_true_on_success(self, db_session):
        """Successful delete must return True"""
        repo = make_repo(db_session)
        user = await repo.create(user_data())

        result = await repo.delete(user.user_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_removes_record_from_db(self, db_session):
        """After delete(), get() for that ID must return None"""
        repo = make_repo(db_session)
        user = await repo.create(user_data())
        user_id = user.user_id

        await repo.delete(user_id)

        assert await repo.get(user_id) is None

    @pytest.mark.asyncio
    async def test_delete_returns_false_for_nonexistent_id(self, db_session):
        """Deleting an ID that was never created → False, not an exception"""
        repo = make_repo(db_session)

        result = await repo.delete(99999)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_only_removes_target_record(self, db_session):
        """delete(id1) must NOT affect other records"""
        repo = make_repo(db_session)
        u1 = await repo.create(user_data(email="a@x.com", phone="1111111111"))
        u2 = await repo.create(user_data(email="b@x.com", phone="2222222222"))

        await repo.delete(u1.user_id)

        assert await repo.get(u1.user_id) is None   # deleted
        assert await repo.get(u2.user_id) is not None  # untouched

    @pytest.mark.asyncio
    async def test_count_decrements_after_delete(self, db_session):
        """count() must decrease by 1 after delete()"""
        repo = make_repo(db_session)
        u1 = await repo.create(user_data(email="a@x.com", phone="1111111111"))
        await repo.create(user_data(email="b@x.com", phone="2222222222"))

        await repo.delete(u1.user_id)

        assert await repo.count() == 1


# ---------------------------------------------------------------------------
# exists()
# ---------------------------------------------------------------------------

class TestBaseExists:

    @pytest.mark.asyncio
    async def test_exists_true_when_record_matches(self, db_session):
        """exists(filter) → True when a matching record is in DB"""
        repo = make_repo(db_session)
        await repo.create(user_data(email="here@x.com"))

        result = await repo.exists({"email": "here@x.com"})

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false_when_no_match(self, db_session):
        """exists(filter) → False when nothing matches"""
        repo = make_repo(db_session)

        result = await repo.exists({"email": "ghost@x.com"})

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_requires_all_filters_to_match(self, db_session):
        """Multiple filters: ALL must match for exists() to return True"""
        repo = make_repo(db_session)
        await repo.create(user_data(email="a@x.com", phone="1111111111"))

        # Both match → True
        assert await repo.exists({"email": "a@x.com", "phone": "1111111111"}) is True

        # One doesn't match → False
        assert await repo.exists({"email": "a@x.com", "phone": "9999999999"}) is False

    @pytest.mark.asyncio
    async def test_exists_false_after_delete(self, db_session):
        """Once a record is deleted, exists() must return False"""
        repo = make_repo(db_session)
        user = await repo.create(user_data(email="bye@x.com"))
        await repo.delete(user.user_id)

        result = await repo.exists({"email": "bye@x.com"})

        assert result is False