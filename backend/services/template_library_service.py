"""
Template Library Service.

Provides business logic for template versioning, sharing, reviews, and collections.
"""
import hashlib
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

import structlog
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.template import Template, TemplateStructure
from backend.models.template_library import (
    TemplateCategory,
    TemplateVersion,
    SharedTemplate,
    TemplateFork,
    TemplateReview,
    TemplateReviewVote,
    TemplateUsageHistory,
    TemplateCollection,
    CollectionTemplate,
    CollectionFollower,
    TemplateVisibility,
)
from backend.models.mapping_profile import TemplateLibraryItem

logger = structlog.get_logger(__name__)
settings = get_settings()


class TemplateLibraryService:
    """Service for managing template library operations."""

    def __init__(self, db: Session):
        self.db = db

    # ==================== Version Management ====================

    def create_version(
        self,
        template_id: uuid.UUID,
        version_number: str,
        changed_by_id: uuid.UUID,
        change_summary: Optional[str] = None,
        version_label: Optional[str] = None,
        publish: bool = False,
    ) -> TemplateVersion:
        """
        Create a new version of a template.

        Args:
            template_id: The template to version
            version_number: Semantic version (e.g., "1.0.0")
            changed_by_id: User creating the version
            change_summary: Description of changes
            version_label: Optional friendly name
            publish: Whether to publish immediately

        Returns:
            Created TemplateVersion
        """
        template = self.db.query(Template).filter(Template.id == template_id).first()
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Calculate file hash
        file_hash = None
        file_size = None
        if template.file_path and Path(template.file_path).exists():
            file_path = Path(template.file_path)
            file_size = file_path.stat().st_size
            with open(file_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()

        # Get structure snapshot
        structure_snapshot = {}
        if template.structure:
            structure_snapshot = {
                "sections": template.structure.sections,
                "periods": template.structure.periods,
                "sheets": template.structure.sheets,
                "confidence_score": template.structure.confidence_score,
            }

        # Mark previous versions as not latest
        self.db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id,
            TemplateVersion.is_latest == True,
        ).update({"is_latest": False})

        # Create new version
        version = TemplateVersion(
            template_id=template_id,
            version_number=version_number,
            version_label=version_label,
            file_path=template.file_path,
            file_hash=file_hash,
            file_size=file_size,
            structure_snapshot=structure_snapshot,
            change_summary=change_summary,
            changed_by_id=changed_by_id,
            is_published=publish,
            is_latest=True,
        )

        self.db.add(version)
        self.db.commit()

        logger.info(
            "template_version_created",
            template_id=str(template_id),
            version=version_number,
        )

        return version

    def get_versions(
        self,
        template_id: uuid.UUID,
        published_only: bool = False,
    ) -> List[TemplateVersion]:
        """Get all versions of a template."""
        query = self.db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id
        )

        if published_only:
            query = query.filter(TemplateVersion.is_published == True)

        return query.order_by(desc(TemplateVersion.created_at)).all()

    def publish_version(self, version_id: uuid.UUID) -> TemplateVersion:
        """Publish a template version."""
        version = self.db.query(TemplateVersion).filter(
            TemplateVersion.id == version_id
        ).first()

        if not version:
            raise ValueError(f"Version {version_id} not found")

        version.is_published = True
        self.db.commit()

        return version

    def restore_version(
        self,
        version_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Template:
        """
        Restore a template to a previous version.

        Creates a new version with the restored content.
        """
        version = self.db.query(TemplateVersion).filter(
            TemplateVersion.id == version_id
        ).first()

        if not version:
            raise ValueError(f"Version {version_id} not found")

        template = self.db.query(Template).filter(
            Template.id == version.template_id
        ).first()

        # Create a new version marking the restoration
        new_version = self.create_version(
            template_id=template.id,
            version_number=self._increment_version(version.version_number),
            changed_by_id=user_id,
            change_summary=f"Restored from version {version.version_number}",
            publish=True,
        )

        logger.info(
            "template_version_restored",
            template_id=str(template.id),
            from_version=version.version_number,
            to_version=new_version.version_number,
        )

        return template

    def _increment_version(self, version: str) -> str:
        """Increment the patch version number."""
        parts = version.split(".")
        if len(parts) == 3:
            parts[2] = str(int(parts[2]) + 1)
            return ".".join(parts)
        return f"{version}.1"

    # ==================== Sharing ====================

    def share_template(
        self,
        template_id: uuid.UUID,
        shared_by_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        permission: str = "view",
        message: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> SharedTemplate:
        """
        Share a template with a user or organization.

        Args:
            template_id: Template to share
            shared_by_id: User sharing the template
            user_id: User to share with (optional)
            organization_id: Organization to share with (optional)
            permission: Permission level (view, edit, admin)
            message: Optional message to recipient
            expires_in_days: Optional expiration

        Returns:
            Created SharedTemplate
        """
        if not user_id and not organization_id:
            raise ValueError("Must specify either user_id or organization_id")

        expires_at = None
        if expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        # Check for existing share
        existing = self.db.query(SharedTemplate).filter(
            SharedTemplate.template_id == template_id,
            or_(
                SharedTemplate.shared_with_user_id == user_id,
                SharedTemplate.shared_with_org_id == organization_id,
            ),
        ).first()

        if existing:
            # Update existing share
            existing.permission = permission
            existing.expires_at = expires_at
            existing.share_message = message
            self.db.commit()
            return existing

        # Create new share
        share = SharedTemplate(
            template_id=template_id,
            shared_by_id=shared_by_id,
            shared_with_user_id=user_id,
            shared_with_org_id=organization_id,
            permission=permission,
            share_message=message,
            expires_at=expires_at,
        )

        self.db.add(share)
        self.db.commit()

        logger.info(
            "template_shared",
            template_id=str(template_id),
            shared_with_user=str(user_id) if user_id else None,
            shared_with_org=str(organization_id) if organization_id else None,
        )

        return share

    def accept_share(self, share_id: uuid.UUID) -> SharedTemplate:
        """Accept a template share invitation."""
        share = self.db.query(SharedTemplate).filter(
            SharedTemplate.id == share_id
        ).first()

        if not share:
            raise ValueError(f"Share {share_id} not found")

        share.is_accepted = True
        share.accepted_at = datetime.utcnow()
        self.db.commit()

        return share

    def revoke_share(self, share_id: uuid.UUID) -> None:
        """Revoke a template share."""
        share = self.db.query(SharedTemplate).filter(
            SharedTemplate.id == share_id
        ).first()

        if share:
            self.db.delete(share)
            self.db.commit()

    def get_shared_with_me(
        self,
        user_id: uuid.UUID,
        organization_ids: Optional[List[uuid.UUID]] = None,
    ) -> List[SharedTemplate]:
        """Get templates shared with a user."""
        query = self.db.query(SharedTemplate).filter(
            or_(
                SharedTemplate.shared_with_user_id == user_id,
                SharedTemplate.shared_with_org_id.in_(organization_ids or []),
            ),
            SharedTemplate.is_accepted == True,
            or_(
                SharedTemplate.expires_at.is_(None),
                SharedTemplate.expires_at > datetime.utcnow(),
            ),
        )

        return query.all()

    # ==================== Forking ====================

    def fork_template(
        self,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
        new_name: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Tuple[Template, TemplateFork]:
        """
        Fork (copy) a template.

        Args:
            template_id: Source template to fork
            user_id: User creating the fork
            new_name: Name for the forked template
            reason: Reason for forking

        Returns:
            Tuple of (new Template, TemplateFork record)
        """
        source = self.db.query(Template).filter(Template.id == template_id).first()
        if not source:
            raise ValueError(f"Template {template_id} not found")

        # Copy the template file
        new_id = uuid.uuid4()
        if source.file_path and Path(source.file_path).exists():
            source_path = Path(source.file_path)
            new_path = source_path.parent / f"{new_id}{source_path.suffix}"
            shutil.copy2(source_path, new_path)
            new_file_path = str(new_path)
        else:
            new_file_path = source.file_path

        # Create forked template
        forked = Template(
            id=new_id,
            filename=new_name or f"Fork of {source.filename}",
            file_path=new_file_path,
            status=source.status,
            sheet_count=source.sheet_count,
            extra_data=source.extra_data,
        )

        self.db.add(forked)
        self.db.flush()

        # Copy structure if exists
        if source.structure:
            new_structure = TemplateStructure(
                template_id=forked.id,
                sections=source.structure.sections,
                periods=source.structure.periods,
                sheets=source.structure.sheets,
                dependency_graph=source.structure.dependency_graph,
                confidence_score=source.structure.confidence_score,
            )
            self.db.add(new_structure)

        # Get latest version
        latest_version = self.db.query(TemplateVersion).filter(
            TemplateVersion.template_id == template_id,
            TemplateVersion.is_latest == True,
        ).first()

        # Create fork record
        fork = TemplateFork(
            source_template_id=template_id,
            source_version_id=latest_version.id if latest_version else None,
            forked_template_id=forked.id,
            forked_by_id=user_id,
            fork_reason=reason,
        )

        self.db.add(fork)
        self.db.commit()

        logger.info(
            "template_forked",
            source_template=str(template_id),
            forked_template=str(forked.id),
            user_id=str(user_id),
        )

        return forked, fork

    def get_fork_count(self, template_id: uuid.UUID) -> int:
        """Get the number of forks for a template."""
        return self.db.query(func.count(TemplateFork.id)).filter(
            TemplateFork.source_template_id == template_id
        ).scalar()

    # ==================== Reviews ====================

    def add_review(
        self,
        template_id: uuid.UUID,
        user_id: uuid.UUID,
        rating: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        pros: Optional[List[str]] = None,
        cons: Optional[List[str]] = None,
        use_case: Optional[str] = None,
        experience_level: Optional[str] = None,
    ) -> TemplateReview:
        """
        Add a review for a template.

        Args:
            template_id: Template being reviewed
            user_id: User creating the review
            rating: Star rating (1-5)
            title: Review title
            content: Review text
            pros: List of pros
            cons: List of cons
            use_case: How they used it
            experience_level: User's experience level

        Returns:
            Created TemplateReview
        """
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")

        # Check for existing review
        existing = self.db.query(TemplateReview).filter(
            TemplateReview.template_id == template_id,
            TemplateReview.user_id == user_id,
        ).first()

        if existing:
            # Update existing review
            existing.rating = rating
            existing.title = title
            existing.content = content
            existing.pros = pros or []
            existing.cons = cons or []
            existing.use_case = use_case
            existing.experience_level = experience_level
            existing.updated_at = datetime.utcnow()
            self.db.commit()
            self._update_template_rating(template_id)
            return existing

        # Check if user has used the template
        has_used = self.db.query(TemplateUsageHistory).filter(
            TemplateUsageHistory.template_id == template_id,
            TemplateUsageHistory.user_id == user_id,
            TemplateUsageHistory.action == "used",
        ).first()

        review = TemplateReview(
            template_id=template_id,
            user_id=user_id,
            rating=rating,
            title=title,
            content=content,
            pros=pros or [],
            cons=cons or [],
            use_case=use_case,
            experience_level=experience_level,
            is_verified_purchase=has_used is not None,
        )

        self.db.add(review)
        self.db.commit()

        # Update template rating
        self._update_template_rating(template_id)

        logger.info(
            "template_review_added",
            template_id=str(template_id),
            rating=rating,
        )

        return review

    def _update_template_rating(self, template_id: uuid.UUID) -> None:
        """Update the average rating for a template in the library."""
        avg_rating = self.db.query(func.avg(TemplateReview.rating)).filter(
            TemplateReview.template_id == template_id,
            TemplateReview.is_approved == True,
        ).scalar()

        library_item = self.db.query(TemplateLibraryItem).filter(
            TemplateLibraryItem.template_id == template_id
        ).first()

        if library_item and avg_rating:
            library_item.rating = float(avg_rating)
            self.db.commit()

    def vote_review(
        self,
        review_id: uuid.UUID,
        user_id: uuid.UUID,
        is_helpful: bool,
    ) -> TemplateReviewVote:
        """Vote on whether a review is helpful."""
        # Check for existing vote
        existing = self.db.query(TemplateReviewVote).filter(
            TemplateReviewVote.review_id == review_id,
            TemplateReviewVote.user_id == user_id,
        ).first()

        if existing:
            # Update vote
            old_helpful = existing.is_helpful
            existing.is_helpful = is_helpful
            self.db.commit()

            # Update counts on review
            review = self.db.query(TemplateReview).filter(
                TemplateReview.id == review_id
            ).first()

            if old_helpful != is_helpful:
                if is_helpful:
                    review.helpful_count += 1
                    review.not_helpful_count -= 1
                else:
                    review.helpful_count -= 1
                    review.not_helpful_count += 1
                self.db.commit()

            return existing

        vote = TemplateReviewVote(
            review_id=review_id,
            user_id=user_id,
            is_helpful=is_helpful,
        )

        self.db.add(vote)

        # Update counts
        review = self.db.query(TemplateReview).filter(
            TemplateReview.id == review_id
        ).first()

        if is_helpful:
            review.helpful_count += 1
        else:
            review.not_helpful_count += 1

        self.db.commit()

        return vote

    def get_reviews(
        self,
        template_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "helpful",  # helpful, recent, rating_high, rating_low
    ) -> List[TemplateReview]:
        """Get reviews for a template."""
        query = self.db.query(TemplateReview).filter(
            TemplateReview.template_id == template_id,
            TemplateReview.is_approved == True,
        )

        if sort_by == "helpful":
            query = query.order_by(desc(TemplateReview.helpful_count))
        elif sort_by == "recent":
            query = query.order_by(desc(TemplateReview.created_at))
        elif sort_by == "rating_high":
            query = query.order_by(desc(TemplateReview.rating))
        elif sort_by == "rating_low":
            query = query.order_by(TemplateReview.rating)

        return query.offset(offset).limit(limit).all()

    # ==================== Usage Tracking ====================

    def record_usage(
        self,
        template_id: uuid.UUID,
        action: str,
        user_id: Optional[uuid.UUID] = None,
        organization_id: Optional[uuid.UUID] = None,
        document_id: Optional[uuid.UUID] = None,
        source: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> TemplateUsageHistory:
        """Record template usage for analytics."""
        usage = TemplateUsageHistory(
            template_id=template_id,
            user_id=user_id,
            organization_id=organization_id,
            action=action,
            document_id=document_id,
            source=source,
            session_id=session_id,
        )

        self.db.add(usage)

        # Update library item counts
        library_item = self.db.query(TemplateLibraryItem).filter(
            TemplateLibraryItem.template_id == template_id
        ).first()

        if library_item:
            if action == "downloaded":
                library_item.download_count += 1
            elif action == "used":
                library_item.use_count += 1

        self.db.commit()

        return usage

    def get_usage_stats(
        self,
        template_id: uuid.UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get usage statistics for a template."""
        since = datetime.utcnow() - timedelta(days=days)

        # Get counts by action
        action_counts = self.db.query(
            TemplateUsageHistory.action,
            func.count(TemplateUsageHistory.id),
        ).filter(
            TemplateUsageHistory.template_id == template_id,
            TemplateUsageHistory.created_at >= since,
        ).group_by(TemplateUsageHistory.action).all()

        # Get unique users
        unique_users = self.db.query(
            func.count(func.distinct(TemplateUsageHistory.user_id))
        ).filter(
            TemplateUsageHistory.template_id == template_id,
            TemplateUsageHistory.created_at >= since,
        ).scalar()

        # Get daily usage
        daily_usage = self.db.query(
            func.date(TemplateUsageHistory.created_at),
            func.count(TemplateUsageHistory.id),
        ).filter(
            TemplateUsageHistory.template_id == template_id,
            TemplateUsageHistory.created_at >= since,
        ).group_by(func.date(TemplateUsageHistory.created_at)).all()

        return {
            "period_days": days,
            "action_counts": {action: count for action, count in action_counts},
            "unique_users": unique_users,
            "daily_usage": [
                {"date": str(date), "count": count}
                for date, count in daily_usage
            ],
        }

    # ==================== Collections ====================

    def create_collection(
        self,
        user_id: uuid.UUID,
        name: str,
        description: Optional[str] = None,
        visibility: TemplateVisibility = TemplateVisibility.PRIVATE,
        organization_id: Optional[uuid.UUID] = None,
    ) -> TemplateCollection:
        """Create a template collection."""
        slug = name.lower().replace(" ", "-")[:200]

        collection = TemplateCollection(
            user_id=user_id,
            organization_id=organization_id,
            name=name,
            description=description,
            slug=slug,
            visibility=visibility,
        )

        self.db.add(collection)
        self.db.commit()

        return collection

    def add_to_collection(
        self,
        collection_id: uuid.UUID,
        template_id: uuid.UUID,
        notes: Optional[str] = None,
    ) -> CollectionTemplate:
        """Add a template to a collection."""
        # Get max sort order
        max_order = self.db.query(func.max(CollectionTemplate.sort_order)).filter(
            CollectionTemplate.collection_id == collection_id
        ).scalar() or 0

        item = CollectionTemplate(
            collection_id=collection_id,
            template_id=template_id,
            sort_order=max_order + 1,
            notes=notes,
        )

        self.db.add(item)

        # Update collection count
        collection = self.db.query(TemplateCollection).filter(
            TemplateCollection.id == collection_id
        ).first()
        collection.template_count += 1

        self.db.commit()

        return item

    def remove_from_collection(
        self,
        collection_id: uuid.UUID,
        template_id: uuid.UUID,
    ) -> None:
        """Remove a template from a collection."""
        item = self.db.query(CollectionTemplate).filter(
            CollectionTemplate.collection_id == collection_id,
            CollectionTemplate.template_id == template_id,
        ).first()

        if item:
            self.db.delete(item)

            # Update collection count
            collection = self.db.query(TemplateCollection).filter(
                TemplateCollection.id == collection_id
            ).first()
            collection.template_count -= 1

            self.db.commit()

    def follow_collection(
        self,
        collection_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CollectionFollower:
        """Follow a collection."""
        existing = self.db.query(CollectionFollower).filter(
            CollectionFollower.collection_id == collection_id,
            CollectionFollower.user_id == user_id,
        ).first()

        if existing:
            return existing

        follower = CollectionFollower(
            collection_id=collection_id,
            user_id=user_id,
        )

        self.db.add(follower)

        # Update count
        collection = self.db.query(TemplateCollection).filter(
            TemplateCollection.id == collection_id
        ).first()
        collection.follower_count += 1

        self.db.commit()

        return follower

    def unfollow_collection(
        self,
        collection_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Unfollow a collection."""
        follower = self.db.query(CollectionFollower).filter(
            CollectionFollower.collection_id == collection_id,
            CollectionFollower.user_id == user_id,
        ).first()

        if follower:
            self.db.delete(follower)

            # Update count
            collection = self.db.query(TemplateCollection).filter(
                TemplateCollection.id == collection_id
            ).first()
            collection.follower_count -= 1

            self.db.commit()

    # ==================== Categories ====================

    def get_categories(
        self,
        parent_id: Optional[uuid.UUID] = None,
        active_only: bool = True,
    ) -> List[TemplateCategory]:
        """Get template categories."""
        query = self.db.query(TemplateCategory)

        if parent_id:
            query = query.filter(TemplateCategory.parent_id == parent_id)
        else:
            query = query.filter(TemplateCategory.parent_id.is_(None))

        if active_only:
            query = query.filter(TemplateCategory.is_active == True)

        return query.order_by(TemplateCategory.sort_order).all()

    def create_category(
        self,
        name: str,
        slug: str,
        description: Optional[str] = None,
        parent_id: Optional[uuid.UUID] = None,
        icon: Optional[str] = None,
        color: Optional[str] = None,
    ) -> TemplateCategory:
        """Create a template category."""
        category = TemplateCategory(
            name=name,
            slug=slug,
            description=description,
            parent_id=parent_id,
            icon=icon,
            color=color,
        )

        self.db.add(category)
        self.db.commit()

        return category


def get_template_library_service(db: Session) -> TemplateLibraryService:
    """Factory function to get template library service instance."""
    return TemplateLibraryService(db)
