from app.db.database import SessionLocal
from app.services.request_expiration_service import expire_due_requests


def main() -> None:
    db = SessionLocal()
    try:
        expired_count = expire_due_requests(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f"Expired {expired_count} request(s).")


if __name__ == "__main__":
    main()
