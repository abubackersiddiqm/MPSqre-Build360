from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from modules.ai.application.services import active_policy
from modules.ai.models import AICitation, AIEntityInsight, AIInteraction, AIModelPolicy
from modules.crm.models import Activity, Lead, PipelineStage, StageHistory
from modules.platform.actors import RequestActor
from modules.platform.audit import AuditRecord, append_audit
from modules.platform.events import EventRecord, append_event
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.models import Company

INSIGHT_CODE = "CRM_LEAD_INTELLIGENCE"
SUBJECT_TYPE = "crm.lead"


def _digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _feature_allowed(company: Company, code: str) -> bool:
    return feature_enabled(company=company, code=code)


def feature_access(company: Company) -> dict[str, bool]:
    return {
        "summary": _feature_allowed(company, "crm.ai_summary"),
        "recommendation": _feature_allowed(company, "crm.ai_recommendation"),
    }


def _require_any_feature(company: Company) -> dict[str, bool]:
    access = feature_access(company)
    if not any(access.values()):
        raise PermissionDenied("CRM AI intelligence is not included in the active subscription")
    return access


def _lead(company: Company, public_id: uuid.UUID) -> Lead:
    lead = (
        Lead.objects.select_related("stage", "customer", "primary_contact")
        .filter(company=company, public_id=public_id)
        .first()
    )
    if lead is None:
        raise ValidationError("CRM lead was not found")
    return lead


def _meaningful_context(*, company: Company, lead: Lead, max_records: int = 50) -> tuple[dict[str, Any], list[Activity], list[StageHistory]]:
    activity_scope = Q(lead=lead)
    if lead.primary_contact_id:
        # Relationship 360 keeps the person as the master. Include authorized
        # contact-level history so the AI call prep does not ignore earlier or
        # cross-lead interactions with the same person.
        activity_scope |= Q(contact=lead.primary_contact)
    activities = list(
        Activity.objects.filter(company=company)
        .filter(activity_scope)
        .distinct()
        .order_by("-created_at")[:max_records]
    )
    histories = list(
        StageHistory.objects.filter(
            company=company,
            entity_type=PipelineStage.EntityType.LEAD,
            entity_public_id=lead.public_id,
        )
        .order_by("-changed_at")[:20]
    )
    context = {
        "lead": {
            "public_id": str(lead.public_id),
            "version": lead.version,
            "title": lead.title,
            "description": lead.description,
            "source_code": lead.source_code,
            "stage": {
                "code": lead.stage.code,
                "name": lead.stage.name,
                "outcome": lead.stage.outcome,
                "allows_conversion": lead.stage.allows_conversion,
            },
            "estimated_value": str(lead.estimated_value) if lead.estimated_value is not None else None,
            "currency": lead.currency,
            "next_follow_up_at": lead.next_follow_up_at.isoformat() if lead.next_follow_up_at else None,
            "qualified_at": lead.qualified_at.isoformat() if lead.qualified_at else None,
            "disqualified_at": lead.disqualified_at.isoformat() if lead.disqualified_at else None,
            "converted_at": lead.converted_at.isoformat() if lead.converted_at else None,
            "created_at": lead.created_at.isoformat(),
            "primary_contact": {
                "public_id": str(lead.primary_contact.public_id),
                "display_name": " ".join(
                    part for part in [lead.primary_contact.first_name, lead.primary_contact.last_name] if part
                ).strip(),
                "preferred_channel_code": lead.primary_contact.preferred_channel_code,
            } if lead.primary_contact_id else None,
        },
        "activities": [
            {
                "public_id": str(item.public_id),
                "version": item.version,
                "activity_type": item.activity_type,
                "status": item.status,
                "priority": item.priority,
                "subject": item.subject,
                "notes": item.notes,
                "scheduled_for": item.scheduled_for.isoformat() if item.scheduled_for else None,
                "follow_up_at": item.follow_up_at.isoformat() if item.follow_up_at else None,
                "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
                "created_at": item.created_at.isoformat(),
            }
            for item in activities
        ],
        "stage_history": [
            {
                "public_id": str(item.public_id),
                "from_stage": item.from_stage_code,
                "to_stage": item.to_stage_code,
                "reason_code": item.reason_code,
                "entity_version": item.entity_version,
                "changed_at": item.changed_at.isoformat(),
            }
            for item in histories
        ],
    }
    return context, activities, histories


def source_digest(*, company: Company, lead: Lead) -> str:
    context, _, _ = _meaningful_context(company=company, lead=lead)
    return _digest(context)


