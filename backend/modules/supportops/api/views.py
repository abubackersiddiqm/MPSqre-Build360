from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from modules.supportops.application.selectors import support_overview
from modules.supportops.application.services import (
    add_interaction,
    create_article,
    create_change,
    create_feedback,
    create_improvement,
    create_problem,
    create_ticket,
    refresh_sla,
    seed_defaults,
    transition_article,
    transition_change,
    transition_improvement,
    transition_problem,
    transition_ticket,
)
from modules.supportops.models import (
    ChangeRequest,
    CustomerFeedback,
    ImprovementItem,
    KnowledgeArticle,
    ProblemRecord,
    ServiceCatalogItem,
    SupportTicket,
)
from modules.tenant.api.base import TenantScopedAPIView

from .serializers import (
    ArticleCreateSerializer,
    ArticleTransitionSerializer,
    ChangeCreateSerializer,
    ChangeTransitionSerializer,
    FeedbackCreateSerializer,
    ImprovementCreateSerializer,
    ImprovementTransitionSerializer,
    InteractionCreateSerializer,
    ProblemCreateSerializer,
    ProblemTransitionSerializer,
    TicketCreateSerializer,
    TicketTransitionSerializer,
)


def correlation_id(request: Request) -> uuid.UUID:
    return getattr(request, "request_id", uuid.uuid4())


def translate(error: DjangoValidationError) -> ValidationError:
    if hasattr(error, "message_dict"):
        return ValidationError(error.message_dict)
    return ValidationError(getattr(error, "messages", [str(error)]))


def find(model, *, company, public_id, message):
    item = model.objects.filter(company=company, public_id=public_id).first()
    if item is None:
        raise NotFound(message)
    return item


class SupportAPIView(TenantScopedAPIView):
    required_permission = "support.view"

    def initial(self, request: Request, *args: object, **kwargs: object) -> None:
        super().initial(request, *args, **kwargs)
        self.tenant_context.require(self.required_permission)

    @property
    def actor(self) -> uuid.UUID:
        return self.tenant_context.principal.user.public_id


class OverviewView(SupportAPIView):
    def get(self, request: Request) -> Response:
        seed_defaults(self.tenant_context.company)
        refresh_sla(self.tenant_context.company)
        payload = support_overview(self.tenant_context.company)
        payload["capabilities"] = {
            "can_manage": self.tenant_context.can("support.manage"),
            "can_ticket": self.tenant_context.can("support.ticket"),
            "can_resolve": self.tenant_context.can("support.resolve"),
            "can_sla": self.tenant_context.can("support.sla"),
            "can_problem": self.tenant_context.can("support.problem"),
            "can_change": self.tenant_context.can("support.change"),
            "can_knowledge": self.tenant_context.can("support.knowledge"),
            "can_improve": self.tenant_context.can("support.improve"),
            "can_export": self.tenant_context.can("support.export"),
        }
        return Response(payload)


class TicketCreateView(SupportAPIView):
    required_permission = "support.ticket"

    def post(self, request: Request) -> Response:
        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        catalog_id = data.pop("catalog_item_public_id", None)
        catalog_item = find(
            ServiceCatalogItem, company=self.tenant_context.company, public_id=catalog_id,
            message="Service catalog item not found"
        ) if catalog_id else None
        try:
            ticket = create_ticket(
                company=self.tenant_context.company, catalog_item=catalog_item,
                actor_public_id=self.actor, correlation_id=correlation_id(request), **data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(ticket.public_id), "code": ticket.code, "status": ticket.status_code, "version": ticket.version}, status=201)


class TicketTransitionView(SupportAPIView):
    required_permission = "support.resolve"

    def post(self, request: Request, ticket_id: uuid.UUID) -> Response:
        ticket = find(SupportTicket, company=self.tenant_context.company, public_id=ticket_id, message="Support ticket not found")
        serializer = TicketTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ticket = transition_ticket(
                ticket=ticket, actor_public_id=self.actor, correlation_id=correlation_id(request),
                **serializer.validated_data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(ticket.public_id), "status": ticket.status_code, "version": ticket.version})


class InteractionCreateView(SupportAPIView):
    required_permission = "support.ticket"

    def post(self, request: Request) -> Response:
        serializer = InteractionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        ticket_id = data.pop("ticket_public_id")
        ticket = find(SupportTicket, company=self.tenant_context.company, public_id=ticket_id, message="Support ticket not found")
        try:
            interaction = add_interaction(
                company=self.tenant_context.company, ticket=ticket, actor_public_id=self.actor,
                correlation_id=correlation_id(request), **data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(interaction.public_id), "ticket": ticket.code}, status=201)


class ProblemCreateView(SupportAPIView):
    required_permission = "support.problem"

    def post(self, request: Request) -> Response:
        serializer = ProblemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        ticket_id = data.pop("source_ticket_public_id", None)
        data["source_ticket"] = find(
            SupportTicket, company=self.tenant_context.company, public_id=ticket_id, message="Support ticket not found"
        ) if ticket_id else None
        try:
            problem = create_problem(
                company=self.tenant_context.company, actor_public_id=self.actor,
                correlation_id=correlation_id(request), **data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(problem.public_id), "code": problem.code, "version": problem.version}, status=201)


