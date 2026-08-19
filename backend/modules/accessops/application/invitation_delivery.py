from __future__ import annotations

from dataclasses import dataclass
from html import escape
from urllib.parse import quote

from django.utils import timezone

from modules.accessops.models import AccessInvitation
from modules.tenant.application.email_delivery import (
    resolve_transactional_brand,
    send_transactional_email,
)
from modules.tenant.models import Company, CompanyBrandProfile


@dataclass(frozen=True, slots=True)
class InvitationBrandContext:
    product_name: str
    sender_name: str
    tagline: str
    support_email: str
    logo_url: str
    primary_color: str
    powered_by_build360: bool
    acceptance_base_url: str
    white_label_enabled: bool


def resolve_invitation_brand(company: Company) -> InvitationBrandContext:
    brand = resolve_transactional_brand(company)
    profile = CompanyBrandProfile.objects.filter(company=company).first()
    tagline = (
        profile.tagline.strip()
        if brand.white_label_enabled and profile is not None and profile.tagline.strip()
        else "Construction Operating System"
    )
    return InvitationBrandContext(
        product_name=brand.product_name,
        sender_name=brand.sender_name,
        tagline=tagline,
        support_email=brand.support_email,
        logo_url=brand.logo_url,
        primary_color=brand.primary_color,
        powered_by_build360=brand.powered_by_build360,
        acceptance_base_url=brand.public_web_url,
        white_label_enabled=brand.white_label_enabled,
    )


def invitation_acceptance_url(*, company: Company, raw_token: str) -> str:
    brand = resolve_invitation_brand(company)
    return f"{brand.acceptance_base_url}/accept-invitation?token={quote(raw_token, safe='')}"


def _brand_snapshot(brand: InvitationBrandContext) -> dict[str, object]:
    return {
        "product_name": brand.product_name,
        "sender_name": brand.sender_name,
        "tagline": brand.tagline,
        "support_email": brand.support_email,
        "logo_url": brand.logo_url,
        "primary_color": brand.primary_color,
        "powered_by_build360": brand.powered_by_build360,
        "acceptance_base_url": brand.acceptance_base_url,
        "white_label_enabled": brand.white_label_enabled,
    }


def _invitation_copy(*, invitation: AccessInvitation, brand: InvitationBrandContext, acceptance_url: str) -> tuple[str, str, str]:
    invitee_name = invitation.display_name.strip() or invitation.email
    company_name = invitation.company.display_name
    subject = f"You're invited to {brand.product_name}"
    text = (
        f"Hi {invitee_name},\n\n"
        f"You've been invited to join {company_name}.\n\n"
        f"Accept invitation: {acceptance_url}\n\n"
        f"This one-time invitation expires {invitation.expires_at.isoformat()}.\n"
    )
    if brand.powered_by_build360 and brand.product_name != "MPSqre Build360":
        text += "\nPowered by MPSqre Build360\n"

    button_color = brand.primary_color if brand.primary_color.startswith("#") else "#174D3C"
    powered_by = (
        '<p style="margin-top:24px;color:#667085;font-size:12px">Powered by MPSqre Build360</p>'
        if brand.powered_by_build360 and brand.product_name != "MPSqre Build360"
        else ""
    )
    logo = (
        f'<img src="{escape(brand.logo_url, quote=True)}" alt="{escape(brand.product_name)}" style="max-height:52px;max-width:220px;margin-bottom:18px" />'
        if brand.logo_url
        else ""
    )
    html = f"""
<!doctype html>
<html><body style="margin:0;background:#f6f8f7;font-family:Arial,sans-serif;color:#17202a">
  <div style="max-width:620px;margin:0 auto;padding:32px 18px">
    <div style="background:#fff;border:1px solid #e4e7ec;border-radius:18px;padding:32px">
      {logo}
      <div style="font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:{button_color}">{escape(brand.product_name)}</div>
      <h1 style="font-size:24px;line-height:1.3;margin:12px 0 10px">You're invited to {escape(company_name)}</h1>
      <p style="line-height:1.65;color:#475467">Hi {escape(invitee_name)}, you've been invited to join the {escape(company_name)} workspace.</p>
      <p style="margin:28px 0"><a href="{escape(acceptance_url, quote=True)}" style="background:{button_color};color:#fff;text-decoration:none;font-weight:700;padding:13px 20px;border-radius:10px;display:inline-block">Accept invitation</a></p>
      <p style="line-height:1.6;color:#667085;font-size:13px">This is a one-time link and expires on {escape(invitation.expires_at.isoformat())}.</p>
      {powered_by}
    </div>
  </div>
</body></html>
""".strip()
    return subject, text, html