def _age_label(value) -> str:
    if not value:
        return "not recorded"
    delta = timezone.now() - value
    if delta.total_seconds() < 3600:
        return "within the last hour"
    if delta.days <= 0:
        return "today"
    if delta.days == 1:
        return "yesterday"
    return f"{delta.days} days ago"


def _summary(*, lead: Lead, activities: list[Activity]) -> str:
    now = timezone.now()
    completed = [item for item in activities if item.status == Activity.Status.COMPLETED]
    planned = [item for item in activities if item.status == Activity.Status.PLANNED]
    overdue = [item for item in planned if item.scheduled_for and item.scheduled_for < now]
    latest = completed[0] if completed else (activities[0] if activities else None)

    parts = [
        f"This lead is currently in {lead.stage.name} ({lead.stage.outcome})",
        f"and came from {lead.source_code or 'an unspecified source'}.",
    ]
    if lead.estimated_value is not None:
        parts.append(f"Estimated value is {lead.currency} {lead.estimated_value}.")
    if latest:
        latest_time = latest.occurred_at or latest.completed_at or latest.created_at
        parts.append(
            f"The latest recorded interaction was {latest.activity_type.replace('_', ' ')} {_age_label(latest_time)}: {latest.subject}."
        )
        if latest.notes:
            clean = " ".join(latest.notes.split())
            parts.append(f"Latest context: {clean[:280]}.")
    else:
        parts.append("No lead interaction has been logged yet.")
    if lead.next_follow_up_at:
        state = "overdue" if lead.next_follow_up_at < now else "scheduled"
        parts.append(
            f"The lead-level follow-up is {state} for {lead.next_follow_up_at.astimezone().strftime('%d %b %Y, %I:%M %p')}."
        )
    if overdue:
        parts.append(f"There are {len(overdue)} overdue planned CRM activit{'y' if len(overdue) == 1 else 'ies'}.")
    return " ".join(parts)


def _recommendation(*, lead: Lead, activities: list[Activity]) -> dict[str, Any]:
    now = timezone.now()
    planned = [item for item in activities if item.status == Activity.Status.PLANNED]
    overdue = sorted(
        [item for item in planned if item.scheduled_for and item.scheduled_for < now],
        key=lambda item: item.scheduled_for,
    )
    upcoming = sorted(
        [item for item in planned if item.scheduled_for and item.scheduled_for >= now],
        key=lambda item: item.scheduled_for,
    )
    completed = [item for item in activities if item.status == Activity.Status.COMPLETED]
    latest_completed = completed[0] if completed else None

    if lead.stage.outcome == PipelineStage.Outcome.CONVERTED or lead.converted_at:
        return {
            "action_code": "NO_SALES_ACTION",
            "label": "Continue from the converted opportunity/project workflow",
            "reason": "The CRM lead is already converted; duplicate sales follow-up should not be created from AI advice.",
            "suggested_due_at": None,
            "confidence": "0.9900",
        }
    if lead.stage.outcome == PipelineStage.Outcome.DISQUALIFIED or lead.disqualified_at:
        return {
            "action_code": "REVIEW_CLOSURE",
            "label": "Review closure evidence only if the lead should be reopened",
            "reason": "The lead is disqualified. AI advice must not reopen or change the pipeline stage automatically.",
            "suggested_due_at": None,
            "confidence": "0.9800",
        }
    if overdue:
        item = overdue[0]
        return {
            "action_code": "COMPLETE_OVERDUE_ACTIVITY",
            "label": f"Complete overdue {item.activity_type.replace('_', ' ')}",
            "reason": f"The planned CRM activity “{item.subject}” is overdue and is the clearest recorded next commitment.",
            "suggested_due_at": now.isoformat(),
            "confidence": "0.9700",
        }
    if lead.next_follow_up_at and lead.next_follow_up_at < now:
        return {
            "action_code": "FOLLOW_UP_NOW",
            "label": "Follow up with the lead now",
            "reason": "The lead-level next follow-up time has passed and no newer completed action supersedes it.",
            "suggested_due_at": now.isoformat(),
            "confidence": "0.9500",
        }
    if not activities:
        due = now + (timedelta(hours=2) if lead.source_code == "META_ADS" else timedelta(days=1))
        return {
            "action_code": "FIRST_CONTACT",
            "label": "Make the first customer contact",
            "reason": (
                "The lead has no logged interactions yet."
                + (" Meta Ads leads should be contacted quickly while intent is fresh." if lead.source_code == "META_ADS" else "")
            ),
            "suggested_due_at": due.isoformat(),
            "confidence": "0.9200",
        }
    if upcoming:
        item = upcoming[0]
        return {
            "action_code": "COMPLETE_SCHEDULED_ACTIVITY",
            "label": f"Complete scheduled {item.activity_type.replace('_', ' ')}",
            "reason": f"The log book already contains the planned commitment “{item.subject}”; AI should not invent a competing action.",
            "suggested_due_at": item.scheduled_for.isoformat(),
            "confidence": "0.9700",
        }
    if lead.stage.allows_conversion and latest_completed:
        return {
            "action_code": "REVIEW_CONVERSION_READINESS",
            "label": "Review conversion readiness",
            "reason": "The current stage allows conversion and recent lead history exists, so the next decision should be evidence-based qualification/conversion review.",
            "suggested_due_at": (now + timedelta(days=1)).isoformat(),
            "confidence": "0.8800",
        }
    if not lead.next_follow_up_at:
        return {
            "action_code": "SET_NEXT_FOLLOW_UP",
            "label": "Set the next follow-up",
            "reason": "Recent history exists but the lead has no lead-level next follow-up date.",
            "suggested_due_at": (now + timedelta(days=1)).isoformat(),
            "confidence": "0.8600",
        }
    return {
        "action_code": "CONTINUE_FOLLOW_UP",
        "label": "Continue the recorded follow-up plan",
        "reason": "A future lead-level follow-up already exists; the safest next action is to honor that recorded commitment.",
        "suggested_due_at": lead.next_follow_up_at.isoformat(),
        "confidence": "0.9000",
    }


