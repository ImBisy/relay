"""SQLite storage layer tests."""
from __future__ import annotations

from src.storage import (
    CalendarStore,
    LogsStore,
    NotesStore,
    PendingActionsStore,
    RemindersStore,
)
from src.storage.models import (
    ActionLogEntry,
    CalendarEvent,
    Note,
    PendingAction,
    Reminder,
)


def test_reminders_create_and_list(stores):
    rs: RemindersStore = stores["reminders"]
    rs.create(Reminder(id="r1", text="call mom"))
    rs.create(Reminder(id="r2", text="buy milk"))
    items = rs.list_active()
    assert {r.id for r in items} == {"r1", "r2"}


def test_reminders_complete_and_delete(stores):
    rs: RemindersStore = stores["reminders"]
    rs.create(Reminder(id="r1", text="call mom"))
    assert rs.mark_completed("r1") is True
    assert rs.list_active() == []
    assert rs.delete("r1") is True
    assert rs.get("r1") is None


def test_notes_search(stores):
    ns: NotesStore = stores["notes"]
    ns.create(Note(id="n1", content="biology mock on Tuesday"))
    ns.create(Note(id="n2", content="grocery list"))
    found = ns.search("biology")
    assert len(found) == 1 and found[0].id == "n1"


def test_calendar_in_range(stores):
    cs: CalendarStore = stores["calendar"]
    cs.create(CalendarEvent(id="e1", title="meeting", start_time="2026-05-08T10:00:00"))
    cs.create(CalendarEvent(id="e2", title="lunch", start_time="2026-05-09T12:00:00"))
    items = cs.list_in_range("2026-05-08T00:00:00", "2026-05-09T00:00:00")
    assert {e.id for e in items} == {"e1"}


def test_logs_by_plan(stores):
    ls: LogsStore = stores["logs"]
    ls.append(ActionLogEntry(status="step_succeeded", plan_id="p1",
                              step_index=0, message="ok"))
    ls.append(ActionLogEntry(status="step_succeeded", plan_id="p1",
                              step_index=1, message="ok"))
    ls.append(ActionLogEntry(status="step_succeeded", plan_id="p2",
                              step_index=0, message="ok"))
    plan_logs = ls.list_by_plan("p1")
    assert len(plan_logs) == 2
    assert [le.step_index for le in plan_logs] == [0, 1]


def test_pending_actions_lifecycle(stores):
    ps: PendingActionsStore = stores["pending"]
    pending = PendingAction(id="p1", tool_name="email",
                              args={"recipient_email": "a@b.com", "body": "hi"},
                              preview="Email a@b.com — hi")
    ps.create(pending)
    assert ps.latest_pending() is not None
    assert ps.confirm("p1") is True
    assert ps.latest_pending() is None
