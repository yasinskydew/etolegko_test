"""initial schema: enums, tables, geo seed, admin user

Revision ID: 20261119185515
Revises:
Create Date: 2026-11-19 18:55:15
"""

from __future__ import annotations

import os
from typing import Sequence, Union

import bcrypt
import sqlalchemy as sa
from alembic import op

revision: str = "20261119185515"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GEO_SEED: list[tuple[str, str]] = [
    ("MX", "Mexico"),
    ("AU", "Australia"),
    ("RO", "Romania"),
    ("US", "United States"),
    ("GB", "United Kingdom"),
    ("DE", "Germany"),
    ("FR", "France"),
    ("IT", "Italy"),
    ("ES", "Spain"),
    ("BR", "Brazil"),
    ("IN", "India"),
    ("ID", "Indonesia"),
    ("PH", "Philippines"),
    ("TH", "Thailand"),
    ("VN", "Vietnam"),
    ("PL", "Poland"),
    ("UA", "Ukraine"),
    ("KZ", "Kazakhstan"),
    ("TR", "Turkey"),
    ("CA", "Canada"),
    ("AR", "Argentina"),
    ("CL", "Chile"),
    ("CO", "Colombia"),
    ("PE", "Peru"),
    ("NL", "Netherlands"),
    ("BE", "Belgium"),
    ("AT", "Austria"),
    ("CH", "Switzerland"),
    ("SE", "Sweden"),
    ("NO", "Norway"),
    ("DK", "Denmark"),
    ("FI", "Finland"),
    ("PT", "Portugal"),
    ("CZ", "Czechia"),
    ("HU", "Hungary"),
    ("GR", "Greece"),
    ("IE", "Ireland"),
    ("NZ", "New Zealand"),
    ("SG", "Singapore"),
    ("MY", "Malaysia"),
    ("JP", "Japan"),
    ("KR", "South Korea"),
    ("TW", "Taiwan"),
    ("HK", "Hong Kong"),
    ("AE", "United Arab Emirates"),
    ("SA", "Saudi Arabia"),
    ("EG", "Egypt"),
    ("ZA", "South Africa"),
    ("NG", "Nigeria"),
    ("KE", "Kenya"),
]


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def upgrade() -> None:
    company_lifecycle = sa.Enum(
        "creating", "ready", name="company_lifecycle", create_type=False
    )
    traffic_status = sa.Enum(
        "active", "disabled", name="traffic_status", create_type=False
    )
    stream_type = sa.Enum(
        "google", "offers", "plain", name="stream_type", create_type=False
    )
    sa.Enum("creating", "ready", name="company_lifecycle").create(
        op.get_bind(), checkfirst=False
    )
    sa.Enum("active", "disabled", name="traffic_status").create(
        op.get_bind(), checkfirst=False
    )
    sa.Enum("google", "offers", "plain", name="stream_type").create(
        op.get_bind(), checkfirst=False
    )

    op.create_table(
        "user",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "geo",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
    )

    op.create_table(
        "company",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("keitaro_campaign_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "traffic_status",
            traffic_status,
            server_default="active",
            nullable=False,
        ),
        sa.Column("lifecycle", company_lifecycle, nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "company_name_lower_uidx",
        "company",
        [sa.text("lower(name)")],
        unique=True,
    )
    op.create_index(
        "company_keitaro_campaign_uidx",
        "company",
        ["keitaro_campaign_id"],
        unique=True,
        postgresql_where=sa.text("keitaro_campaign_id IS NOT NULL"),
    )

    op.create_table(
        "company_geo",
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("geo_code", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 1", name="company_geo_position_check"),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["geo_code"], ["geo.code"]),
        sa.PrimaryKeyConstraint("company_id", "geo_code"),
    )
    op.create_index(
        "company_geo_position_uidx",
        "company_geo",
        ["company_id", "position"],
        unique=True,
    )

    op.create_table(
        "idempotency_key",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"]),
    )

    op.create_table(
        "stream",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("type", stream_type, nullable=False),
        sa.Column("keitaro_stream_id", sa.BigInteger(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position >= 1", name="stream_position_check"),
        sa.ForeignKeyConstraint(["company_id"], ["company.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "stream_keitaro_uidx",
        "stream",
        ["keitaro_stream_id"],
        unique=True,
        postgresql_where=sa.text("keitaro_stream_id IS NOT NULL"),
    )
    op.create_index(
        "stream_one_google_uidx",
        "stream",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("type = 'google'"),
    )
    op.create_index(
        "stream_one_offers_uidx",
        "stream",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("type = 'offers'"),
    )
    op.create_index(
        "stream_position_uidx",
        "stream",
        ["company_id", "position"],
        unique=True,
    )

    op.create_table(
        "stream_offer",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("stream_id", sa.BigInteger(), nullable=False),
        sa.Column("offer_id", sa.BigInteger(), nullable=False),
        sa.Column("percent", sa.SmallInteger(), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("removed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "percent >= 0 AND percent <= 100",
            name="stream_offer_percent_check",
        ),
        sa.CheckConstraint("position >= 1", name="stream_offer_position_check"),
        sa.ForeignKeyConstraint(["stream_id"], ["stream.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "stream_offer_uidx",
        "stream_offer",
        ["stream_id", "offer_id"],
        unique=True,
    )
    op.create_index(
        "stream_offer_position_uidx",
        "stream_offer",
        ["stream_id", "position"],
        unique=True,
    )

    op.create_table(
        "stream_offer_snapshot",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), primary_key=True),
        sa.Column("stream_id", sa.BigInteger(), nullable=False),
        sa.Column("offer_id", sa.BigInteger(), nullable=False),
        sa.Column("percent", sa.SmallInteger(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("removed", sa.Boolean(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "percent >= 0 AND percent <= 100",
            name="stream_offer_snapshot_percent_check",
        ),
        sa.CheckConstraint("position >= 1", name="stream_offer_snapshot_position_check"),
        sa.ForeignKeyConstraint(["stream_id"], ["stream.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "stream_offer_snapshot_uidx",
        "stream_offer_snapshot",
        ["stream_id", "offer_id"],
        unique=True,
    )
    op.create_index(
        "stream_offer_snapshot_position_uidx",
        "stream_offer_snapshot",
        ["stream_id", "position"],
        unique=True,
    )

    geo_table = sa.table(
        "geo",
        sa.column("code", sa.Text),
        sa.column("name", sa.Text),
    )
    op.bulk_insert(
        geo_table,
        [{"code": code, "name": name} for code, name in GEO_SEED],
    )

    username = os.environ.get("ADMIN_USERNAME") or "admin"
    password = os.environ.get("ADMIN_PASSWORD") or "changeme"
    user_table = sa.table(
        "user",
        sa.column("username", sa.Text),
        sa.column("password_hash", sa.Text),
    )
    op.bulk_insert(
        user_table,
        [{"username": username, "password_hash": _hash_password(password)}],
    )


def downgrade() -> None:
    op.drop_index("stream_offer_snapshot_position_uidx", table_name="stream_offer_snapshot")
    op.drop_index("stream_offer_snapshot_uidx", table_name="stream_offer_snapshot")
    op.drop_table("stream_offer_snapshot")
    op.drop_index("stream_offer_position_uidx", table_name="stream_offer")
    op.drop_index("stream_offer_uidx", table_name="stream_offer")
    op.drop_table("stream_offer")
    op.drop_index("stream_position_uidx", table_name="stream")
    op.drop_index("stream_one_offers_uidx", table_name="stream")
    op.drop_index("stream_one_google_uidx", table_name="stream")
    op.drop_index("stream_keitaro_uidx", table_name="stream")
    op.drop_table("stream")
    op.drop_table("idempotency_key")
    op.drop_index("company_geo_position_uidx", table_name="company_geo")
    op.drop_table("company_geo")
    op.drop_index("company_keitaro_campaign_uidx", table_name="company")
    op.drop_index("company_name_lower_uidx", table_name="company")
    op.drop_table("company")
    op.drop_table("geo")
    op.drop_table("user")
    sa.Enum(name="stream_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="traffic_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="company_lifecycle").drop(op.get_bind(), checkfirst=True)