def _recommendation_tanglish(recommendation: dict[str, Any] | None) -> tuple[str, str]:
    if not recommendation:
        return "", ""
    code = str(recommendation.get("action_code") or "")
    mapping = {
        "NO_SALES_ACTION": (
            "Converted workflow-la continue pannunga",
            "Lead already convert aagirukku; duplicate sales follow-up create panna vendam.",
        ),
        "REVIEW_CLOSURE": (
            "Closure evidence-a review pannunga",
            "Lead disqualify aagirukku. Reopen panna valid reason/evidence irukka nu mattum review pannunga.",
        ),
        "COMPLETE_OVERDUE_ACTIVITY": (
            "Overdue activity-a first complete pannunga",
            "Already promise pannina or schedule pannina action overdue aagirukku; adha mudhala close pannradhu safest next step.",
        ),
        "FOLLOW_UP_NOW": (
            "Customer-ku ippo follow-up pannunga",
            "Recorded follow-up time pass aagirukku; newer completed action edhuvum adha replace pannala.",
        ),
        "FIRST_CONTACT": (
            "Customer-ku first contact pannunga",
            "Innum interaction log aagala; requirement-a understand panna first call/message start pannunga.",
        ),
        "COMPLETE_SCHEDULED_ACTIVITY": (
            "Already schedule pannina activity-a complete pannunga",
            "CRM-la next commitment already irukku; adhukku opposite-a pudhu action invent panna vendam.",
        ),
        "REVIEW_CONVERSION_READINESS": (
            "Conversion-ku ready-a irukka nu review pannunga",
            "Current stage conversion allow pannudhu; recent history base-la next business decision-a review pannunga.",
        ),
        "SET_NEXT_FOLLOW_UP": (
            "Next follow-up time set pannunga",
            "Recent history irukku, aana clear next follow-up date/time set aagala.",
        ),
        "CONTINUE_FOLLOW_UP": (
            "Recorded follow-up plan-a continue pannunga",
            "Future follow-up already irukku; recorded customer commitment-a honor pannradhu safest next step.",
        ),
    }
    return mapping.get(code, (
        "Next customer step-a confirm pannunga",
        "Latest CRM history base-la next clear action-a customer-kooda confirm pannunga.",
    ))


def _clean(value: str | None, limit: int = 320) -> str:
    return " ".join((value or "").split())[:limit]


def _person_name(lead: Lead) -> str:
    if not lead.primary_contact_id:
        return "the customer"
    display = " ".join(
        part for part in [lead.primary_contact.first_name, lead.primary_contact.last_name] if part
    ).strip()
    return display or "the customer"


def _latest_completed(activities: list[Activity]) -> Activity | None:
    return next((item for item in activities if item.status == Activity.Status.COMPLETED), None)