def deliver_invitation_email(*, invitation: AccessInvitation, raw_token: str) -> dict[str, object]:
    brand = resolve_invitation_brand(invitation.company)
    acceptance_url = invitation_acceptance_url(company=invitation.company, raw_token=raw_token)
    snapshot = _brand_snapshot(brand)
    now = timezone.now()
    invitation.delivery_attempted_at = now
    invitation.delivery_brand_snapshot = snapshot
    invitation.delivery_error_code = ""

    subject, text, html = _invitation_copy(
        invitation=invitation,
        brand=brand,
        acceptance_url=acceptance_url,
    )
    delivery = send_transactional_email(
        company=invitation.company,
        subject=subject,
        text=text,
        html=html,
        to=[invitation.email],
        sender_name=brand.sender_name,
        reply_to=[brand.support_email] if brand.support_email else None,
    )
    if delivery.status == "LOCAL_PREVIEW":
        status = AccessInvitation.DeliveryStatus.LOCAL_PREVIEW
    elif delivery.status == "SENT":
        status = AccessInvitation.DeliveryStatus.SENT
    else:
        status = AccessInvitation.DeliveryStatus.FAILED
        invitation.delivery_error_code = delivery.error_code

    invitation.delivery_status_code = status
    invitation.delivery_sent_at = now if status in {
        AccessInvitation.DeliveryStatus.SENT,
        AccessInvitation.DeliveryStatus.LOCAL_PREVIEW,
    } else None
    invitation.version += 1
    invitation.save(
        update_fields=[
            "delivery_status_code",
            "delivery_attempted_at",
            "delivery_sent_at",
            "delivery_error_code",
            "delivery_brand_snapshot",
            "version",
            "updated_at",
        ]
    )
    return {
        "status": invitation.delivery_status_code,
        "attempted_at": invitation.delivery_attempted_at.isoformat() if invitation.delivery_attempted_at else None,
        "sent_at": invitation.delivery_sent_at.isoformat() if invitation.delivery_sent_at else None,
        "error_code": invitation.delivery_error_code,
        "brand_name": brand.product_name,
        "sender_name": brand.sender_name,
        "acceptance_url": acceptance_url,
        "powered_by_build360": brand.powered_by_build360,
        "delivery_route": delivery.route,
    }


def preview_invitation(raw_token: str) -> dict[str, object] | None:
    import hashlib

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    invitation = (
        AccessInvitation.objects.select_related("company")
        .filter(token_hash=token_hash)
        .first()
    )
    now = timezone.now()
    if (
        invitation is None
        or invitation.revoked_at is not None
        or invitation.accepted_at is not None
        or invitation.expires_at <= now
    ):
        return None
    brand = resolve_invitation_brand(invitation.company)
    return {
        "valid": True,
        "company_name": invitation.company.display_name,
        "invitee_name": invitation.display_name,
        "expires_at": invitation.expires_at.isoformat(),
        "branding": {
            "product_name": brand.product_name,
            "tagline": brand.tagline,
            "primary_color": brand.primary_color,
            "powered_by_build360": brand.powered_by_build360,
            "white_label_enabled": brand.white_label_enabled,
        },
    }
