from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from modules.platform.models import PublicIdModel, TimestampedModel
from modules.tenant.models import Company


def normalize_code(value: str) -> str:
    return value.strip().upper().replace(" ", "_").replace("-", "_")


class LandPolicyVersion(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_acquisition_policies")
    version = models.PositiveIntegerField(default=1)
    status_code = models.CharField(max_length=30, default="DRAFT")
    due_diligence_target_days = models.PositiveIntegerField(default=45)
    approval_alert_days = models.PositiveIntegerField(default=60)
    minimum_margin_percent = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("15.0000"))
    configuration = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    published_by_public_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "landops_policy"
        constraints = [
            models.UniqueConstraint(fields=["company", "version"], name="land_policy_ver_uq"),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gt=models.F("effective_from")),
                name="land_policy_dates_ck",
            ),
            models.CheckConstraint(condition=models.Q(minimum_margin_percent__gte=0), name="land_policy_margin_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="land_policy_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.status_code = normalize_code(self.status_code)


class LandParcel(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_parcels")
    parcel_code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    parcel_type_code = models.CharField(max_length=60, default="FREEHOLD")
    jurisdiction_code = models.CharField(max_length=80, blank=True)
    survey_reference = models.CharField(max_length=160, blank=True)
    title_reference = models.CharField(max_length=160, blank=True)
    address = models.JSONField(default=dict, blank=True)
    gross_area = models.DecimalField(max_digits=18, decimal_places=3)
    usable_area = models.DecimalField(max_digits=18, decimal_places=3, null=True, blank=True)
    area_unit_code = models.CharField(max_length=30, default="SQ_M")
    zoning_code = models.CharField(max_length=80, blank=True)
    current_use_code = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    status_code = models.CharField(max_length=30, default="PROSPECT")
    owner_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "landops_parcel"
        constraints = [
            models.UniqueConstraint(fields=["company", "parcel_code"], name="land_parcel_code_uq"),
            models.CheckConstraint(condition=models.Q(gross_area__gt=0), name="land_parcel_area_ck"),
            models.CheckConstraint(
                condition=models.Q(usable_area__isnull=True) | models.Q(usable_area__gte=0),
                name="land_parcel_usable_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "status_code"], name="land_parcel_status_idx"),
            models.Index(fields=["company", "jurisdiction_code"], name="land_parcel_juris_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.parcel_code = normalize_code(self.parcel_code)
        self.parcel_type_code = normalize_code(self.parcel_type_code)
        self.area_unit_code = normalize_code(self.area_unit_code)
        self.status_code = normalize_code(self.status_code)
        if not isinstance(self.address, dict):
            raise ValidationError({"address": "Parcel address must be a JSON object."})
        if self.usable_area is not None and self.usable_area > self.gross_area:
            raise ValidationError({"usable_area": "Usable area cannot exceed gross area."})
        if self.latitude is not None and not Decimal("-90") <= self.latitude <= Decimal("90"):
            raise ValidationError({"latitude": "Latitude must be between -90 and 90."})
        if self.longitude is not None and not Decimal("-180") <= self.longitude <= Decimal("180"):
            raise ValidationError({"longitude": "Longitude must be between -180 and 180."})


class OwnershipInterest(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_ownership_interests")
    parcel = models.ForeignKey(LandParcel, on_delete=models.PROTECT, related_name="ownership_interests")
    owner_name = models.CharField(max_length=240)
    owner_type_code = models.CharField(max_length=60, default="INDIVIDUAL")
    share_percent = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("100.0000"))
    ownership_document_reference = models.CharField(max_length=240, blank=True)
    encumbrance_flag = models.BooleanField(default=False)
    encumbrance_summary = models.TextField(blank=True)
    verification_status_code = models.CharField(max_length=30, default="PENDING")
    created_by_public_id = models.UUIDField()
    verified_by_public_id = models.UUIDField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "landops_owner"
        constraints = [
            models.UniqueConstraint(fields=["parcel", "owner_name"], name="land_owner_name_uq"),
            models.CheckConstraint(
                condition=models.Q(share_percent__gt=0) & models.Q(share_percent__lte=100),
                name="land_owner_share_ck",
            ),
        ]
        indexes = [models.Index(fields=["company", "verification_status_code"], name="land_owner_verify_idx")]

    def clean(self) -> None:
        super().clean()
        self.owner_type_code = normalize_code(self.owner_type_code)
        self.verification_status_code = normalize_code(self.verification_status_code)
        if self.parcel_id and self.parcel.company_id != self.company_id:
            raise ValidationError("Ownership interest cannot cross companies.")


class DueDiligenceCase(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_due_diligence_cases")
    parcel = models.ForeignKey(LandParcel, on_delete=models.PROTECT, related_name="due_diligence_cases")
    case_number = models.CharField(max_length=80)
    category_code = models.CharField(max_length=60, default="TITLE")
    opened_on = models.DateField()
    target_on = models.DateField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    risk_rating_code = models.CharField(max_length=30, default="MEDIUM")
    findings = models.JSONField(default=list, blank=True)
    blockers = models.JSONField(default=list, blank=True)
    created_by_public_id = models.UUIDField()
    reviewed_by_public_id = models.UUIDField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "landops_diligence"
        constraints = [models.UniqueConstraint(fields=["company", "case_number"], name="land_dd_case_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "target_on"], name="land_dd_status_idx"),
            models.Index(fields=["company", "risk_rating_code"], name="land_dd_risk_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.case_number = normalize_code(self.case_number)
        self.category_code = normalize_code(self.category_code)
        self.status_code = normalize_code(self.status_code)
        self.risk_rating_code = normalize_code(self.risk_rating_code)
        if self.parcel_id and self.parcel.company_id != self.company_id:
            raise ValidationError("Due-diligence case cannot cross companies.")
        if self.target_on and self.target_on < self.opened_on:
            raise ValidationError({"target_on": "Target date cannot precede opened date."})
        if not isinstance(self.findings, list):
            raise ValidationError({"findings": "Findings must be a JSON array."})
        if not isinstance(self.blockers, list):
            raise ValidationError({"blockers": "Blockers must be a JSON array."})


class FeasibilityScenario(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_feasibility_scenarios")
    parcel = models.ForeignKey(LandParcel, on_delete=models.PROTECT, related_name="feasibility_scenarios")
    scenario_code = models.CharField(max_length=80)
    name = models.CharField(max_length=240)
    scenario_type_code = models.CharField(max_length=60, default="BASE_CASE")
    gross_development_area = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    saleable_area = models.DecimalField(max_digits=18, decimal_places=3, default=0)
    area_unit_code = models.CharField(max_length=30, default="SQ_M")
    planned_units = models.PositiveIntegerField(default=0)
    estimated_revenue = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    land_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    construction_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    soft_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    finance_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    contingency_cost = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    projected_margin_percent = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    irr_percent = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="INR")
    assumptions = models.JSONField(default=dict, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "landops_feasibility"
        constraints = [
            models.UniqueConstraint(fields=["parcel", "scenario_code"], name="land_feas_code_uq"),
            models.CheckConstraint(condition=models.Q(gross_development_area__gte=0), name="land_feas_gda_ck"),
            models.CheckConstraint(condition=models.Q(saleable_area__gte=0), name="land_feas_sale_ck"),
            models.CheckConstraint(condition=models.Q(estimated_revenue__gte=0), name="land_feas_revenue_ck"),
            models.CheckConstraint(condition=models.Q(land_cost__gte=0), name="land_feas_landcost_ck"),
            models.CheckConstraint(condition=models.Q(construction_cost__gte=0), name="land_feas_buildcost_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code"], name="land_feas_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.scenario_code = normalize_code(self.scenario_code)
        self.scenario_type_code = normalize_code(self.scenario_type_code)
        self.area_unit_code = normalize_code(self.area_unit_code)
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        if self.parcel_id and self.parcel.company_id != self.company_id:
            raise ValidationError("Feasibility scenario cannot cross companies.")
        if self.saleable_area > self.gross_development_area and self.gross_development_area > 0:
            raise ValidationError({"saleable_area": "Saleable area cannot exceed gross development area."})
        if not isinstance(self.assumptions, dict):
            raise ValidationError({"assumptions": "Feasibility assumptions must be a JSON object."})

    @property
    def total_cost(self) -> Decimal:
        return self.land_cost + self.construction_cost + self.soft_cost + self.finance_cost + self.contingency_cost


class AcquisitionOpportunity(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_acquisition_opportunities")
    parcel = models.ForeignKey(LandParcel, on_delete=models.PROTECT, related_name="acquisition_opportunities")
    feasibility = models.ForeignKey(FeasibilityScenario, on_delete=models.PROTECT, related_name="acquisition_opportunities", null=True, blank=True)
    opportunity_code = models.CharField(max_length=80)
    seller_name = models.CharField(max_length=240)
    acquisition_method_code = models.CharField(max_length=60, default="PURCHASE")
    stage_code = models.CharField(max_length=30, default="IDENTIFIED")
    asking_price = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    target_price = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    approved_budget = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=3, default="INR")
    probability_percent = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    expected_close_on = models.DateField(null=True, blank=True)
    sponsor_public_id = models.UUIDField(null=True, blank=True)
    owner_public_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "landops_opportunity"
        constraints = [
            models.UniqueConstraint(fields=["company", "opportunity_code"], name="land_opp_code_uq"),
            models.CheckConstraint(
                condition=models.Q(probability_percent__gte=0) & models.Q(probability_percent__lte=100),
                name="land_opp_prob_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(asking_price__isnull=True) | models.Q(asking_price__gte=0),
                name="land_opp_ask_ck",
            ),
            models.CheckConstraint(
                condition=models.Q(target_price__isnull=True) | models.Q(target_price__gte=0),
                name="land_opp_target_ck",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "stage_code", "expected_close_on"], name="land_opp_stage_idx"),
            models.Index(fields=["company", "parcel"], name="land_opp_parcel_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.opportunity_code = normalize_code(self.opportunity_code)
        self.acquisition_method_code = normalize_code(self.acquisition_method_code)
        self.stage_code = normalize_code(self.stage_code)
        self.currency_code = normalize_code(self.currency_code)
        if self.parcel_id and self.parcel.company_id != self.company_id:
            raise ValidationError("Acquisition opportunity cannot cross companies.")
        if self.feasibility_id:
            if self.feasibility.company_id != self.company_id or self.feasibility.parcel_id != self.parcel_id:
                raise ValidationError("Acquisition feasibility must belong to the same company and parcel.")


class CommercialOffer(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_commercial_offers")
    opportunity = models.ForeignKey(AcquisitionOpportunity, on_delete=models.PROTECT, related_name="offers")
    offer_number = models.CharField(max_length=80)
    offer_date = models.DateField()
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency_code = models.CharField(max_length=3, default="INR")
    validity_until = models.DateField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="DRAFT")
    conditions = models.JSONField(default=dict, blank=True)
    created_by_public_id = models.UUIDField()
    approved_by_public_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    issued_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "landops_offer"
        constraints = [
            models.UniqueConstraint(fields=["company", "offer_number"], name="land_offer_no_uq"),
            models.CheckConstraint(condition=models.Q(amount__gte=0), name="land_offer_amount_ck"),
        ]
        indexes = [models.Index(fields=["company", "status_code", "validity_until"], name="land_offer_status_idx")]

    def clean(self) -> None:
        super().clean()
        self.offer_number = normalize_code(self.offer_number)
        self.currency_code = normalize_code(self.currency_code)
        self.status_code = normalize_code(self.status_code)
        if self.opportunity_id and self.opportunity.company_id != self.company_id:
            raise ValidationError("Commercial offer cannot cross companies.")
        if self.validity_until and self.validity_until < self.offer_date:
            raise ValidationError({"validity_until": "Offer validity cannot precede the offer date."})
        if not isinstance(self.conditions, dict):
            raise ValidationError({"conditions": "Offer conditions must be a JSON object."})


class StatutoryApproval(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_statutory_approvals")
    parcel = models.ForeignKey(LandParcel, on_delete=models.PROTECT, related_name="statutory_approvals")
    opportunity = models.ForeignKey(AcquisitionOpportunity, on_delete=models.PROTECT, related_name="statutory_approvals", null=True, blank=True)
    approval_code = models.CharField(max_length=80)
    approval_type_code = models.CharField(max_length=80)
    authority_name = models.CharField(max_length=240)
    application_reference = models.CharField(max_length=160, blank=True)
    submitted_on = models.DateField(null=True, blank=True)
    expected_on = models.DateField(null=True, blank=True)
    approved_on = models.DateField(null=True, blank=True)
    expiry_on = models.DateField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="PLANNED")
    mandatory_for_acquisition = models.BooleanField(default=False)
    conditions = models.JSONField(default=dict, blank=True)
    evidence_reference = models.CharField(max_length=240, blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "landops_approval"
        constraints = [models.UniqueConstraint(fields=["company", "approval_code"], name="land_approval_code_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "expiry_on"], name="land_approval_status_idx"),
            models.Index(fields=["company", "parcel"], name="land_approval_parcel_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.approval_code = normalize_code(self.approval_code)
        self.approval_type_code = normalize_code(self.approval_type_code)
        self.status_code = normalize_code(self.status_code)
        if self.parcel_id and self.parcel.company_id != self.company_id:
            raise ValidationError("Statutory approval cannot cross companies.")
        if self.opportunity_id and (self.opportunity.company_id != self.company_id or self.opportunity.parcel_id != self.parcel_id):
            raise ValidationError("Approval opportunity must belong to the same company and parcel.")
        if self.expected_on and self.submitted_on and self.expected_on < self.submitted_on:
            raise ValidationError({"expected_on": "Expected decision date cannot precede submission date."})
        if self.expiry_on and self.approved_on and self.expiry_on <= self.approved_on:
            raise ValidationError({"expiry_on": "Approval expiry must follow approval date."})
        if not isinstance(self.conditions, dict):
            raise ValidationError({"conditions": "Approval conditions must be a JSON object."})


class LandRisk(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_acquisition_risks")
    parcel = models.ForeignKey(LandParcel, on_delete=models.PROTECT, related_name="land_risks")
    opportunity = models.ForeignKey(AcquisitionOpportunity, on_delete=models.PROTECT, related_name="risks", null=True, blank=True)
    risk_number = models.CharField(max_length=80)
    category_code = models.CharField(max_length=60, default="LEGAL")
    severity_code = models.CharField(max_length=30, default="MEDIUM")
    probability_code = models.CharField(max_length=30, default="POSSIBLE")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    mitigation_plan = models.TextField(blank=True)
    owner_public_id = models.UUIDField(null=True, blank=True)
    due_on = models.DateField(null=True, blank=True)
    status_code = models.CharField(max_length=30, default="OPEN")
    accepted_by_public_id = models.UUIDField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    closed_by_public_id = models.UUIDField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "landops_risk"
        constraints = [models.UniqueConstraint(fields=["company", "risk_number"], name="land_risk_no_uq")]
        indexes = [
            models.Index(fields=["company", "status_code", "severity_code"], name="land_risk_status_idx"),
            models.Index(fields=["company", "due_on"], name="land_risk_due_idx"),
        ]

    def clean(self) -> None:
        super().clean()
        self.risk_number = normalize_code(self.risk_number)
        self.category_code = normalize_code(self.category_code)
        self.severity_code = normalize_code(self.severity_code)
        self.probability_code = normalize_code(self.probability_code)
        self.status_code = normalize_code(self.status_code)
        if self.parcel_id and self.parcel.company_id != self.company_id:
            raise ValidationError("Land risk cannot cross companies.")
        if self.opportunity_id and (self.opportunity.company_id != self.company_id or self.opportunity.parcel_id != self.parcel_id):
            raise ValidationError("Risk opportunity must belong to the same company and parcel.")


class AcquisitionEvent(PublicIdModel, TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="land_acquisition_events")
    opportunity = models.ForeignKey(AcquisitionOpportunity, on_delete=models.PROTECT, related_name="events")
    event_type_code = models.CharField(max_length=60)
    event_on = models.DateTimeField()
    summary = models.CharField(max_length=500)
    evidence = models.JSONField(default=dict, blank=True)
    recorded_by_public_id = models.UUIDField()

    class Meta:
        db_table = "landops_event"
        indexes = [models.Index(fields=["company", "opportunity", "event_on"], name="land_event_opp_idx")]

    def clean(self) -> None:
        super().clean()
        self.event_type_code = normalize_code(self.event_type_code)
        if self.opportunity_id and self.opportunity.company_id != self.company_id:
            raise ValidationError("Acquisition event cannot cross companies.")
        if not isinstance(self.evidence, dict):
            raise ValidationError({"evidence": "Event evidence must be a JSON object."})