def _summary_tanglish(*, lead: Lead, activities: list[Activity]) -> str:
    now = timezone.now()
    latest = _latest_completed(activities) or (activities[0] if activities else None)
    parts = [
        f"Indha lead ippo {lead.stage.name} stage-la irukku.",
        f"Source {lead.source_code or 'record pannala'}.",
    ]
    if lead.estimated_value is not None:
        parts.append(f"Estimated value {lead.currency} {lead.estimated_value}.")
    if latest:
        latest_time = latest.occurred_at or latest.completed_at or latest.created_at
        parts.append(
            f"Latest-a {_age_label(latest_time)} {latest.activity_type.replace('_', ' ')} interaction record aagirukku: {latest.subject}."
        )
        if latest.notes:
            parts.append(f"Latest context: {_clean(latest.notes, 220)}.")
    else:
        parts.append("Innum customer interaction log pannala.")
    if lead.next_follow_up_at:
        state = "overdue" if lead.next_follow_up_at < now else "scheduled"
        parts.append(
            f"Next follow-up {state}; {lead.next_follow_up_at.astimezone().strftime('%d %b %Y, %I:%M %p')} ku plan pannirukku."
        )
    else:
        parts.append("Next follow-up time set pannala.")
    return " ".join(parts)


def _attention_signals(*, lead: Lead, activities: list[Activity]) -> list[dict[str, str]]:
    now = timezone.now()
    signals: list[dict[str, str]] = []
    planned = [item for item in activities if item.status == Activity.Status.PLANNED]
    overdue = [item for item in planned if item.scheduled_for and item.scheduled_for < now]
    latest = _latest_completed(activities)

    if overdue:
        signals.append({
            "code": "OVERDUE_COMMITMENT",
            "severity": "high",
            "label": "Overdue customer commitment",
            "reason": f"{len(overdue)} planned CRM action(s) are overdue.",
            "label_tanglish": "Customer commitment overdue aagirukku",
            "reason_tanglish": f"{len(overdue)} planned CRM action overdue aagirukku; first idha close pannunga.",
        })
    if lead.next_follow_up_at and lead.next_follow_up_at < now:
        signals.append({
            "code": "LEAD_FOLLOW_UP_OVERDUE",
            "severity": "high",
            "label": "Lead follow-up is overdue",
            "reason": "The recorded lead-level follow-up time has already passed.",
            "label_tanglish": "Lead follow-up overdue aagirukku",
            "reason_tanglish": "Record pannina follow-up time already pass aagirukku; delay pannama follow-up pannunga.",
        })
    if latest and latest.outcome_code in {"callback_requested", "follow_up_required"}:
        signals.append({
            "code": "CUSTOMER_REQUESTED_NEXT_STEP",
            "severity": "high",
            "label": "Customer requested a next step",
            "reason": f"Latest recorded outcome is {latest.outcome_code.replace('_', ' ')}.",
            "label_tanglish": "Customer next step request pannirukkaru",
            "reason_tanglish": f"Latest outcome {latest.outcome_code.replace('_', ' ')}; promised next step-a miss panna vendam.",
        })
    if latest and latest.outcome_code in {"wrong_number", "bounced"}:
        signals.append({
            "code": "CONTACT_CHANNEL_ISSUE",
            "severity": "high",
            "label": "Contact channel needs attention",
            "reason": f"Latest recorded outcome is {latest.outcome_code.replace('_', ' ')}.",
            "label_tanglish": "Contact channel-a check pannunga",
            "reason_tanglish": f"Latest outcome {latest.outcome_code.replace('_', ' ')}; correct phone/email irukka nu verify pannunga.",
        })
    if not activities:
        signals.append({
            "code": "NO_INTERACTION",
            "severity": "medium",
            "label": "No customer interaction logged",
            "reason": "There is no recorded conversation yet for this lead relationship.",
            "label_tanglish": "Innum customer interaction log aagala",
            "reason_tanglish": "Indha relationship-ku conversation record illa; first contact pannitu outcome save pannunga.",
        })
    elif latest:
        latest_time = latest.occurred_at or latest.completed_at or latest.created_at
        if latest_time and (now - latest_time).days >= 7:
            signals.append({
                "code": "RELATIONSHIP_STALE",
                "severity": "medium",
                "label": "Relationship may be going cold",
                "reason": f"The latest completed interaction was {_age_label(latest_time)}.",
                "label_tanglish": "Relationship cold aaga chance irukku",
                "reason_tanglish": f"Latest completed interaction {_age_label(latest_time)}; customer-a reconnect pannunga.",
            })
    if not lead.next_follow_up_at and not any(item.follow_up_at or item.scheduled_for for item in planned):
        signals.append({
            "code": "NO_NEXT_ACTION",
            "severity": "medium",
            "label": "No next action is scheduled",
            "reason": "The relationship can be forgotten unless a clear next step is recorded.",
            "label_tanglish": "Next action schedule pannala",
            "reason_tanglish": "Clear next step record pannala na relationship miss aaga chance irukku; follow-up schedule pannunga.",
        })
    return signals[:5]


