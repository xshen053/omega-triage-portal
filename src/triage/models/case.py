import logging
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from core import settings
from triage.models import BaseTimestampedModel, BaseUserTrackedModel, WorkItemState

logger = logging.getLogger(__name__)


class Case(BaseTimestampedModel, BaseUserTrackedModel):
    """
    Represents a case that is being reported to a maintainer for a fix.
    """

    class CasePartner(models.TextChoices):
        NONE = "N", _("None")
        GITHUB_SECURITY_LAB = "GS", _("GitHub Security Lab")
        CERT = "CT", _("CERT")
        MSRC = "MS", _("MSRC")
        NOT_SPECIFIED = "NS", _("Not Specified")

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    findings = models.ManyToManyField("Finding", related_name="cases")
    state = models.CharField(max_length=2, choices=WorkItemState.choices, default=WorkItemState.NEW)
    title = models.CharField(max_length=1024)
    description = models.TextField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name="assigned_cases",
        on_delete=models.SET_NULL,
    )
    assigned_dt = models.DateTimeField(auto_now_add=True)
    reported_to = models.CharField(max_length=2048, null=True, blank=True)
    reporting_partner = models.CharField(
        max_length=2,
        choices=CasePartner.choices,
        default=CasePartner.NOT_SPECIFIED,
        null=True,
        blank=True,
    )
    report_foreign_reference = models.CharField(max_length=1024, null=True, blank=True)
    resolved_target_dt = models.DateTimeField(null=True, blank=True)
    resolved_dt = models.DateTimeField(null=True, blank=True)
    notes = models.ManyToManyField("Note", related_name="cases")
