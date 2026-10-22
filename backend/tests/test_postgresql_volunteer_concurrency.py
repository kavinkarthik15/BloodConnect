import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.db.database import get_db as default_get_db
from app.main import app
from app.models.audit_log import AuditLog
from app.models.auth_security import BrowserSession
from app.models.blood_request import BloodRequest
from app.models.donation_confirmation import DonationConfirmation
from app.models.donor import DonorProfile
from app.models.match import DonorMatch
from app.models.notification import Notification
from app.models.response import DonorResponse
from app.models.user import User
from app.models.volunteer_assignment import VolunteerAssignment
from app.services.auth_service import create_access_token


POSTGRES_TEST_URL = os.environ.get("NSS_POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="Set NSS_POSTGRES_TEST_DATABASE_URL to a migrated disposable PostgreSQL database.",
)


@pytest.fixture(scope="module")
def postgres_sessions():
    if not POSTGRES_TEST_URL:
        pytest.skip("A disposable PostgreSQL database was not configured.")

    engine = create_engine(
        POSTGRES_TEST_URL,
        pool_size=8,
        max_overflow=0,
        connect_args={"options": "-c lock_timeout=5000 -c statement_timeout=10000"},
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def get_postgres_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    previous_override = app.dependency_overrides.get(default_get_db)
    app.dependency_overrides[default_get_db] = get_postgres_db
    try:
        yield session_factory, engine
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(default_get_db, None)
        else:
            app.dependency_overrides[default_get_db] = previous_override
        engine.dispose()


def _seed_assignment(session_factory, status="assigned"):
    suffix = uuid4().hex
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        requester = User(
            full_name="Synthetic requester",
            email=f"requester-{suffix}@example.test",
            phone="9876543210",
            password_hash="unused",
            role="requester",
        )
        volunteer = User(
            full_name="Synthetic volunteer",
            email=f"volunteer-{suffix}@example.test",
            phone="9876543210",
            password_hash="unused",
            role="volunteer",
        )
        coordinator = User(
            full_name="Synthetic coordinator",
            email=f"coordinator-{suffix}@example.test",
            phone="9876543210",
            password_hash="unused",
            role="coordinator",
        )
        db.add_all([requester, volunteer, coordinator])
        db.flush()
        request = BloodRequest(
            request_code=f"TEST-{suffix}",
            requester_id=requester.id,
            patient_reference="Synthetic concurrency test",
            blood_group="O+",
            units_required=1,
            units_confirmed=0,
            hospital_name="Synthetic hospital",
            hospital_address="1 Test Road",
            city="Bengaluru",
            required_at=now + timedelta(days=1),
            urgency="Normal",
            contact_name="Synthetic contact",
            contact_phone="9876543210",
            status="coordinating",
        )
        db.add(request)
        db.flush()
        assignment = VolunteerAssignment(
            request_id=request.id,
            volunteer_id=volunteer.id,
            assigned_by=coordinator.id,
            status=status,
        )
        db.add(assignment)
        tokens = {}
        for user in (volunteer, coordinator):
            session_id = str(uuid4())
            db.add(BrowserSession(
                id=session_id,
                user_id=user.id,
                expires_at=now + timedelta(hours=1),
            ))
            tokens[user.role] = create_access_token(
                user.email,
                session_id=session_id,
            )
        db.commit()
        return {
            "request_id": request.id,
            "assignment_id": assignment.id,
            "volunteer_id": volunteer.id,
            "coordinator_id": coordinator.id,
            "tokens": tokens,
        }


def _seed_request_workflow(session_factory, status="verified", units_required=1, donor_count=1):
    suffix = uuid4().hex
    now = datetime.now(timezone.utc)
    with session_factory() as db:
        requester = User(
            full_name="Synthetic requester",
            email=f"requester-{suffix}@example.test",
            phone="9876543210",
            password_hash="unused",
            role="requester",
        )
        coordinators = [
            User(
                full_name="Synthetic coordinator",
                email=f"coordinator-{suffix}-{index}@example.test",
                phone="9876543210",
                password_hash="unused",
                role="coordinator",
            )
            for index in range(2)
        ]
        donors = [
            User(
                full_name="Synthetic donor",
                email=f"donor-{suffix}-{index}@example.test",
                phone="9876543210",
                password_hash="unused",
                role="donor",
            )
            for index in range(donor_count)
        ]
        db.add_all([requester, *coordinators, *donors])
        db.flush()
        request = BloodRequest(
            request_code=f"TEST-{suffix}",
            requester_id=requester.id,
            patient_reference="Synthetic concurrency test",
            blood_group="O+",
            units_required=units_required,
            units_confirmed=0,
            hospital_name="Synthetic hospital",
            hospital_address="1 Test Road",
            city="Bengaluru",
            required_at=now + timedelta(days=1),
            urgency="Normal",
            contact_name="Synthetic contact",
            contact_phone="9876543210",
            status=status,
        )
        db.add(request)
        db.flush()
        for donor in donors:
            db.add(DonorProfile(
                user_id=donor.id,
                blood_group="O+",
                city="Bengaluru",
                available=True,
                verified=True,
            ))
            db.add(DonorMatch(
                request_id=request.id,
                donor_id=donor.id,
                compatibility_type="exact",
                match_score=100,
                status="matched",
            ))
        tokens = {}
        users = [*coordinators, *donors]
        for user in users:
            session_id = str(uuid4())
            db.add(BrowserSession(
                id=session_id,
                user_id=user.id,
                expires_at=now + timedelta(hours=1),
            ))
            tokens[user.email] = create_access_token(user.email, session_id=session_id)
        db.commit()
        return {
            "request_id": request.id,
            "requester_id": requester.id,
            "coordinator_ids": [coordinator.id for coordinator in coordinators],
            "coordinator_tokens": [tokens[coordinator.email] for coordinator in coordinators],
            "donor_ids": [donor.id for donor in donors],
            "donor_tokens": [tokens[donor.email] for donor in donors],
        }


def _install_delay_trigger(engine, trigger_name, function_name, table_name, event):
    with engine.begin() as connection:
        connection.execute(text(
            f"CREATE FUNCTION {function_name}() RETURNS trigger LANGUAGE plpgsql "
            "AS $$ BEGIN PERFORM pg_sleep(0.3); RETURN NEW; END $$"
        ))
        connection.execute(text(
            f"CREATE TRIGGER {trigger_name} BEFORE {event} ON {table_name} "
            f"FOR EACH ROW EXECUTE FUNCTION {function_name}()"
        ))


def _remove_delay_trigger(engine, trigger_name, function_name, table_name):
    with engine.begin() as connection:
        connection.execute(text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"))
        connection.execute(text(f"DROP FUNCTION IF EXISTS {function_name}()"))


def _parallel_requests(requests):
    barrier = Barrier(len(requests))

    def send(request):
        barrier.wait(timeout=5)
        client = TestClient(app, raise_server_exceptions=False)
        return request(client)

    with ThreadPoolExecutor(max_workers=len(requests)) as pool:
        futures = [pool.submit(send, request) for request in requests]
        return [future.result(timeout=15) for future in futures]


def _audit_rows(session_factory, assignment_id, actions):
    with session_factory() as db:
        return db.query(AuditLog).filter(
            AuditLog.entity_type == "volunteer_assignment",
            AuditLog.entity_id == str(assignment_id),
            AuditLog.action.in_(actions),
        ).all()


def test_concurrent_identical_volunteer_transition_is_applied_once(postgres_sessions):
    session_factory, engine = postgres_sessions
    seeded = _seed_assignment(session_factory)
    trigger = ("delay_volunteer_transition", "delay_volunteer_transition_fn")
    _install_delay_trigger(engine, *trigger, "volunteer_assignments", "UPDATE OF status")
    try:
        responses = _parallel_requests([
            lambda client: client.patch(
                f"/api/volunteers/me/assignments/{seeded['assignment_id']}/status?status=accepted",
                headers={"Authorization": f"Bearer {seeded['tokens']['volunteer']}"},
            ),
            lambda client: client.patch(
                f"/api/volunteers/me/assignments/{seeded['assignment_id']}/status?status=accepted",
                headers={"Authorization": f"Bearer {seeded['tokens']['volunteer']}"},
            ),
        ])
    finally:
        _remove_delay_trigger(engine, *trigger, "volunteer_assignments")

    assert sorted(response.status_code for response in responses) == [200, 409]
    audits = _audit_rows(session_factory, seeded["assignment_id"], {"assignment_status_changed"})
    assert len(audits) == 1
    assert json.loads(audits[0].metadata_json) == {
        "from_status": "assigned",
        "to_status": "accepted",
    }
    with session_factory() as db:
        assignment = db.get(VolunteerAssignment, seeded["assignment_id"])
        assert assignment.status == "accepted"


def test_coordinator_cancellation_and_volunteer_transition_are_serialized(postgres_sessions):
    session_factory, engine = postgres_sessions
    seeded = _seed_assignment(session_factory)
    trigger = ("delay_volunteer_cancel_race", "delay_volunteer_cancel_race_fn")
    _install_delay_trigger(engine, *trigger, "volunteer_assignments", "UPDATE OF status")
    try:
        responses = _parallel_requests([
            lambda client: client.patch(
                f"/api/volunteers/me/assignments/{seeded['assignment_id']}/status?status=accepted",
                headers={"Authorization": f"Bearer {seeded['tokens']['volunteer']}"},
            ),
            lambda client: client.patch(
                f"/api/volunteers/{seeded['assignment_id']}/cancel",
                headers={"Authorization": f"Bearer {seeded['tokens']['coordinator']}"},
            ),
        ])
    finally:
        _remove_delay_trigger(engine, *trigger, "volunteer_assignments")

    assert responses[1].status_code == 200
    assert responses[0].status_code in {200, 409}
    audits = _audit_rows(
        session_factory,
        seeded["assignment_id"],
        {"assignment_status_changed", "assignment_cancelled"},
    )
    audit_metadata = [json.loads(audit.metadata_json) for audit in sorted(audits, key=lambda item: item.id)]
    if responses[0].status_code == 200:
        assert audit_metadata == [
            {"from_status": "assigned", "to_status": "accepted"},
            {"request_id": seeded["request_id"], "from_status": "accepted", "to_status": "cancelled"},
        ]
    else:
        assert audit_metadata == [
            {"request_id": seeded["request_id"], "from_status": "assigned", "to_status": "cancelled"},
        ]
    with session_factory() as db:
        assignment = db.get(VolunteerAssignment, seeded["assignment_id"])
        assert assignment.status == "cancelled"


def test_concurrent_duplicate_assignment_creation_is_rejected(postgres_sessions):
    session_factory, engine = postgres_sessions
    seeded = _seed_assignment(session_factory, status="completed")
    trigger = ("delay_duplicate_assignment_insert", "delay_duplicate_assignment_insert_fn")
    _install_delay_trigger(engine, *trigger, "volunteer_assignments", "INSERT")
    payload = {"volunteer_id": seeded["volunteer_id"]}
    headers = {"Authorization": f"Bearer {seeded['tokens']['coordinator']}"}
    try:
        responses = _parallel_requests([
            lambda client: client.post(
                f"/api/volunteers/requests/{seeded['request_id']}/assignments",
                headers=headers,
                json=payload,
            ),
            lambda client: client.post(
                f"/api/volunteers/requests/{seeded['request_id']}/assignments",
                headers=headers,
                json=payload,
            ),
        ])
    finally:
        _remove_delay_trigger(engine, *trigger, "volunteer_assignments")

    assert sorted(response.status_code for response in responses) == [201, 409]
    with session_factory() as db:
        active_assignments = db.query(VolunteerAssignment).filter(
            VolunteerAssignment.request_id == seeded["request_id"],
            VolunteerAssignment.volunteer_id == seeded["volunteer_id"],
            VolunteerAssignment.status.notin_(["completed", "cancelled"]),
        ).count()
        assert active_assignments == 1


def test_concurrent_donor_acceptance_and_coordinator_verification(postgres_sessions):
    session_factory, _engine = postgres_sessions
    seeded = _seed_request_workflow(session_factory, donor_count=2)
    request_id = seeded["request_id"]
    donor_accepts = _parallel_requests([
        lambda client, token=token: client.post(
            f"/api/requests/{request_id}/accept",
            headers={"Authorization": f"Bearer {token}"},
        )
        for token in seeded["donor_tokens"]
    ])
    assert sorted(response.status_code for response in donor_accepts) == [200, 200], [
        response.text for response in donor_accepts
    ]
    with session_factory() as db:
        assert db.query(DonorResponse).filter(DonorResponse.request_id == request_id).count() == 2

    verification = _seed_request_workflow(session_factory, status="submitted")
    verify_responses = _parallel_requests([
        lambda client, token=token: client.post(
            f"/api/requests/{verification['request_id']}/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        for token in verification["coordinator_tokens"]
    ])
    assert sorted(response.status_code for response in verify_responses) == [200, 409]


def test_duplicate_donor_acceptance_is_rejected(postgres_sessions):
    session_factory, _engine = postgres_sessions
    seeded = _seed_request_workflow(session_factory)
    request_id = seeded["request_id"]
    token = seeded["donor_tokens"][0]
    responses = _parallel_requests([
        lambda client: client.post(
            f"/api/requests/{request_id}/accept",
            headers={"Authorization": f"Bearer {token}"},
        )
        for _ in range(2)
    ])
    assert sorted(response.status_code for response in responses) == [200, 409]
    with session_factory() as db:
        assert db.query(DonorResponse).filter(
            DonorResponse.request_id == request_id,
            DonorResponse.donor_id == seeded["donor_ids"][0],
        ).count() == 1


def test_confirmation_unit_cap_and_withdrawal_are_transactionally_serialized(postgres_sessions):
    session_factory, engine = postgres_sessions
    seeded = _seed_request_workflow(session_factory, status="coordinating", donor_count=2)
    with session_factory() as db:
        db.add_all([
            DonorResponse(request_id=seeded["request_id"], donor_id=donor_id, response="accepted")
            for donor_id in seeded["donor_ids"]
        ])
        db.commit()

    def confirm_request(client, donor_id):
        return client.post(
            f"/api/requests/{seeded['request_id']}/donations/{donor_id}/confirm",
            headers={"Authorization": f"Bearer {seeded['coordinator_tokens'][0]}"},
            json={"units_confirmed": 1, "verification_source": "coordinator_confirmed"},
        )

    confirmations = _parallel_requests([
        lambda client: confirm_request(client, donor_id)
        for donor_id in seeded["donor_ids"]
    ])
    assert sorted(response.status_code for response in confirmations) == [200, 409]
    with session_factory() as db:
        request = db.get(BloodRequest, seeded["request_id"])
        assert request.units_confirmed == 1
        assert db.query(DonationConfirmation).filter(
            DonationConfirmation.request_id == seeded["request_id"],
        ).count() == 1

    withdraw = _seed_request_workflow(session_factory, status="coordinating")
    donor_id = withdraw["donor_ids"][0]
    with session_factory() as db:
        db.add(DonorResponse(request_id=withdraw["request_id"], donor_id=donor_id, response="accepted"))
        db.commit()
    race_responses = _parallel_requests([
        lambda client: client.post(
            f"/api/requests/{withdraw['request_id']}/withdraw",
            headers={"Authorization": f"Bearer {withdraw['donor_tokens'][0]}"},
        ),
        lambda client: client.post(
            f"/api/requests/{withdraw['request_id']}/donations/{donor_id}/confirm",
            headers={"Authorization": f"Bearer {withdraw['coordinator_tokens'][0]}"},
            json={"units_confirmed": 1, "verification_source": "coordinator_confirmed"},
        ),
    ])
    assert sorted(response.status_code for response in race_responses) == [200, 409]
    with session_factory() as db:
        response = db.query(DonorResponse).filter(
            DonorResponse.request_id == withdraw["request_id"],
            DonorResponse.donor_id == donor_id,
        ).one()
        confirmations = db.query(DonationConfirmation).filter(
            DonationConfirmation.request_id == withdraw["request_id"],
            DonationConfirmation.donor_id == donor_id,
        ).count()
        assert (response.response, confirmations) in {("withdrawn", 0), ("accepted", 1)}


def test_failed_confirmation_audit_rolls_back_and_can_retry(postgres_sessions):
    session_factory, engine = postgres_sessions
    seeded = _seed_request_workflow(session_factory, status="coordinating")
    donor_id = seeded["donor_ids"][0]
    with session_factory() as db:
        db.add(DonorResponse(request_id=seeded["request_id"], donor_id=donor_id, response="accepted"))
        db.commit()

    with engine.begin() as connection:
        connection.execute(text(
            "CREATE FUNCTION fail_test_donation_audit() RETURNS trigger LANGUAGE plpgsql "
            "AS $$ BEGIN IF NEW.action = 'donation_confirmed' THEN "
            "RAISE EXCEPTION 'injected test failure'; END IF; RETURN NEW; END $$"
        ))
        connection.execute(text(
            "CREATE TRIGGER fail_test_donation_audit BEFORE INSERT ON audit_logs "
            "FOR EACH ROW EXECUTE FUNCTION fail_test_donation_audit()"
        ))
    try:
        failing_client = TestClient(app, raise_server_exceptions=False)
        failed = failing_client.post(
            f"/api/requests/{seeded['request_id']}/donations/{donor_id}/confirm",
            headers={"Authorization": f"Bearer {seeded['coordinator_tokens'][0]}"},
            json={"units_confirmed": 1, "verification_source": "coordinator_confirmed"},
        )
        assert failed.status_code == 500
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TRIGGER IF EXISTS fail_test_donation_audit ON audit_logs"))
            connection.execute(text("DROP FUNCTION IF EXISTS fail_test_donation_audit()"))

    with session_factory() as db:
        request = db.get(BloodRequest, seeded["request_id"])
        assert request.status == "coordinating"
        assert request.units_confirmed == 0
        assert db.query(DonationConfirmation).filter(
            DonationConfirmation.request_id == seeded["request_id"],
        ).count() == 0
        assert db.query(AuditLog).filter(
            AuditLog.action == "donation_confirmed",
            AuditLog.entity_id == str(seeded["request_id"]),
        ).count() == 0
        assert db.query(Notification).filter(
            Notification.type == "donation_confirmed",
            Notification.related_entity_id == seeded["request_id"],
        ).count() == 0

    retry = TestClient(app).post(
        f"/api/requests/{seeded['request_id']}/donations/{donor_id}/confirm",
        headers={"Authorization": f"Bearer {seeded['coordinator_tokens'][0]}"},
        json={"units_confirmed": 1, "verification_source": "coordinator_confirmed"},
    )
    assert retry.status_code == 200


def test_expiration_job_is_idempotent_across_process_restarts(postgres_sessions):
    session_factory, _engine = postgres_sessions
    seeded = _seed_request_workflow(session_factory, status="coordinating")
    with session_factory() as db:
        request = db.get(BloodRequest, seeded["request_id"])
        request.required_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        due_request_count = db.query(BloodRequest).filter(
            BloodRequest.status.in_({"submitted", "verified", "coordinating", "partially_fulfilled"}),
            BloodRequest.required_at <= datetime.now(timezone.utc),
        ).count()

    environment = os.environ.copy()
    environment["DATABASE_URL"] = POSTGRES_TEST_URL
    environment["APP_ENV"] = "development"
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    first = subprocess.run(
        [sys.executable, "-m", "app.cli.expire_requests"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    second = subprocess.run(
        [sys.executable, "-m", "app.cli.expire_requests"],
        cwd=backend_dir,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    assert first.stdout.strip() == f"Expired {due_request_count} request(s)."
    assert second.stdout.strip() == "Expired 0 request(s)."
    with session_factory() as db:
        request = db.get(BloodRequest, seeded["request_id"])
        assert request.status == "expired"
        assert db.query(AuditLog).filter(
            AuditLog.action == "request_expired",
            AuditLog.entity_id == str(request.id),
        ).count() == 1