def _data_gaps(*, lead: Lead) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if lead.estimated_value is None:
        gaps.append({
            "code": "VALUE_MISSING",
            "label": "Estimated value is not set",
            "label_tanglish": "Estimated value set pannala",
        })
    if not lead.source_code:
        gaps.append({
            "code": "SOURCE_MISSING",
            "label": "Lead source is not recorded",
            "label_tanglish": "Lead source record pannala",
        })
    if not lead.next_follow_up_at and not lead.converted_at and not lead.disqualified_at:
        gaps.append({
            "code": "FOLLOW_UP_MISSING",
            "label": "Next follow-up is not set",
            "label_tanglish": "Next follow-up set pannala",
        })
    if not _clean(lead.description):
        gaps.append({
            "code": "REQUIREMENT_CONTEXT_MISSING",
            "label": "Requirement/context is very limited",
            "label_tanglish": "Customer requirement/context romba kammiya irukku",
        })
    return gaps[:4]


def _call_preparation(*, lead: Lead, activities: list[Activity], recommendation: dict[str, Any] | None) -> dict[str, Any]:
    person = _person_name(lead)
    latest = _latest_completed(activities)
    latest_context = _clean(latest.notes if latest else "", 280)
    action_label = str((recommendation or {}).get("label") or "Confirm the next customer step")

    if not activities:
        objective_en = f"Understand {person}'s requirement for {lead.title} and agree one clear next step."
        objective_tanglish = f"{person} oda {lead.title} requirement-a clear-a understand panni, call mudiyumbodhu oru next step confirm pannunga."
        opening_en = f"Hi {person}, I’m calling regarding your {lead.title} enquiry. I’d like to understand what you need and make sure we take the right next step."
        opening_tanglish = f"Hi {person}, unga {lead.title} enquiry pathi call pannuren. Unga exact requirement enna nu understand panni, correct next step decide pannalaam."
    else:
        objective_en = f"Use the latest CRM history to move {lead.title} forward without repeating questions already answered."
        objective_tanglish = f"Already CRM-la irukkura latest history-a use panni, same question repeat pannama {lead.title} next step-ku move pannunga."
        opening_en = f"Hi {person}, I’m following up on {lead.title}. I reviewed our last update and wanted to check what has changed and what you need from us next."
        opening_tanglish = f"Hi {person}, {lead.title} pathi follow-up panna call pannuren. Last update check panniten; ippo edhavathu change irukka, enga side-la next enna support venum nu pesalaam."

    talking_en = [
        f"Confirm the current requirement and decision status for {lead.title}.",
        f"Keep the conversation focused on the recorded next action: {action_label}.",
        "Agree who will do what next and by when before ending the call.",
    ]
    talking_tanglish = [
        f"{lead.title} requirement ippo same-a irukka, decision status enna nu confirm pannunga.",
        f"Recorded next action '{action_label}' mela conversation-a focus pannunga.",
        "Call mudiyuradhukku munnaadi next yaar enna pannuvanga, eppo pannuvanga nu clear-a confirm pannunga.",
    ]
    if latest_context:
        talking_en.insert(1, f"Use the latest recorded customer context: {latest_context}")
        talking_tanglish.insert(1, f"Latest record-la irukkura customer context-a reference pannunga: {latest_context}")

    questions_en = [
        "Has anything changed in your requirement since our last conversation?",
        "What is the main thing holding back the next decision right now?",
        "What would you need from us to comfortably move to the next step?",
    ]
    questions_tanglish = [
        "Last time pesinadhukku apram requirement-la edhavathu change irukka?",
        "Ippo next decision edukka main-a enna blocker irukku?",
        "Next step-ku comfortable-a move aaga enga side-la enna support venum?",
    ]

    return {
        "english": {
            "objective": objective_en,
            "opening_line": opening_en,
            "talking_points": talking_en[:4],
            "questions": questions_en,
            "closing_line": "Before we close, can we agree the exact next step and a date/time for it?",
        },
        "tanglish": {
            "objective": objective_tanglish,
            "opening_line": opening_tanglish,
            "talking_points": talking_tanglish[:4],
            "questions": questions_tanglish,
            "closing_line": "Call close pannradhukku munnaadi exact next step enna, adha eppo pannalam nu confirm pannalama?",
        },
        "grounded_context": latest_context or "No recent customer note is available; do not invent customer needs or commitments.",
        "safety_note": "Use this as a conversation aid. Verify price, scope, delivery dates and commitments from approved business records before promising anything.",
    }


