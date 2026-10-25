"""Persist daily workflow admission counts per workspace."""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspace_usage",
        sa.Column("workspace_id", sa.String(32), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("day", sa.String(10), primary_key=True),
        sa.Column("generation_attempts", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("workspace_usage")
