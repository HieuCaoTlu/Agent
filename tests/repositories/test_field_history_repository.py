"""Test `FieldHistoryRepository` — append-only, không có update/delete."""

from app.repositories.field_history_repository import FieldHistoryRepository


async def test_append_only_interface_has_no_mutation_methods() -> None:
    """Khẳng định repository không lộ hàm update/delete — bảo vệ tính bất biến (NT-7)."""
    assert not hasattr(FieldHistoryRepository, "update")
    assert not hasattr(FieldHistoryRepository, "delete")


async def test_append_and_list_by_session(db_session) -> None:
    import uuid

    session_id = uuid.uuid4()
    repo = FieldHistoryRepository(db_session)
    await repo.append(
        session_id=session_id,
        field_name="ho_ten",
        old_value=None,
        new_value="Nguyễn Văn A",
        change_source="llm_extraction",
    )
    await db_session.commit()

    history = await repo.list_by_session(session_id)
    assert len(history) == 1
    assert history[0].new_value == "Nguyễn Văn A"
    assert history[0].change_source == "llm_extraction"


async def test_list_by_field_filters_correctly(db_session) -> None:
    import uuid

    session_id = uuid.uuid4()
    repo = FieldHistoryRepository(db_session)
    await repo.append(session_id, "ho_ten", None, "A", "llm_extraction")
    await repo.append(session_id, "ngay_sinh", None, "01/01/2000", "llm_extraction")
    await db_session.commit()

    ho_ten_history = await repo.list_by_field(session_id, "ho_ten")
    assert len(ho_ten_history) == 1
    assert ho_ten_history[0].field_name == "ho_ten"