def _message_drafts(*, lead: Lead, recommendation: dict[str, Any] | None) -> dict[str, Any]:
    person = _person_name(lead)
    action_label = str((recommendation or {}).get("label") or "confirm the next step")
    return {
        "whatsapp": {
            "english": f"Hi {person}, following up on your {lead.title} enquiry. I wanted to check the current status and {action_label.lower()}. Please let me know a convenient time to connect.",
            "tanglish": f"Hi {person}, unga {lead.title} enquiry pathi follow-up pannuren. Current status check panni {action_label.lower()} pathi pesanum. Ungalukku convenient time sollunga, connect pannalaam.",
        },
        "email": {
            "subject": f"Follow-up: {lead.title}",
            "english": f"Hi {person},\n\nI’m following up on {lead.title}. I’d like to confirm the current status and the next step from both sides. Please share a convenient time to connect.\n\nThank you.",
            "tanglish": f"Hi {person},\n\n{lead.title} pathi follow-up pannuren. Current status-um, rendu side next step enna nu confirm pannalaam. Ungalukku convenient time share pannunga, connect pannalaam.\n\nThank you.",
        },
    }


def _output(*, lead: Lead, activities: list[Activity], access: dict[str, bool]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "advisory_only": True,
        "generated_by": "local_grounded",
        "copilot_version": "sales_copilot_v20u",
    }
    recommendation = _recommendation(lead=lead, activities=activities) if access["recommendation"] else None
    if recommendation:
        label_tanglish, reason_tanglish = _recommendation_tanglish(recommendation)
        recommendation = {
            **recommendation,
            "label_tanglish": label_tanglish,
            "reason_tanglish": reason_tanglish,
        }
    if access["summary"]:
        payload["summary"] = _summary(lead=lead, activities=activities)
        payload["summary_tanglish"] = _summary_tanglish(lead=lead, activities=activities)
    else:
        payload["summary"] = None
        payload["summary_tanglish"] = None
    payload["recommended_next_action"] = recommendation
    if access["recommendation"]:
        payload["call_preparation"] = _call_preparation(lead=lead, activities=activities, recommendation=recommendation)
        payload["message_drafts"] = _message_drafts(lead=lead, recommendation=recommendation)
        payload["attention_signals"] = _attention_signals(lead=lead, activities=activities)
        payload["data_gaps"] = _data_gaps(lead=lead)
    else:
        payload["call_preparation"] = None
        payload["message_drafts"] = None
        payload["attention_signals"] = []
        payload["data_gaps"] = []
    return payload


def _effective(insight: AIEntityInsight | None) -> dict[str, Any] | None:
    if insight is None:
        return None
    generated = dict(insight.output_payload or {})
    override = dict(insight.override_payload or {})
    effective = dict(generated)
    if override:
        if "summary" in override:
            effective["summary"] = override["summary"]
        if any(key in override for key in ("action_label", "action_reason", "suggested_due_at")):
            action = dict(generated.get("recommended_next_action") or {})
            if "action_label" in override:
                action["label"] = override["action_label"]
                action["action_code"] = "HUMAN_OVERRIDE"
            if "action_reason" in override:
                action["reason"] = override["action_reason"]
            if "suggested_due_at" in override:
                action["suggested_due_at"] = override["suggested_due_at"]
            effective["recommended_next_action"] = action or None
    return effective


def _citation_payload(interaction: AIInteraction | None) -> list[dict[str, Any]]:
    if interaction is None:
        return []
    return [
        {
            "public_id": str(item.public_id),
            "rank": item.rank,
            "source_type": item.source_type,
            "source_public_id": str(item.source_public_id),
            "source_label": item.source_label,
            "excerpt": item.excerpt,
            "authorization_basis": item.authorization_basis,
        }
        for item in interaction.citations.all().order_by("rank")
    ]


def state(*, company: Company, lead_public_id: uuid.UUID) -> dict[str, Any]:
    access = _require_any_feature(company)
    lead = _lead(company, lead_public_id)
    digest = source_digest(company=company, lead=lead)
    insight = (
        AIEntityInsight.objects.select_related("interaction")
        .prefetch_related("interaction__citations")
        .filter(
            company=company,
            subject_type=SUBJECT_TYPE,
            subject_public_id=lead.public_id,
            insight_code=INSIGHT_CODE,
        )
        .first()
    )
    return {
        "lead_public_id": str(lead.public_id),
        "feature_access": access,
        "exists": insight is not None,
        "stale": insight is None or insight.source_digest != digest,
        "generated_at": insight.generated_at if insight else None,
        "source_digest": digest,
        "interaction_public_id": str(insight.interaction.public_id) if insight else None,
        "generated": dict(insight.output_payload or {}) if insight else None,
        "effective": _effective(insight),
        "override": dict(insight.override_payload or {}) if insight else {},
        "override_active": bool(insight and insight.override_payload),
        "overridden_at": insight.overridden_at if insight else None,
        "citations": _citation_payload(insight.interaction if insight else None),
        "version": insight.version if insight else None,
        "advisory_notice": "AI Sales Copilot is grounded decision support only. It can prepare call talking points and message drafts, but it cannot change pipeline stage, send messages, reveal contacts, or create activities automatically.",
    }


