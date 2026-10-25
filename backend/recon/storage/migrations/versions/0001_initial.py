"""Initial local analysis, jobs, comparisons and experiments schema."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "binaries",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("artifact_path", sa.String()),
        sa.Column("artifact_hash", sa.String()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.String(), nullable=False),
    )
    op.create_table(
        "functions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "binary_id",
            sa.String(32),
            sa.ForeignKey("binaries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("address", sa.BigInteger(), nullable=False),
        sa.Column("end_address", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("discovery_method", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("instruction_count", sa.Integer(), nullable=False),
        sa.Column("block_count", sa.Integer(), nullable=False),
        sa.Column("artifact_index", sa.Integer(), nullable=False),
    )
    op.create_index("ix_functions_binary_id", "functions", ["binary_id"])
    op.create_index("ix_functions_name", "functions", ["name"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("error_code", sa.String()),
        sa.Column("error", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("finished_at", sa.String()),
        sa.Column("config_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_jobs_state", "jobs", ["state"])
    op.create_table(
        "comparisons",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column(
            "source_binary_id",
            sa.String(32),
            sa.ForeignKey("binaries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_binary_id",
            sa.String(32),
            sa.ForeignKey("binaries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("artifact_path", sa.String()),
        sa.Column("artifact_hash", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("artifact_path", sa.String()),
        sa.Column("artifact_hash", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    for name in ["experiments", "comparisons", "jobs", "functions", "binaries"]:
        op.drop_table(name)
