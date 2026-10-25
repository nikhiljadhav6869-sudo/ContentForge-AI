"""Record email ownership without changing existing credentials or access."""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("email_verified_at", sa.String(40), nullable=True))
    op.create_table(
        "email_verifications",
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.String(40), nullable=False),
        sa.Column("requested_at", sa.String(40), nullable=False),
    )


def downgrade():
    op.drop_table("email_verifications")
    op.drop_column("users", "email_verified_at")
