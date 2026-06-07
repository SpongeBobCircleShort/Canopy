import secrets

from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories import (
    create_invite,
    create_organization,
    get_organization,
    get_org_webhooks,
    list_invites_for_org,
    list_organizations,
    revoke_invite,
    set_org_webhooks,
)
from app.schemas import NotificationSettings, NotificationSettingsUpdate, Organization, OrganizationCreate, OrganizationInvite, OrganizationInviteCreate, OrganizationInviteCreated
from app.security import get_current_user, org_id_for_user, require_admin

router = APIRouter()


def _require_same_org_admin(org_id: int, current_user: dict) -> None:
    if current_user.get("role") != "admin" or org_id_for_user(current_user) != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")


@router.get("", response_model=list[Organization])
def list_orgs(current_user: dict = Depends(get_current_user)) -> list[Organization]:
    if current_user.get("role") == "admin":
        return list_organizations()
    org_id = current_user.get("organization_id")
    organization = get_organization(org_id) if org_id is not None else None
    return [organization] if organization else []


@router.post("", response_model=Organization, status_code=status.HTTP_201_CREATED)
def create_org(payload: OrganizationCreate, _current_user: dict = Depends(require_admin)) -> Organization:
    return create_organization(payload)


@router.get("/{org_id}", response_model=Organization)
def get_org(org_id: int, current_user: dict = Depends(get_current_user)) -> Organization:
    if current_user.get("role") != "admin" and current_user.get("organization_id") != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    organization = get_organization(org_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return organization


@router.post("/{org_id}/invites", response_model=OrganizationInviteCreated, status_code=status.HTTP_201_CREATED)
def create_org_invite(
    org_id: int,
    payload: OrganizationInviteCreate,
    current_user: dict = Depends(require_admin),
) -> OrganizationInviteCreated:
    _require_same_org_admin(org_id, current_user)
    return create_invite(
        org_id,
        payload,
        invited_by_user_id=current_user["id"],
        token=secrets.token_urlsafe(32),
    )


@router.get("/{org_id}/invites", response_model=list[OrganizationInvite])
def list_org_invites(org_id: int, current_user: dict = Depends(require_admin)) -> list[OrganizationInvite]:
    _require_same_org_admin(org_id, current_user)
    return list_invites_for_org(org_id)


@router.get("/{org_id}/notification-settings", response_model=NotificationSettings)
def get_notification_settings(org_id: int, current_user: dict = Depends(require_admin)) -> NotificationSettings:
    _require_same_org_admin(org_id, current_user)
    return NotificationSettings(webhooks=get_org_webhooks(org_id))


@router.patch("/{org_id}/notification-settings", response_model=NotificationSettings)
def update_notification_settings(
    org_id: int,
    payload: NotificationSettingsUpdate,
    current_user: dict = Depends(require_admin),
) -> NotificationSettings:
    _require_same_org_admin(org_id, current_user)
    invalid = [url for url in payload.webhooks if url and not url.startswith(("http://", "https://"))]
    if invalid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid webhook URLs: {invalid}")
    webhooks = set_org_webhooks(org_id, payload.webhooks)
    return NotificationSettings(webhooks=webhooks)


@router.post("/{org_id}/invites/{invite_id}/revoke", response_model=OrganizationInvite)
def revoke_org_invite(
    org_id: int,
    invite_id: int,
    current_user: dict = Depends(require_admin),
) -> OrganizationInvite:
    _require_same_org_admin(org_id, current_user)
    invite = revoke_invite(invite_id, org_id)
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
    return invite
