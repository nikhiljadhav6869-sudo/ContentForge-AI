"""Preserve supported editor formatting without changing canonical evidence text."""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("artifact_versions", sa.Column("document", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("artifact_versions", "document")
