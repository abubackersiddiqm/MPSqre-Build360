from __future__ import annotations

import re
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from modules.crm.models import (
    Activity,
    Contact,
    CrmAutomationExecution,
    CrmAutomationRule,
    Customer,
    Lead,
    Opportunity,
)
from modules.platform.audit import AuditRecord, append_audit
from modules.subscription.application.feature_control import feature_enabled
from modules.tenant.models import Company, Membership

RULE_CODE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,79}$")
SUPPORTED_ACTION_TYPES = {
    "create_task",
    "schedule_follow_up",
    "add_note",
    "assign_owner",
    "set_lead_follow_up",
}
SUPPORTED_OPERATORS = {
    "eq",
    "neq",
    "in",
    "not_in",
    "contains",
    "gt",
    "gte",
    "lt",
    "lte",
    "is_empty",
    "not_empty",
}


def _clean_rule_code(value: str) -> str:
    code = value.strip().lower().replace(" ", "-")
    if not RULE_CODE_RE.fullmatch(code):
        raise ValidationError("Automation code must start with a letter and contain only lowercase letters, numbers, - or _")
    return code


def validate_condition_tree(value: dict[str, Any] | None) -> dict[str, Any]:
    tree = dict(value or {})
    if not tree:
        return {"mode": "all", "items": []}
    mode = str(tree.get("mode") or "all").lower()
    if mode not in {"all", "any"}:
        raise ValidationError("Automation condition mode must be all or any")
    items = tree.get("items") or []
    if not isinstance(items, list) or len(items) > 20:
        raise ValidationError("Automation supports up to 20 conditions per rule")
    normalized: list[dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            raise ValidationError("Automation conditions must be objects")
        field = str(raw.get("field") or "").strip()
        operator = str(raw.get("operator") or "eq").strip().lower()
        if not field or len(field) > 120:
            raise ValidationError("Automation condition field is required")
        if operator not in SUPPORTED_OPERATORS:
            raise ValidationError(f"Unsupported automation condition operator: {operator}")
        normalized.append({"field": field, "operator": operator, "value": raw.get("value")})
    return {"mode": mode, "items": normalized}


def validate_actions(value: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    actions = list(value or [])
    if not actions or len(actions) > 10:
        raise ValidationError("Automation rules require 1 to 10 actions")
    normalized: list[dict[str, Any]] = []
    for raw in actions:
        if not isinstance(raw, dict):
            raise ValidationError("Automation actions must be objects")
        action_type = str(raw.get("type") or "").strip().lower()
        if action_type not in SUPPORTED_ACTION_TYPES:
            raise ValidationError(f"Unsupported CRM automation action: {action_type}")
        action = dict(raw)
        action["type"] = action_type
        if action_type in {"create_task", "schedule_follow_up", "add_note"}:
            subject = str(action.get("subject") or "").strip()
            if not subject:
                raise ValidationError(f"{action_type} requires a subject")
            action["subject"] = subject[:250]
            action["notes"] = str(action.get("notes") or "").strip()[:4000]
        if action_type in {"create_task", "schedule_follow_up", "set_lead_follow_up"}:
            try:
                due_in_hours = int(action.get("due_in_hours", 24))
            except (TypeError, ValueError) as exc:
                raise ValidationError("due_in_hours must be an integer") from exc
            if due_in_hours < 0 or due_in_hours > 24 * 365:
                raise ValidationError("due_in_hours must be between 0 and 8760")
            action["due_in_hours"] = due_in_hours
        if action_type in {"create_task", "schedule_follow_up"}:
            priority = str(action.get("priority") or Activity.Priority.NORMAL).lower()
            if priority not in Activity.Priority.values:
                raise ValidationError("Automation activity priority is invalid")
            action["priority"] = priority
        if action_type == "assign_owner":
            owner = str(action.get("owner_membership_public_id") or "trigger_actor").strip()
            if owner != "trigger_actor":
                try:
                    uuid.UUID(owner)
                except ValueError as exc:
                    raise ValidationError("assign_owner requires trigger_actor or a membership public ID") from exc
            action["owner_membership_public_id"] = owner
        normalized.append(action)
    return normalized


def create_rule(
    *,
    company: Company,
    code: str,
    name: str,
    trigger_code: str,
    condition_tree: dict[str, Any] | None,
    actions: list[dict[str, Any]] | None,
    description: str = "",
    priority: int = 100,
    stop_on_match: bool = False,
    is_active: bool = True,
) -> CrmAutomationRule:
    if trigger_code not in CrmAutomationRule.TriggerCode.values:
        raise ValidationError("Unsupported CRM automation trigger")
    rule = CrmAutomationRule(
        company=company,
        code=_clean_rule_code(code),
        name=name.strip(),
        description=description.strip(),
        trigger_code=trigger_code,
        condition_tree=validate_condition_tree(condition_tree),
        actions=validate_actions(actions),
        priority=priority,
        stop_on_match=stop_on_match,
        is_active=is_active,
    )
    rule.full_clean()
    rule.save()
    return rule


@transaction.atomic
def update_rule(
    *,
    company: Company,
    public_id: uuid.UUID,
    expected_version: int,
    changes: dict[str, Any],
) -> CrmAutomationRule:
    rule = CrmAutomationRule.objects.select_for_update().filter(company=company, public_id=public_id).first()
    if rule is None:
        raise ValidationError("CRM automation rule was not found")
    if rule.version != expected_version:
        raise ValidationError("CRM automation rule changed; refresh before updating")
    if "name" in changes:
        rule.name = str(changes["name"]).strip()
    if "description" in changes:
        rule.description = str(changes["description"] or "").strip()
    if "trigger_code" in changes:
        trigger = str(changes["trigger_code"])
        if trigger not in CrmAutomationRule.TriggerCode.values:
            raise ValidationError("Unsupported CRM automation trigger")
        rule.trigger_code = trigger
    if "condition_tree" in changes:
        rule.condition_tree = validate_condition_tree(changes["condition_tree"])
    if "actions" in changes:
        rule.actions = validate_actions(changes["actions"])
    if "priority" in changes:
        rule.priority = int(changes["priority"])
    if "stop_on_match" in changes:
        rule.stop_on_match = bool(changes["stop_on_match"])
    if "is_active" in changes:
        rule.is_active = bool(changes["is_active"])
    rule.version += 1
    rule.full_clean()
    rule.save()
    return rule


def _record_snapshot(record: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "public_id": str(record.public_id),
        "version": int(getattr(record, "version", 1) or 1),
    }
    for field in (
        "source_code",
        "currency",
        "status",
        "activity_type",
        "direction",
        "outcome_code",
        "priority",
        "consent_status",
        "preferred_channel_code",
    ):
        if hasattr(record, field):
            payload[field] = getattr(record, field)
    for field in ("estimated_value", "amount"):
        if hasattr(record, field):
            raw = getattr(record, field)
            payload[field] = str(raw) if raw is not None else None
    if hasattr(record, "owner_membership_public_id"):
        owner = record.owner_membership_public_id
        payload["owner_membership_public_id"] = str(owner) if owner else None
    if hasattr(record, "custom_fields"):
        payload["custom_fields"] = dict(record.custom_fields or {})
    stage = getattr(record, "stage", None)
    if stage is not None:
        payload["stage"] = {
            "code": stage.code,
            "name": stage.name,
            "outcome": stage.outcome,
            "pipeline_code": stage.pipeline.code if stage.pipeline else "",
        }
    return payload


def _resolve(payload: dict[str, Any], field: str) -> Any:
    current: Any = payload
    for part in field.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _comparable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        return text.lower()


def _condition_matches(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "is_empty":
        return actual in (None, "", [], {})
    if operator == "not_empty":
        return actual not in (None, "", [], {})
    if operator == "contains":
        if isinstance(actual, (list, tuple, set)):
            return str(expected).lower() in {str(item).lower() for item in actual}
        return str(expected).lower() in str(actual or "").lower()
    if operator in {"in", "not_in"}:
        expected_values = expected if isinstance(expected, list) else [item.strip() for item in str(expected or "").split(",") if item.strip()]
        matched = _comparable(actual) in {_comparable(item) for item in expected_values}
        return matched if operator == "in" else not matched
    left = _comparable(actual)
    right = _comparable(expected)
    if operator == "eq":
        return left == right
    if operator == "neq":
        return left != right
    try:
        if operator == "gt":
            return left > right
        if operator == "gte":
            return left >= right
        if operator == "lt":
            return left < right
        if operator == "lte":
            return left <= right
    except TypeError:
        return False
    return False


def rule_matches(rule: CrmAutomationRule, payload: dict[str, Any]) -> bool:
    tree = validate_condition_tree(rule.condition_tree)
    items = tree["items"]
    if not items:
        return True
    matches = [_condition_matches(_resolve(payload, item["field"]), item["operator"], item.get("value")) for item in items]
    return all(matches) if tree["mode"] == "all" else any(matches)


def _active_membership(company: Company, public_id: uuid.UUID) -> Membership:
    now = timezone.now()
    membership = (
        Membership.objects.filter(
            company=company,
            public_id=public_id,
            effective_from__lte=now,
            suspended_at__isnull=True,
            terminated_at__isnull=True,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gt=now))
        .first()
    )
    if membership is None:
        raise ValidationError("Automation owner membership is not active for this company")
    return membership


def _parent_kwargs(record: Any) -> dict[str, Any]:
    if isinstance(record, Contact):
        return {"contact": record, "customer": record.customer}
    if isinstance(record, Lead):
        return {"lead": record, "contact": record.primary_contact, "customer": record.customer}
    if isinstance(record, Opportunity):
        return {"opportunity": record, "contact": record.primary_contact, "customer": record.customer}
    if isinstance(record, Customer):
        return {"customer": record}
    if isinstance(record, Activity):
        return {
            "customer": record.customer,
            "contact": record.contact,
            "lead": record.lead,
            "opportunity": record.opportunity,
        }
    raise ValidationError("Automation cannot attach an activity to this CRM record type")


def _execute_action(*, company: Company, actor: Any, execution: CrmAutomationExecution, record: Any, action: dict[str, Any]) -> dict[str, Any]:
    action_type = action["type"]
    now = timezone.now()
    if action_type in {"create_task", "schedule_follow_up", "add_note"}:
        from modules.crm.application.services import create_activity

        if action_type == "create_task":
            activity_type = Activity.ActivityType.TASK
            status = Activity.Status.PLANNED
            scheduled_for = now + timedelta(hours=int(action.get("due_in_hours", 24)))
        elif action_type == "schedule_follow_up":
            activity_type = Activity.ActivityType.FOLLOW_UP
            status = Activity.Status.PLANNED
            scheduled_for = now + timedelta(hours=int(action.get("due_in_hours", 24)))
        else:
            activity_type = Activity.ActivityType.NOTE
            status = Activity.Status.COMPLETED
            scheduled_for = None
        activity = create_activity(
            company=company,
            actor=actor,
            activity_type=activity_type,
            subject=action["subject"],
            notes=str(action.get("notes") or ""),
            scheduled_for=scheduled_for,
            status=status,
            priority=str(action.get("priority") or Activity.Priority.NORMAL),
            owner_membership_public_id=getattr(record, "owner_membership_public_id", None) or actor.membership_public_id,
            channel_metadata={
                "automation_generated": True,
                "automation_execution_public_id": str(execution.public_id),
                "automation_rule_public_id": str(execution.rule.public_id),
            },
            **_parent_kwargs(record),
        )
        return {"type": action_type, "activity_public_id": str(activity.public_id)}

    if action_type == "assign_owner":
        if not hasattr(record, "owner_membership_public_id"):
            raise ValidationError("This CRM record type cannot be assigned")
        owner_value = str(action.get("owner_membership_public_id") or "trigger_actor")
        owner_public_id = actor.membership_public_id if owner_value == "trigger_actor" else uuid.UUID(owner_value)
        _active_membership(company, owner_public_id)
        before = str(record.owner_membership_public_id) if record.owner_membership_public_id else None
        record.owner_membership_public_id = owner_public_id
        if hasattr(record, "version"):
            record.version += 1
        record.full_clean()
        update_fields = ["owner_membership_public_id", "updated_at"]
        if hasattr(record, "version"):
            update_fields.append("version")
        record.save(update_fields=update_fields)
        return {"type": action_type, "before": before, "after": str(owner_public_id)}

    if action_type == "set_lead_follow_up":
        if not isinstance(record, Lead):
            raise ValidationError("set_lead_follow_up can only run for lead triggers")
        follow_up_at = now + timedelta(hours=int(action.get("due_in_hours", 24)))
        record.next_follow_up_at = follow_up_at
        record.version += 1
        record.save(update_fields=["next_follow_up_at", "version", "updated_at"])
        return {"type": action_type, "next_follow_up_at": follow_up_at.isoformat()}

    raise ValidationError(f"Unsupported CRM automation action: {action_type}")


def dispatch_automation_event(
    *,
    company: Company,
    actor: Any,
    trigger_code: str,
    record: Any,
    context: dict[str, Any] | None = None,
) -> None:
    """Best-effort, idempotent inline automation.

    Rule failures are evidence, not reasons to roll back the CRM operation that caused the event.
    Actions for a failed rule run inside a savepoint and are rolled back together.
    """
    if trigger_code not in CrmAutomationRule.TriggerCode.values:
        return
    if not feature_enabled(company=company, code="crm.automation"):
        return

    payload = _record_snapshot(record)
    payload.update(dict(context or {}))
    entity_type = record._meta.model_name
    entity_version = int(getattr(record, "version", 1) or 1)
    event_key = f"{trigger_code}:{record.public_id}:v{entity_version}"
    rules = CrmAutomationRule.objects.filter(
        company=company,
        trigger_code=trigger_code,
        is_active=True,
    ).order_by("priority", "pk")

    for rule in rules:
        try:
            execution, created = CrmAutomationExecution.objects.get_or_create(
                company=company,
                rule=rule,
                event_key=event_key,
                defaults={
                    "trigger_code": trigger_code,
                    "entity_type": entity_type,
                    "entity_public_id": record.public_id,
                    "entity_version": entity_version,
                    "status": CrmAutomationExecution.Status.RUNNING,
                    "matched": False,
                    "trigger_payload": payload,
                    "actor_user_public_id": getattr(actor, "user_public_id", None),
                    "actor_membership_public_id": getattr(actor, "membership_public_id", None),
                    "started_at": timezone.now(),
                },
            )
        except IntegrityError:
            continue
        if not created:
            continue

        try:
            matched = rule_matches(rule, payload)
            execution.matched = matched
            if not matched:
                execution.status = CrmAutomationExecution.Status.SKIPPED
                execution.completed_at = timezone.now()
                execution.save(update_fields=["matched", "status", "completed_at", "updated_at"])
                continue

            results: list[dict[str, Any]] = []
            try:
                with transaction.atomic():
                    for action in validate_actions(rule.actions):
                        results.append(_execute_action(company=company, actor=actor, execution=execution, record=record, action=action))
            except Exception as exc:  # rule failure must not fail the originating CRM transaction
                execution.status = CrmAutomationExecution.Status.FAILED
                execution.error_code = exc.__class__.__name__[:80]
                execution.error_message = str(exc)[:1000]
                execution.completed_at = timezone.now()
                execution.save(update_fields=["matched", "status", "error_code", "error_message", "completed_at", "updated_at"])
                continue

            execution.status = CrmAutomationExecution.Status.SUCCEEDED
            execution.action_results = results
            execution.completed_at = timezone.now()
            execution.save(update_fields=["matched", "status", "action_results", "completed_at", "updated_at"])
            CrmAutomationRule.objects.filter(pk=rule.pk).update(last_triggered_at=execution.completed_at)
            append_audit(
                AuditRecord(
                    action="crm.automation.executed",
                    entity_type="crm_automation_rule",
                    entity_public_id=rule.public_id,
                    actor_public_id=getattr(actor, "user_public_id", None),
                    company_public_id=company.public_id,
                    request_id=getattr(actor, "request_id", uuid.uuid4()),
                    correlation_id=getattr(actor, "request_id", uuid.uuid4()),
                    after={
                        "execution_public_id": str(execution.public_id),
                        "trigger_code": trigger_code,
                        "source_entity_public_id": str(record.public_id),
                        "action_count": len(results),
                    },
                )
            )
            if rule.stop_on_match:
                break
        except Exception as exc:
            execution.status = CrmAutomationExecution.Status.FAILED
            execution.error_code = exc.__class__.__name__[:80]
            execution.error_message = str(exc)[:1000]
            execution.completed_at = timezone.now()
            execution.save(update_fields=["status", "error_code", "error_message", "completed_at", "updated_at"])


def rule_payload(rule: CrmAutomationRule) -> dict[str, Any]:
    return {
        "public_id": str(rule.public_id),
        "code": rule.code,
        "name": rule.name,
        "description": rule.description,
        "trigger_code": rule.trigger_code,
        "condition_tree": rule.condition_tree,
        "actions": rule.actions,
        "priority": rule.priority,
        "stop_on_match": rule.stop_on_match,
        "is_active": rule.is_active,
        "last_triggered_at": rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        "version": rule.version,
    }


def execution_payload(execution: CrmAutomationExecution) -> dict[str, Any]:
    return {
        "public_id": str(execution.public_id),
        "rule_public_id": str(execution.rule.public_id),
        "rule_name": execution.rule.name,
        "trigger_code": execution.trigger_code,
        "entity_type": execution.entity_type,
        "entity_public_id": str(execution.entity_public_id),
        "entity_version": execution.entity_version,
        "status": execution.status,
        "matched": execution.matched,
        "action_results": execution.action_results,
        "error_code": execution.error_code,
        "error_message": execution.error_message,
        "started_at": execution.started_at.isoformat(),
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
    }
