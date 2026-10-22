from sqlalchemy import update
from .db import Session, WorkflowRun, WorkflowEvent, serialize


def emit(run_id, event_type, agent=None, **payload):
    with Session.begin() as db:
        sequence = db.scalar(
            update(WorkflowRun)
            .where(WorkflowRun.id == run_id)
            .values(next_sequence=WorkflowRun.next_sequence + 1)
            .returning(WorkflowRun.next_sequence)
        )
        event = WorkflowEvent(run_id=run_id, sequence=sequence, type=event_type, agent=agent, payload=payload)
        db.add(event)
        db.flush()
        return serialize(event)
