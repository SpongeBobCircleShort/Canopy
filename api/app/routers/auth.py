import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories import (
    accept_invite,
    create_organization,
    create_user,
    get_invite_by_token,
    get_organization,
    get_user_by_email,
)
from app.schemas import AuthResponse, InviteStatus, LoginRequest, OrganizationCreate, SignupRequest, UserProfile
from app.security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter()


def _auth_response(user: dict) -> AuthResponse:
    token = create_access_token(
        {
            "sub": str(user["id"]),
            "user_id": user["id"],
            "email": user["email"],
            "role": user.get("role", "member"),
            "org_id": user.get("organization_id"),
        }
    )
    return AuthResponse(access_token=token)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    user = get_user_by_email(payload.email)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _auth_response(user)


def _validate_invite_signup(payload: SignupRequest):
    if payload.organization_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="organization_name cannot be used with invite_token")
    invite = get_invite_by_token(payload.invite_token or "")
    if invite is None or invite.status != InviteStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite is not valid")
    if invite.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite has expired")
    if invite.email.lower() != payload.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invite email does not match signup email")
    return invite


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest) -> AuthResponse:
    if get_user_by_email(payload.email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    invite = None
    if payload.invite_token:
        invite = _validate_invite_signup(payload)
        org_id = invite.org_id
        role = invite.role
    else:
        if not payload.organization_name or not payload.organization_name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="organization_name is required without invite_token")
        organization = create_organization(OrganizationCreate(name=payload.organization_name.strip()))
        org_id = organization.id
        role = "admin"

    try:
        user = create_user(
            payload.name,
            payload.email,
            hash_password(payload.password),
            org_id=org_id,
            role=role,
        )
        if invite is not None:
            accept_invite(invite)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc
    except Exception as exc:
        if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from exc
        raise
    return _auth_response(user)


@router.get("/me", response_model=UserProfile)
def me(current_user: dict = Depends(get_current_user)) -> UserProfile:
    org_id = current_user.get("organization_id")
    organization = get_organization(org_id) if org_id is not None else None
    return UserProfile(
        id=current_user["id"],
        name=current_user["name"],
        email=current_user["email"],
        role=current_user.get("role", "member"),
        org_id=org_id,
        organization=organization,
    )
