"""tablero planeacion

Revisión: 0003
Anterior: 0002
Fecha: 2026-11-12 14:30:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '0003'
down_revision: str | Sequence[str] | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'items_planeacion',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('responsable', sa.String(length=120), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('categoria_id', sa.Integer(), nullable=True),
        sa.Column('dia_semana', sa.Integer(), nullable=True),
        sa.Column('fecha_semana', sa.Date(), nullable=False),
        sa.Column('prioridad', sa.String(length=20), nullable=False),
        sa.Column('tiempo_estimado_min', sa.Integer(), nullable=True),
        sa.Column('completado', sa.Boolean(), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column('creado_en', sa.DateTime(), nullable=False),
        sa.Column('completado_en', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "prioridad IS NULL OR prioridad IN ('minima', 'normal', 'maxima')",
            name=op.f('ck_items_planeacion_prioridad'),
        ),
        sa.ForeignKeyConstraint(
            ['categoria_id'],
            ['categorias.id'],
            name=op.f('fk_items_planeacion_categoria_id_categorias'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_items_planeacion')),
    )
    with op.batch_alter_table('items_planeacion', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_items_planeacion_semana'),
            ['fecha_semana'],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('items_planeacion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_items_planeacion_semana'))

    op.drop_table('items_planeacion')
