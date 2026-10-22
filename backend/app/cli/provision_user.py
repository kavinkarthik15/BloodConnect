import getpass

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User
from app.schemas.auth import UserRegister
from app.services.auth_service import get_password_hash


def provision_privileged_user(
    db: Session,
    *,
    full_name: str,
    email: str,
    phone: str,
    password: str,
    role: str,
    college_org: str | None = None,
    nss_unit: str | None = None,
) -> User:
    if role not in {"coordinator", "volunteer"}:
        raise ValueError("Only coordinator and volunteer roles can be provisioned.")
    validated = UserRegister(
        full_name=full_name,
        email=email,
        phone=phone,
        password=password,
        role=role,
        college_org=college_org,
        nss_unit=nss_unit,
    )
    if db.query(User).filter(User.email == str(validated.email).lower()).first():
        raise ValueError("An account with that email already exists.")
    user = User(
        full_name=validated.full_name,
        email=str(validated.email).lower(),
        phone=validated.phone,
        password_hash=get_password_hash(validated.password),
        role=role,
        college_org=validated.college_org,
        nss_unit=validated.nss_unit,
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def main() -> None:
    role = input("Role (coordinator/volunteer): ").strip().lower()
    full_name = input("Full name: ").strip()
    email = input("Email: ").strip()
    phone = input("Phone: ").strip()
    college_org = input("College/organization (optional): ").strip() or None
    nss_unit = input("NSS unit (optional): ").strip() or None
    password = getpass.getpass("Temporary password (not echoed): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    db = SessionLocal()
    try:
        provision_privileged_user(
            db,
            full_name=full_name,
            email=email,
            phone=phone,
            password=password,
            role=role,
            college_org=college_org,
            nss_unit=nss_unit,
        )
    except ValueError as exc:
        db.rollback()
        raise SystemExit("Account provisioning failed due to invalid input or an existing account.") from None
    finally:
        db.close()
    print("Privileged account provisioned.")


if __name__ == "__main__":
    main()