class ProblemTransitionView(SupportAPIView):
    required_permission = "support.problem"

    def post(self, request: Request, problem_id: uuid.UUID) -> Response:
        problem = find(ProblemRecord, company=self.tenant_context.company, public_id=problem_id, message="Problem record not found")
        serializer = ProblemTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            problem = transition_problem(
                problem=problem, actor_public_id=self.actor, correlation_id=correlation_id(request),
                **serializer.validated_data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(problem.public_id), "status": problem.status_code, "version": problem.version})


class ChangeCreateView(SupportAPIView):
    required_permission = "support.change"

    def post(self, request: Request) -> Response:
        serializer = ChangeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        ticket_id = data.pop("source_ticket_public_id", None)
        problem_id = data.pop("problem_public_id", None)
        data["source_ticket"] = find(
            SupportTicket, company=self.tenant_context.company, public_id=ticket_id, message="Support ticket not found"
        ) if ticket_id else None
        data["problem"] = find(
            ProblemRecord, company=self.tenant_context.company, public_id=problem_id, message="Problem record not found"
        ) if problem_id else None
        try:
            change = create_change(
                company=self.tenant_context.company, actor_public_id=self.actor,
                correlation_id=correlation_id(request), **data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(change.public_id), "code": change.code, "version": change.version}, status=201)


class ChangeTransitionView(SupportAPIView):
    required_permission = "support.change"

    def post(self, request: Request, change_id: uuid.UUID) -> Response:
        change = find(ChangeRequest, company=self.tenant_context.company, public_id=change_id, message="Change request not found")
        serializer = ChangeTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data["status_code"] == "APPROVED" and not self.tenant_context.can("support.manage"):
            raise ValidationError("support.manage permission is required to approve a change request.")
        try:
            change = transition_change(
                change=change, actor_public_id=self.actor, correlation_id=correlation_id(request),
                **serializer.validated_data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(change.public_id), "status": change.status_code, "version": change.version})


class ArticleCreateView(SupportAPIView):
    required_permission = "support.knowledge"

    def post(self, request: Request) -> Response:
        serializer = ArticleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            article = create_article(
                company=self.tenant_context.company, actor_public_id=self.actor,
                correlation_id=correlation_id(request), **serializer.validated_data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(article.public_id), "code": article.code, "version": article.version}, status=201)


class ArticleTransitionView(SupportAPIView):
    required_permission = "support.knowledge"

    def post(self, request: Request, article_id: uuid.UUID) -> Response:
        article = find(KnowledgeArticle, company=self.tenant_context.company, public_id=article_id, message="Knowledge article not found")
        serializer = ArticleTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            article = transition_article(
                article=article, actor_public_id=self.actor, correlation_id=correlation_id(request),
                **serializer.validated_data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(article.public_id), "status": article.status_code, "version": article.version})


class FeedbackCreateView(SupportAPIView):
    required_permission = "support.ticket"

    def post(self, request: Request) -> Response:
        serializer = FeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        ticket_id = data.pop("ticket_public_id")
        ticket = find(SupportTicket, company=self.tenant_context.company, public_id=ticket_id, message="Support ticket not found")
        data.setdefault("submitted_at", timezone.now())
        try:
            feedback = create_feedback(
                company=self.tenant_context.company, ticket=ticket, actor_public_id=self.actor,
                correlation_id=correlation_id(request), **data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(feedback.public_id), "rating": feedback.rating}, status=201)


class ImprovementCreateView(SupportAPIView):
    required_permission = "support.improve"

    def post(self, request: Request) -> Response:
        serializer = ImprovementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        ticket_id = data.pop("source_ticket_public_id", None)
        problem_id = data.pop("source_problem_public_id", None)
        feedback_id = data.pop("source_feedback_public_id", None)
        data["source_ticket"] = find(
            SupportTicket, company=self.tenant_context.company, public_id=ticket_id, message="Support ticket not found"
        ) if ticket_id else None
        data["source_problem"] = find(
            ProblemRecord, company=self.tenant_context.company, public_id=problem_id, message="Problem record not found"
        ) if problem_id else None
        data["source_feedback"] = find(
            CustomerFeedback, company=self.tenant_context.company, public_id=feedback_id, message="Customer feedback not found"
        ) if feedback_id else None
        try:
            item = create_improvement(
                company=self.tenant_context.company, actor_public_id=self.actor,
                correlation_id=correlation_id(request), **data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "code": item.code, "version": item.version}, status=201)


class ImprovementTransitionView(SupportAPIView):
    required_permission = "support.improve"

    def post(self, request: Request, improvement_id: uuid.UUID) -> Response:
        item = find(ImprovementItem, company=self.tenant_context.company, public_id=improvement_id, message="Improvement item not found")
        serializer = ImprovementTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = transition_improvement(
                item=item, actor_public_id=self.actor, correlation_id=correlation_id(request),
                **serializer.validated_data
            )
        except DjangoValidationError as error:
            raise translate(error) from error
        return Response({"public_id": str(item.public_id), "status": item.status_code, "version": item.version})


class SLARefreshView(SupportAPIView):
    required_permission = "support.sla"

    def post(self, request: Request) -> Response:
        return Response(refresh_sla(self.tenant_context.company))
