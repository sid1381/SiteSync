"""Add survey and survey response tables

Revision ID: bfe077b4b23f
Revises: 
Create Date: 2025-09-27 14:23:11.946230

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bfe077b4b23f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create surveys table
    op.create_table('surveys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('site_id', sa.Integer(), nullable=True),
    sa.Column('sponsor_name', sa.String(length=255), nullable=True),
    sa.Column('study_name', sa.String(length=255), nullable=True),
    sa.Column('study_type', sa.String(length=100), nullable=True),
    sa.Column('nct_number', sa.String(length=50), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('protocol_file_path', sa.String(length=500), nullable=True),
    sa.Column('survey_file_path', sa.String(length=500), nullable=True),
    sa.Column('survey_format', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('protocol_extracted_data', sa.JSON(), nullable=True),
    sa.Column('survey_questions', sa.JSON(), nullable=True),
    sa.Column('feasibility_score', sa.Integer(), nullable=True),
    sa.Column('score_breakdown', sa.JSON(), nullable=True),
    sa.Column('flags', sa.JSON(), nullable=True),
    sa.Column('autofilled_responses', sa.JSON(), nullable=True),
    sa.Column('completion_percentage', sa.Float(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(), nullable=True),
    sa.Column('submitted_to_email', sa.String(length=255), nullable=True),
    sa.Column('export_pdf_path', sa.String(length=500), nullable=True),
    sa.Column('export_excel_path', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Create survey_responses table
    op.create_table('survey_responses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('survey_id', sa.Integer(), nullable=True),
    sa.Column('question_id', sa.String(length=50), nullable=True),
    sa.Column('question_text', sa.Text(), nullable=True),
    sa.Column('question_type', sa.String(length=50), nullable=True),
    sa.Column('is_objective', sa.Boolean(), nullable=True),
    sa.Column('response_value', sa.Text(), nullable=True),
    sa.Column('response_source', sa.String(length=50), nullable=True),
    sa.Column('confidence_score', sa.Float(), nullable=True),
    sa.Column('manually_edited', sa.Boolean(), nullable=True),
    sa.Column('edited_by', sa.String(length=255), nullable=True),
    sa.Column('edited_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['survey_id'], ['surveys.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('survey_responses')
    op.drop_table('surveys')
