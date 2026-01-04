"""
Analytics service for usage tracking and metrics.

Provides methods for:
- Recording usage events
- Calculating metrics and statistics
- Checking quota limits
- Generating reports
"""
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

import structlog
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from backend.models.analytics import (
    UsageMetric,
    MetricType,
    OrganizationQuota,
    ProcessingStats,
    DailyActiveUsers,
    BillingEvent,
)

logger = structlog.get_logger(__name__)


class AnalyticsService:
    """Service for tracking and analyzing usage metrics."""

    def __init__(self, db: Session):
        self.db = db

    # =========================================================================
    # Metric Recording
    # =========================================================================

    def increment_metric(
        self,
        organization_id: uuid.UUID,
        metric_type: MetricType,
        count: int = 1,
        value: float = None,
        metric_date: date = None,
        metadata: Dict[str, Any] = None,
    ) -> UsageMetric:
        """
        Increment a usage metric for an organization.

        Args:
            organization_id: Organization to record metric for
            metric_type: Type of metric to increment
            count: Amount to increment by
            value: Optional value to add (for averages, totals)
            metric_date: Date for the metric (defaults to today)
            metadata: Additional context

        Returns:
            Updated or created UsageMetric
        """
        if metric_date is None:
            metric_date = date.today()

        # Find or create metric record
        metric = self.db.query(UsageMetric).filter(
            UsageMetric.organization_id == organization_id,
            UsageMetric.metric_type == metric_type,
            UsageMetric.metric_date == metric_date,
        ).first()

        if metric:
            metric.count += count
            if value is not None:
                metric.total_value = (metric.total_value or 0) + value
            if metadata:
                existing = metric.extra_data or {}
                existing.update(metadata)
                metric.extra_data = existing
        else:
            metric = UsageMetric(
                organization_id=organization_id,
                metric_type=metric_type,
                metric_date=metric_date,
                count=count,
                total_value=value,
                extra_data=metadata,
            )
            self.db.add(metric)

        self.db.commit()
        self.db.refresh(metric)

        logger.debug(
            "metric_incremented",
            organization_id=str(organization_id),
            metric_type=metric_type.value,
            count=count,
        )

        return metric

    def record_processing_stats(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID = None,
        document_id: str = None,
        job_id: uuid.UUID = None,
        filename: str = None,
        file_size_bytes: int = None,
        page_count: int = None,
        statement_type: str = None,
        processing_started_at: datetime = None,
        processing_completed_at: datetime = None,
        tables_extracted: int = None,
        rows_extracted: int = None,
        items_classified: int = None,
        classification_confidence_avg: float = None,
        success: bool = True,
        error_message: str = None,
        error_stage: str = None,
        stage_timings: Dict[str, int] = None,
    ) -> ProcessingStats:
        """Record processing statistics for a document."""
        stats = ProcessingStats(
            organization_id=organization_id,
            user_id=user_id,
            document_id=document_id,
            job_id=job_id,
            filename=filename,
            file_size_bytes=file_size_bytes,
            page_count=page_count,
            statement_type=statement_type,
            processing_started_at=processing_started_at,
            processing_completed_at=processing_completed_at,
            tables_extracted=tables_extracted,
            rows_extracted=rows_extracted,
            items_classified=items_classified,
            classification_confidence_avg=classification_confidence_avg,
            success=success,
            error_message=error_message,
            error_stage=error_stage,
        )

        # Calculate total duration
        if processing_started_at and processing_completed_at:
            delta = processing_completed_at - processing_started_at
            stats.processing_duration_ms = int(delta.total_seconds() * 1000)

        # Add stage timings
        if stage_timings:
            stats.upload_duration_ms = stage_timings.get("upload")
            stats.extraction_duration_ms = stage_timings.get("extraction")
            stats.classification_duration_ms = stage_timings.get("classification")
            stats.export_duration_ms = stage_timings.get("export")

        self.db.add(stats)

        # Also increment daily metrics
        metric_type = MetricType.DOCUMENTS_PROCESSED if success else MetricType.DOCUMENTS_FAILED
        self.increment_metric(organization_id, metric_type)

        if page_count:
            self.increment_metric(
                organization_id,
                MetricType.PAGES_PROCESSED,
                count=page_count,
            )

        self.db.commit()
        self.db.refresh(stats)

        return stats

    def record_user_activity(
        self,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        activity_type: str,
    ) -> DailyActiveUsers:
        """Record user activity for DAU tracking."""
        today = date.today()
        now = datetime.utcnow()

        # Find or create DAU record
        dau = self.db.query(DailyActiveUsers).filter(
            DailyActiveUsers.user_id == user_id,
            DailyActiveUsers.activity_date == today,
        ).first()

        if dau:
            dau.last_activity_at = now
            if activity_type == "login":
                dau.login_count += 1
            elif activity_type == "api_request":
                dau.api_request_count += 1
            elif activity_type == "document_upload":
                dau.document_uploads += 1
            elif activity_type == "export":
                dau.exports_created += 1
        else:
            dau = DailyActiveUsers(
                organization_id=organization_id,
                user_id=user_id,
                activity_date=today,
                first_activity_at=now,
                last_activity_at=now,
                login_count=1 if activity_type == "login" else 0,
                api_request_count=1 if activity_type == "api_request" else 0,
                document_uploads=1 if activity_type == "document_upload" else 0,
                exports_created=1 if activity_type == "export" else 0,
            )
            self.db.add(dau)

        self.db.commit()
        return dau

    def record_billing_event(
        self,
        organization_id: uuid.UUID,
        event_type: str,
        quantity: float = 1.0,
        unit: str = None,
        unit_price: float = None,
        reference_id: str = None,
        reference_type: str = None,
    ) -> BillingEvent:
        """Record a billable event."""
        total_amount = None
        if unit_price is not None:
            total_amount = quantity * unit_price

        event = BillingEvent(
            organization_id=organization_id,
            event_type=event_type,
            quantity=quantity,
            unit=unit,
            unit_price=unit_price,
            total_amount=total_amount,
            reference_id=reference_id,
            reference_type=reference_type,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)

        return event

    # =========================================================================
    # Metrics Retrieval
    # =========================================================================

    def get_metrics_summary(
        self,
        organization_id: uuid.UUID,
        start_date: date = None,
        end_date: date = None,
    ) -> Dict[str, Any]:
        """Get summarized metrics for an organization."""
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        # Query metrics
        metrics = self.db.query(
            UsageMetric.metric_type,
            func.sum(UsageMetric.count).label("total_count"),
            func.sum(UsageMetric.total_value).label("total_value"),
        ).filter(
            UsageMetric.organization_id == organization_id,
            UsageMetric.metric_date >= start_date,
            UsageMetric.metric_date <= end_date,
        ).group_by(UsageMetric.metric_type).all()

        result = {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "metrics": {},
        }

        for metric_type, total_count, total_value in metrics:
            result["metrics"][metric_type.value] = {
                "count": total_count or 0,
                "value": total_value,
            }

        return result

    def get_daily_metrics(
        self,
        organization_id: uuid.UUID,
        metric_type: MetricType,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get daily breakdown of a specific metric."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        metrics = self.db.query(UsageMetric).filter(
            UsageMetric.organization_id == organization_id,
            UsageMetric.metric_type == metric_type,
            UsageMetric.metric_date >= start_date,
            UsageMetric.metric_date <= end_date,
        ).order_by(UsageMetric.metric_date).all()

        return [
            {
                "date": m.metric_date.isoformat(),
                "count": m.count,
                "value": m.total_value,
            }
            for m in metrics
        ]

    def get_processing_stats_summary(
        self,
        organization_id: uuid.UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get processing statistics summary."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        base_query = self.db.query(ProcessingStats).filter(
            ProcessingStats.organization_id == organization_id,
            ProcessingStats.created_at >= cutoff,
        )

        total = base_query.count()
        successful = base_query.filter(ProcessingStats.success == True).count()
        failed = base_query.filter(ProcessingStats.success == False).count()

        # Averages
        avg_stats = self.db.query(
            func.avg(ProcessingStats.processing_duration_ms).label("avg_duration"),
            func.avg(ProcessingStats.page_count).label("avg_pages"),
            func.avg(ProcessingStats.classification_confidence_avg).label("avg_confidence"),
            func.sum(ProcessingStats.rows_extracted).label("total_rows"),
        ).filter(
            ProcessingStats.organization_id == organization_id,
            ProcessingStats.created_at >= cutoff,
            ProcessingStats.success == True,
        ).first()

        # By statement type
        by_type = self.db.query(
            ProcessingStats.statement_type,
            func.count(ProcessingStats.id).label("count"),
        ).filter(
            ProcessingStats.organization_id == organization_id,
            ProcessingStats.created_at >= cutoff,
        ).group_by(ProcessingStats.statement_type).all()

        return {
            "period_days": days,
            "total_documents": total,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total * 100) if total > 0 else 0,
            "avg_processing_time_ms": avg_stats.avg_duration if avg_stats else None,
            "avg_pages_per_document": avg_stats.avg_pages if avg_stats else None,
            "avg_classification_confidence": avg_stats.avg_confidence if avg_stats else None,
            "total_rows_extracted": int(avg_stats.total_rows or 0) if avg_stats else 0,
            "by_statement_type": {
                t: c for t, c in by_type if t is not None
            },
        }

    def get_dau_stats(
        self,
        organization_id: uuid.UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get daily active users statistics."""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Daily counts
        daily = self.db.query(
            DailyActiveUsers.activity_date,
            func.count(DailyActiveUsers.user_id.distinct()).label("user_count"),
        ).filter(
            DailyActiveUsers.organization_id == organization_id,
            DailyActiveUsers.activity_date >= start_date,
            DailyActiveUsers.activity_date <= end_date,
        ).group_by(DailyActiveUsers.activity_date).all()

        # Monthly active (unique users in period)
        mau = self.db.query(
            func.count(DailyActiveUsers.user_id.distinct())
        ).filter(
            DailyActiveUsers.organization_id == organization_id,
            DailyActiveUsers.activity_date >= start_date,
            DailyActiveUsers.activity_date <= end_date,
        ).scalar() or 0

        daily_data = [{"date": d.isoformat(), "users": c} for d, c in daily]
        avg_dau = sum(d["users"] for d in daily_data) / len(daily_data) if daily_data else 0

        return {
            "period_days": days,
            "monthly_active_users": mau,
            "average_daily_active": round(avg_dau, 1),
            "daily_breakdown": daily_data,
        }

    # =========================================================================
    # Quota Management
    # =========================================================================

    def get_or_create_quota(self, organization_id: uuid.UUID) -> OrganizationQuota:
        """Get or create quota for an organization."""
        quota = self.db.query(OrganizationQuota).filter(
            OrganizationQuota.organization_id == organization_id,
        ).first()

        if not quota:
            quota = OrganizationQuota(organization_id=organization_id)
            self.db.add(quota)
            self.db.commit()
            self.db.refresh(quota)

        return quota

    def check_quota(
        self,
        organization_id: uuid.UUID,
        check_type: str,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Check if an organization is within quota limits.

        Args:
            organization_id: Organization to check
            check_type: Type of quota to check (documents, api, storage, users)

        Returns:
            Tuple of (is_allowed, message, usage_info)
        """
        quota = self.get_or_create_quota(organization_id)

        if check_type == "documents":
            # Get documents this month
            month_start = date.today().replace(day=1)
            docs_this_month = self.db.query(func.sum(UsageMetric.count)).filter(
                UsageMetric.organization_id == organization_id,
                UsageMetric.metric_type == MetricType.DOCUMENTS_PROCESSED,
                UsageMetric.metric_date >= month_start,
            ).scalar() or 0

            usage_info = {
                "used": docs_this_month,
                "limit": quota.max_documents_per_month,
                "remaining": max(0, quota.max_documents_per_month - docs_this_month),
            }

            if docs_this_month >= quota.max_documents_per_month:
                return False, "Monthly document limit reached", usage_info
            return True, "OK", usage_info

        elif check_type == "api":
            # Get API requests today
            today_requests = self.db.query(func.sum(UsageMetric.count)).filter(
                UsageMetric.organization_id == organization_id,
                UsageMetric.metric_type == MetricType.API_REQUESTS,
                UsageMetric.metric_date == date.today(),
            ).scalar() or 0

            usage_info = {
                "used": today_requests,
                "limit": quota.max_api_requests_per_day,
                "remaining": max(0, quota.max_api_requests_per_day - today_requests),
            }

            if today_requests >= quota.max_api_requests_per_day:
                return False, "Daily API request limit reached", usage_info
            return True, "OK", usage_info

        elif check_type == "storage":
            # Get current storage usage
            storage_bytes = self.db.query(func.sum(UsageMetric.count)).filter(
                UsageMetric.organization_id == organization_id,
                UsageMetric.metric_type == MetricType.STORAGE_USED_BYTES,
            ).scalar() or 0

            storage_gb = storage_bytes / (1024 ** 3)
            usage_info = {
                "used_gb": round(storage_gb, 2),
                "limit_gb": quota.max_storage_gb,
                "remaining_gb": round(max(0, quota.max_storage_gb - storage_gb), 2),
            }

            if storage_gb >= quota.max_storage_gb:
                return False, "Storage limit reached", usage_info
            return True, "OK", usage_info

        return True, "Unknown check type", {}

    def get_usage_report(
        self,
        organization_id: uuid.UUID,
    ) -> Dict[str, Any]:
        """Get comprehensive usage report for an organization."""
        quota = self.get_or_create_quota(organization_id)
        month_start = date.today().replace(day=1)

        # Document usage
        _, _, doc_usage = self.check_quota(organization_id, "documents")

        # API usage
        _, _, api_usage = self.check_quota(organization_id, "api")

        # Storage usage
        _, _, storage_usage = self.check_quota(organization_id, "storage")

        # Processing stats
        processing_summary = self.get_processing_stats_summary(organization_id, days=30)

        # Active users
        dau_stats = self.get_dau_stats(organization_id, days=30)

        return {
            "organization_id": str(organization_id),
            "plan": quota.plan_name,
            "generated_at": datetime.utcnow().isoformat(),
            "quotas": {
                "documents": {
                    **doc_usage,
                    "period": "monthly",
                },
                "api_requests": {
                    **api_usage,
                    "period": "daily",
                },
                "storage": storage_usage,
            },
            "limits": {
                "max_users": quota.max_users,
                "max_api_keys": quota.max_api_keys,
                "max_integrations": quota.max_integrations,
                "max_file_size_mb": quota.max_file_size_mb,
                "max_pages_per_document": quota.max_pages_per_document,
            },
            "features": {
                "batch_processing": quota.allow_batch_processing,
                "api_access": quota.allow_api_access,
                "webhooks": quota.allow_webhooks,
                "integrations": quota.allow_integrations,
            },
            "processing": processing_summary,
            "users": dau_stats,
        }


# Convenience functions
def get_analytics_service(db: Session) -> AnalyticsService:
    """Get analytics service instance."""
    return AnalyticsService(db)
