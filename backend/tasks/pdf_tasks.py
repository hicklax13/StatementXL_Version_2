"""
PDF processing background tasks.

Celery tasks for extracting, classifying, and exporting financial data from PDFs.
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import structlog
from celery import shared_task
from sqlalchemy.orm import Session

from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.models.job import Job, JobStatus, JobType

logger = structlog.get_logger(__name__)


def get_db_session() -> Session:
    """Get a database session for use in Celery tasks."""
    return SessionLocal()


def update_job_progress(
    db: Session,
    job_id: str,
    progress: float,
    current_step: str = None
) -> None:
    """Update job progress in database."""
    try:
        job_uuid = uuid.UUID(job_id)
        job = db.query(Job).filter(Job.id == job_uuid).first()
        if job:
            job.update_progress(progress, current_step)
            db.commit()
    except Exception as e:
        logger.error("failed_to_update_job_progress", job_id=job_id, error=str(e))


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_pdf(
    self,
    job_id: str,
    document_id: str,
    user_id: str,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a PDF document - extract tables and classify line items.

    Args:
        job_id: UUID of the job record
        document_id: UUID of the document to process
        user_id: UUID of the user who initiated the job
        options: Optional processing options

    Returns:
        Dict with processing results
    """
    db = get_db_session()
    options = options or {}

    try:
        # Get job and mark as processing
        job_uuid = uuid.UUID(job_id)
        job = db.query(Job).filter(Job.id == job_uuid).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.celery_task_id = self.request.id
        job.mark_processing()
        db.commit()

        logger.info("pdf_processing_started", job_id=job_id, document_id=document_id)

        # Step 1: Load document (10%)
        update_job_progress(db, job_id, 0.1, "Loading document")

        from backend.models.document import Document
        doc_uuid = uuid.UUID(document_id)
        document = db.query(Document).filter(Document.id == doc_uuid).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Step 2: Extract tables (40%)
        update_job_progress(db, job_id, 0.2, "Extracting tables")

        from backend.services.table_detector import get_table_detector
        detector = get_table_detector()

        # Read PDF file
        import os
        from backend.config import get_settings
        settings = get_settings()
        pdf_path = os.path.join(str(settings.upload_dir), document.filename)

        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        tables = detector.extract_tables(pdf_path)
        update_job_progress(db, job_id, 0.4, f"Extracted {len(tables)} tables")

        # Step 3: Classify line items (70%)
        update_job_progress(db, job_id, 0.5, "Classifying line items")

        from backend.services.gaap_classifier import get_classifier
        classifier = get_classifier()

        classified_items = []
        total_items = sum(len(table.rows) for table in tables)
        processed_items = 0

        for table in tables:
            for row in table.rows:
                # Get text from first cell for classification
                if row.cells and row.cells[0].value:
                    text = str(row.cells[0].value)
                    classification = classifier.classify(text)
                    classified_items.append({
                        "text": text,
                        "label": classification.get("label", "Unknown"),
                        "confidence": classification.get("confidence", 0.0),
                    })
                    processed_items += 1

                # Update progress periodically
                if processed_items % 10 == 0:
                    progress = 0.5 + (0.2 * processed_items / max(total_items, 1))
                    update_job_progress(db, job_id, progress, f"Classified {processed_items}/{total_items} items")

        update_job_progress(db, job_id, 0.7, "Classification complete")

        # Step 4: Detect statement type (80%)
        update_job_progress(db, job_id, 0.8, "Detecting statement type")

        # Combine all text for statement type detection
        all_text = " ".join([item["text"] for item in classified_items])
        statement_types = classifier.detect_all_statement_types(all_text)

        primary_type = statement_types[0]["statement_type"] if statement_types else "income_statement"

        # Step 5: Save results (90%)
        update_job_progress(db, job_id, 0.9, "Saving results")

        result_data = {
            "document_id": document_id,
            "tables_count": len(tables),
            "items_count": len(classified_items),
            "statement_types": statement_types,
            "primary_statement": primary_type,
            "classified_items_sample": classified_items[:20],  # First 20 for preview
        }

        # Update document status
        document.status = "processed"
        db.commit()

        # Step 6: Complete (100%)
        job.mark_completed(result_data)
        db.commit()

        logger.info(
            "pdf_processing_completed",
            job_id=job_id,
            document_id=document_id,
            tables=len(tables),
            items=len(classified_items),
        )

        return result_data

    except Exception as e:
        logger.error(
            "pdf_processing_failed",
            job_id=job_id,
            document_id=document_id,
            error=str(e),
        )

        # Mark job as failed
        job = db.query(Job).filter(Job.id == uuid.UUID(job_id)).first()
        if job:
            if job.should_retry():
                job.increment_retry()
                db.commit()
                # Retry the task
                raise self.retry(exc=e)
            else:
                job.mark_failed(str(e))
                db.commit()

        raise

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def export_excel(
    self,
    job_id: str,
    document_id: str,
    user_id: str,
    export_options: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Export processed document data to Excel template.

    Args:
        job_id: UUID of the job record
        document_id: UUID of the document
        user_id: UUID of the user
        export_options: Export configuration (style, colorway, etc.)

    Returns:
        Dict with export results including download URL
    """
    db = get_db_session()

    try:
        # Get job and mark as processing
        job_uuid = uuid.UUID(job_id)
        job = db.query(Job).filter(Job.id == job_uuid).first()
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.celery_task_id = self.request.id
        job.mark_processing()
        db.commit()

        logger.info("excel_export_started", job_id=job_id, document_id=document_id)

        # Step 1: Load document and extractions
        update_job_progress(db, job_id, 0.1, "Loading document data")

        from backend.models.document import Document
        doc_uuid = uuid.UUID(document_id)
        document = db.query(Document).filter(Document.id == doc_uuid).first()
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Step 2: Generate Excel file
        update_job_progress(db, job_id, 0.3, "Generating Excel template")

        from backend.services.template_parser import get_template_parser
        from backend.services.template_populator import get_template_populator

        statement_type = export_options.get("statement_type", "income_statement")
        style = export_options.get("style", "basic")
        colorway = export_options.get("colorway", "default")

        # Get template
        parser = get_template_parser()
        template_path = parser.get_template_path(statement_type, style)

        # Populate template
        update_job_progress(db, job_id, 0.5, "Populating template with data")

        populator = get_template_populator()
        # This would use the actual extraction data
        # For now, returning a placeholder result

        update_job_progress(db, job_id, 0.8, "Saving Excel file")

        # Generate output filename
        import secrets
        export_id = secrets.token_hex(8)
        output_filename = f"export_{export_id}.xlsx"

        result_data = {
            "export_id": export_id,
            "filename": output_filename,
            "download_url": f"/api/v1/export/download/{export_id}",
            "style": style,
            "colorway": colorway,
            "statement_type": statement_type,
        }

        # Complete job
        job.mark_completed(result_data)
        db.commit()

        logger.info(
            "excel_export_completed",
            job_id=job_id,
            document_id=document_id,
            export_id=export_id,
        )

        return result_data

    except Exception as e:
        logger.error(
            "excel_export_failed",
            job_id=job_id,
            document_id=document_id,
            error=str(e),
        )

        job = db.query(Job).filter(Job.id == uuid.UUID(job_id)).first()
        if job:
            if job.should_retry():
                job.increment_retry()
                db.commit()
                raise self.retry(exc=e)
            else:
                job.mark_failed(str(e))
                db.commit()

        raise

    finally:
        db.close()


@celery_app.task
def cleanup_expired_jobs() -> Dict[str, int]:
    """
    Periodic task to clean up old completed/failed jobs.

    Runs hourly via Celery Beat.

    Returns:
        Dict with cleanup statistics
    """
    db = get_db_session()

    try:
        # Delete jobs older than 7 days that are completed/failed
        cutoff_date = datetime.utcnow() - timedelta(days=7)

        deleted_count = (
            db.query(Job)
            .filter(
                Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]),
                Job.created_at < cutoff_date,
            )
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info("job_cleanup_completed", deleted_count=deleted_count)

        return {"deleted_jobs": deleted_count}

    except Exception as e:
        logger.error("job_cleanup_failed", error=str(e))
        db.rollback()
        raise

    finally:
        db.close()
