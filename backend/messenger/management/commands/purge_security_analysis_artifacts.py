import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from messenger.models import SecurityAnalysisAuditEvent, SecurityJourneyReport


class Command(BaseCommand):
    help = "Purge aged security analysis artifacts based on retention policy."

    def handle(self, *args, **options):
        retention_days = int(os.getenv("SECURITY_ANALYSIS_RETENTION_DAYS", "90"))
        cutoff = timezone.now() - timedelta(days=retention_days)

        report_qs = SecurityJourneyReport.objects.filter(created_at__lt=cutoff)
        deleted_report_ids = list(report_qs.values_list("id", flat=True))
        deleted_reports_count = report_qs.count()
        report_qs.delete()

        stale_audit_qs = SecurityAnalysisAuditEvent.objects.filter(created_at__lt=cutoff)
        stale_audit_deleted_count = stale_audit_qs.count()
        stale_audit_qs.delete()

        SecurityAnalysisAuditEvent.objects.create(
            actor=None,
            report=None,
            action=SecurityAnalysisAuditEvent.ACTION_RETENTION_PURGE,
            details={
                "retention_days": retention_days,
                "cutoff": cutoff.isoformat(),
                "deleted_reports_count": deleted_reports_count,
                "deleted_report_ids": deleted_report_ids[:100],
                "deleted_audit_events_count": stale_audit_deleted_count,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Purge complete: "
                f"reports={deleted_reports_count}, audit_events={stale_audit_deleted_count}, cutoff={cutoff.isoformat()}"
            )
        )
