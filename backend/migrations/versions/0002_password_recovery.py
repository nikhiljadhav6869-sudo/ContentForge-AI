"""Store hashed, expiring password reset tokens and per-account request cooldowns."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "password_resets",
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.String(40), nullable=False),
        sa.Column("requested_at", sa.String(40), nullable=False),
    )


def downgrade():
    op.drop_table("password_resets")