def _record(
    *,
    actor: RequestActor,
    company: Company,
    action: str,
    entity_public_id: uuid.UUID,
    version: int,
    payload: dict[str, Any],
) -> None:
    append_audit(
        AuditRecord(
            action=action,
            entity_type="ai_entity_insight",
            entity_public_id=entity_public_id,
            actor_public_id=actor.user_public_id,
            company_public_id=company.public_id,
            request_id=actor.request_id,
            correlation_id=actor.request_id,
            ip_address=actor.ip_address,
            user_agent=actor.user_agent,
            after=payload,
        )
    )
    append_event(
        EventRecord(
            event_type=action,
            aggregate_type="ai_entity_insight",
            aggregate_public_id=entity_public_id,
            aggregate_version=version,
            company_public_id=company.public_id,
            correlation_id=actor.request_id,
            payload=payload,
        )
    )


@transaction.atomic
def refresh(
    *,
    company: Company,
    actor: RequestActor,
    lead_public_id: uuid.UUID,
) -> dict[str, Any]:
    access = _require_any_feature(company)
    lead = _lead(company, lead_public_id)
    policy = active_policy(
        company=company,
        code=INSIGHT_CODE,
        purpose=AIModelPolicy.Purpose.ASSISTANT,
    )
    if policy.provider.adapter_code != "local_grounded":
        raise ValidationError(
            "CRM Lead Intelligence external provider execution is not enabled in this version"
        )
    if not settings.AI_LOCAL_ADAPTER_ENABLED:
        raise ValidationError("The local governed AI adapter is disabled")

    context, activities, histories = _meaningful_context(
        company=company,
        lead=lead,
        max_records=policy.max_context_records,
    )
    digest = _digest(context)

    insight = (
        AIEntityInsight.objects.select_for_update()
        .select_related("interaction")
        .filter(
            company=company,
            subject_type=SUBJECT_TYPE,
            subject_public_id=lead.public_id,
            insight_code=INSIGHT_CODE,
        )
        .first()
    )
    if insight and insight.source_digest == digest and insight.interaction.status == AIInteraction.Status.COMPLETED:
        return state(company=company, lead_public_id=lead.public_id)

    # AIInteraction.idempotency_key is max_length=120. Use the UUID hex form
    # and a compact namespace while preserving the full 64-char source digest.
    idempotency_key = f"crm-li:{lead.public_id.hex}:{digest}"
    interaction = AIInteraction.objects.filter(
        company=company,
        idempotency_key=idempotency_key,
    ).first()

    if interaction is None:
        payload = _output(lead=lead, activities=activities, access=access)
        response_lines = []
        if payload.get("summary"):
            response_lines.append(f"Summary: {payload['summary']}")
        action = payload.get("recommended_next_action")
        if action:
            response_lines.append(
                f"Recommended next action: {action['label']}. Reason: {action['reason']}"
            )
        call_prep = payload.get("call_preparation") or {}
        english_call = call_prep.get("english") or {}
        if english_call.get("objective"):
            response_lines.append(f"Next call objective: {english_call['objective']}")
        response_text = "\n".join(response_lines)[: policy.max_output_characters]
        confidence_values = [
            Decimal(str(action["confidence"]))
            for action in [payload.get("recommended_next_action")]
            if action and action.get("confidence")
        ]
        confidence = confidence_values[0] if confidence_values else Decimal("0.9000")

        interaction = AIInteraction(
            company=company,
            policy=policy,
            requested_by_public_id=actor.user_public_id,
            membership_public_id=actor.membership_public_id,
            idempotency_key=idempotency_key,
            purpose=AIModelPolicy.Purpose.ASSISTANT,
            prompt_digest=digest,
            prompt_excerpt=f"Grounded CRM lead intelligence for {lead.public_id}",
            status=AIInteraction.Status.COMPLETED,
            response_text=response_text,
            confidence=confidence,
            citations_required=True,
            review_status=AIInteraction.ReviewStatus.NOT_REQUIRED,
            input_metadata={
                "subject_type": SUBJECT_TYPE,
                "subject_public_id": str(lead.public_id),
                "source_digest": digest,
                "activity_count": len(activities),
                "stage_history_count": len(histories),
                "feature_access": access,
            },
            output_metadata={
                **payload,
                "adapter": "local_grounded",
                "cache_semantics": "digest",
            },
            provider_code_snapshot=policy.provider.code,
            model_name_snapshot=policy.model_name,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            version=2,
        )
        interaction.full_clean()
        interaction.save()

        citations: list[AICitation] = [
            AICitation(
                company=company,
                interaction=interaction,
                rank=1,
                source_type="crm.lead",
                source_public_id=lead.public_id,
                source_label=f"Lead · {lead.title}",
                source_version=str(lead.version),
                excerpt=f"Stage={lead.stage.name}; source={lead.source_code or 'unspecified'}; next_follow_up={lead.next_follow_up_at or 'none'}"[:600],
                authorization_basis="crm.lead.read",
                data_classification="internal",
            )
        ]
        rank = 2
        for item in activities[: max(0, policy.max_context_records - 1)]:
            excerpt = (
                f"{item.activity_type} · {item.status} · {item.subject}"
                + (f" · {' '.join(item.notes.split())[:300]}" if item.notes else "")
            )[:600]
            citations.append(
                AICitation(
                    company=company,
                    interaction=interaction,
                    rank=rank,
                    source_type="crm.activity",
                    source_public_id=item.public_id,
                    source_label=f"CRM activity · {item.subject}",
                    source_version=str(item.version),
                    excerpt=excerpt,
                    authorization_basis="crm.activity.read",
                    data_classification="internal",
                )
            )
            rank += 1
        for citation in citations:
            citation.full_clean()
        AICitation.objects.bulk_create(citations)

    output_payload = dict(interaction.output_metadata or {})
    output_payload.pop("adapter", None)
    output_payload.pop("cache_semantics", None)

    if insight is None:
        insight = AIEntityInsight(
            company=company,
            interaction=interaction,
            subject_type=SUBJECT_TYPE,
            subject_public_id=lead.public_id,
            insight_code=INSIGHT_CODE,
            source_digest=digest,
            output_payload=output_payload,
            generated_at=timezone.now(),
        )
    else:
        insight.interaction = interaction
        insight.source_digest = digest
        insight.output_payload = output_payload
        insight.generated_at = timezone.now()
        insight.version += 1
    insight.full_clean()
    insight.save()

    _record(
        actor=actor,
        company=company,
        action="ai.crm_lead.intelligence.refreshed",
        entity_public_id=insight.public_id,
        version=insight.version,
        payload={
            "lead_public_id": str(lead.public_id),
            "interaction_public_id": str(interaction.public_id),
            "source_digest": digest,
            "override_preserved": bool(insight.override_payload),
        },
    )
    return state(company=company, lead_public_id=lead.public_id)


