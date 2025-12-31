"""Add jobs table for background task tracking

Revision ID: 003
Revises: 002
Create Date: 2025-12-31

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create job status enum
    job_status_enum = postgresql.ENUM(
        'pending', 'processing', 'completed', 'failed', 'cancelled', 'retrying',
        name='jobstatus',
        create_type=True
    )
    job_status_enum.create(op.get_bind(), checkfirst=True)

    # Create job type enum
    job_type_enum = postgresql.ENUM(
        'pdf_extract', 'pdf_classify', 'excel_export', 'batch_process',
        name='jobtype',
        create_type=True
    )
    job_type_enum.create(op.get_bind(), checkfirst=True)

    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('celery_task_id', sa.String(255), nullable=True),
        sa.Column('job_type', sa.Enum('pdf_extract', 'pdf_classify', 'excel_export', 'batch_process', name='jobtype', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', 'cancelled', 'retrying', name='jobstatus', create_type=False), nullable=False, server_default='pending'),

        # Progress tracking
        sa.Column('progress', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_step', sa.String(255), nullable=True),
        sa.Column('total_steps', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('completed_steps', sa.Integer(), nullable=False, server_default='0'),

        # Input/Output
        sa.Column('input_data', postgresql.JSONB(), nullable=True),
        sa.Column('result_data', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Relationships
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Retry tracking
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    )

    # Create indexes
    op.create_index('ix_jobs_celery_task_id', 'jobs', ['celery_task_id'], unique=True)
    op.create_index('ix_jobs_user_id', 'jobs', ['user_id'])
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_created_at', 'jobs', ['created_at'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_jobs_created_at', 'jobs')
    op.drop_index('ix_jobs_status', 'jobs')
    op.drop_index('ix_jobs_user_id', 'jobs')
    op.drop_index('ix_jobs_celery_task_id', 'jobs')

    # Drop table
    op.drop_table('jobs')

    # Drop enums
    sa.Enum(name='jobtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='jobstatus').drop(op.get_bind(), checkfirst=True)
