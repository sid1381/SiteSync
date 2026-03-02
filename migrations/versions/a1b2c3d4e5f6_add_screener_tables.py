"""Add screener tables

Revision ID: a1b2c3d4e5f6
Revises: 4e666e97cb0e
Create Date: 2025-02-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '4e666e97cb0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create screener_projects table
    op.create_table('screener_projects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('protocol_file_path', sa.String(length=500), nullable=True),
        sa.Column('protocol_criteria', sa.JSON(), nullable=True),
        sa.Column('country_weights', sa.JSON(), nullable=True),
        sa.Column('site_weights', sa.JSON(), nullable=True),
        sa.Column('site_country_ratio', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_screener_projects_id'), 'screener_projects', ['id'], unique=False)

    # Create screener_country_results table
    op.create_table('screener_country_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('country_name', sa.String(length=100), nullable=True),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('total_trials', sa.Integer(), nullable=True),
        sa.Column('indication_trials', sa.Integer(), nullable=True),
        sa.Column('site_count', sa.Integer(), nullable=True),
        sa.Column('investigator_count', sa.Integer(), nullable=True),
        sa.Column('competing_trials', sa.Integer(), nullable=True),
        sa.Column('trial_experience_score', sa.Float(), nullable=True),
        sa.Column('site_density_score', sa.Float(), nullable=True),
        sa.Column('competition_score', sa.Float(), nullable=True),
        sa.Column('regulatory_score', sa.Float(), nullable=True),
        sa.Column('prevalence_score', sa.Float(), nullable=True),
        sa.Column('composite_score', sa.Float(), nullable=True),
        sa.Column('regulatory_summary', sa.Text(), nullable=True),
        sa.Column('prevalence_estimate', sa.Text(), nullable=True),
        sa.Column('data_sources', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['screener_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create screener_site_results table
    op.create_table('screener_site_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('country_code', sa.String(length=10), nullable=True),
        sa.Column('site_name', sa.String(length=500), nullable=True),
        sa.Column('city', sa.String(length=200), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('pi_name', sa.String(length=255), nullable=True),
        sa.Column('pi_publications', sa.Integer(), nullable=True),
        sa.Column('total_trials', sa.Integer(), nullable=True),
        sa.Column('indication_trials', sa.Integer(), nullable=True),
        sa.Column('phase_match_trials', sa.Integer(), nullable=True),
        sa.Column('completed_trials', sa.Integer(), nullable=True),
        sa.Column('terminated_trials', sa.Integer(), nullable=True),
        sa.Column('recruiting_trials', sa.Integer(), nullable=True),
        sa.Column('fda_inspections', sa.Integer(), nullable=True),
        sa.Column('fda_warnings', sa.Integer(), nullable=True),
        sa.Column('is_debarred', sa.Boolean(), nullable=True),
        sa.Column('experience_score', sa.Float(), nullable=True),
        sa.Column('pi_strength_score', sa.Float(), nullable=True),
        sa.Column('capacity_score', sa.Float(), nullable=True),
        sa.Column('compliance_score', sa.Float(), nullable=True),
        sa.Column('protocol_match_score', sa.Float(), nullable=True),
        sa.Column('site_composite_score', sa.Float(), nullable=True),
        sa.Column('final_score', sa.Float(), nullable=True),
        sa.Column('gap_analysis', sa.Text(), nullable=True),
        sa.Column('red_flags', sa.JSON(), nullable=True),
        sa.Column('is_shortlisted', sa.Boolean(), nullable=True),
        sa.Column('data_sources', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['screener_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('screener_site_results')
    op.drop_table('screener_country_results')
    op.drop_index(op.f('ix_screener_projects_id'), table_name='screener_projects')
    op.drop_table('screener_projects')