@transaction.atomic
def override(
    *,
    company: Company,
    actor: RequestActor,
    lead_public_id: uuid.UUID,
    summary: str | None = None,
    action_label: str | None = None,
    action_reason: str | None = None,
    suggested_due_at: str | None = None,
    clear_override: bool = False,
) -> dict[str, Any]:
    _require_any_feature(company)
    lead = _lead(company, lead_public_id)
    insight = (
        AIEntityInsight.objects.select_for_update()
        .filter(
            company=company,
            subject_type=SUBJECT_TYPE,
            subject_public_id=lead.public_id,
            insight_code=INSIGHT_CODE,
        )
        .first()
    )
    if insight is None:
        raise ValidationError("Generate CRM Lead Intelligence before applying a human override")

    before = dict(insight.override_payload or {})
    if clear_override:
        insight.override_payload = {}
        insight.overridden_by_public_id = None
        insight.overridden_at = None
    else:
        payload: dict[str, Any] = {}
        if summary is not None and summary.strip():
            payload["summary"] = summary.strip()[:4000]
        if action_label is not None and action_label.strip():
            payload["action_label"] = action_label.strip()[:300]
        if action_reason is not None and action_reason.strip():
            payload["action_reason"] = action_reason.strip()[:1000]
        if suggested_due_at is not None:
            payload["suggested_due_at"] = suggested_due_at
        if not payload:
            raise ValidationError("Provide at least one override value or clear_override=true")
        insight.override_payload = payload
        insight.overridden_by_public_id = actor.user_public_id
        insight.overridden_at = timezone.now()
    insight.version += 1
    insight.full_clean()
    insight.save()

    _record(
        actor=actor,
        company=company,
        action="ai.crm_lead.intelligence.override_changed",
        entity_public_id=insight.public_id,
        version=insight.version,
        payload={
            "lead_public_id": str(lead.public_id),
            "before_override_keys": sorted(before),
            "after_override_keys": sorted((insight.override_payload or {}).keys()),
        },
    )
    return state(company=company, lead_public_id=lead.public_id)
