"""Modelos de la base de datos (SQLAlchemy 2.0, SQLite local).

Sigue la sección 9 del plan v0.5, con los ajustes aprobados en la Fase 1
(ver ``docs/decisiones.md``):

1. ``pausas`` tiene ``jornada_id`` y su ``actividad_id`` es opcional, para poder
   registrar el almuerzo u otras pausas sin una actividad en curso.
2. Nueva tabla ``ediciones_log`` para la trazabilidad de correcciones (RF-07).
3. ``actividades`` tiene ``creada_en`` y ``finalizada_en``.
4. Estado ``eliminada`` en actividades (borrado lógico, para no perder historial).

Convenciones:
- Fechas y horas en hora local de Colombia, sin zona horaria (no hay horario de
  verano). Ver ``data.tiempo.ahora()``.
- Los campos de tipo "enumeración" se guardan como TEXT y se validan con CHECK
  usando los valores de ``data.enums``.
- Duraciones en segundos (``*_seg``) o minutos (``*_min``) según el nombre.
"""

from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from data.enums import (
    CanalSolicitud,
    EstadoActividad,
    EstadoAprobacion,
    EstadoJornada,
    Lugar,
    MotivoRevision,
    Prioridad,
    Recurrencia,
    RespuestaRecordatorio,
    TipoActividad,
    TipoCopia,
    TipoPausa,
    TipoRevision,
    TipoSolicitante,
)
from data.tiempo import ahora

# Nombres de restricciones estables: necesarios para que Alembic pueda
# modificar tablas en SQLite (modo "batch") sin ambigüedades.
CONVENCION_NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Clase base de todos los modelos."""

    metadata = MetaData(naming_convention=CONVENCION_NOMBRES)


def _check_enum(columna: str, enum: type[StrEnum], nombre: str | None = None) -> CheckConstraint:
    """Crea un CHECK que limita ``columna`` a los valores del enum (o NULL)."""
    valores = ", ".join(f"'{m.value}'" for m in enum)
    return CheckConstraint(
        f"{columna} IS NULL OR {columna} IN ({valores})",
        name=nombre or columna,
    )


# ---------------------------------------------------------------------------
# Configuración y catálogos
# ---------------------------------------------------------------------------


class Usuario(Base):
    """Usuario de la app en este PC (la app es de uso individual)."""

    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), default="")
    tema: Mapped[str] = mapped_column(String(40), default="claro")
    #: Hash del PIN opcional; ``None`` si el usuario no usa PIN.
    pin_hash: Mapped[str | None] = mapped_column(String(255))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class Horario(Base):
    """Bloque de horario laboral de un día de la semana (sección 6.1)."""

    __tablename__ = "horarios"
    __table_args__ = (
        UniqueConstraint("dia_semana", "bloque", name="dia_bloque"),
        CheckConstraint("dia_semana BETWEEN 0 AND 6", name="dia_semana"),
        CheckConstraint("bloque >= 1", name="bloque"),
        CheckConstraint("hora_inicio < hora_fin", name="rango_horas"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    #: 0 = lunes ... 6 = domingo (igual que ``date.weekday()``).
    dia_semana: Mapped[int] = mapped_column(Integer)
    bloque: Mapped[int] = mapped_column(Integer, default=1)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)


class Categoria(Base):
    """Categoría libre creada por el usuario (flyers, animaciones, etc.)."""

    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    color: Mapped[str] = mapped_column(String(9), default="#6B7280")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Solicitante(Base):
    """Persona que pide actividades extra o revisiones (RF-03)."""

    __tablename__ = "solicitantes"
    __table_args__ = (
        _check_enum("tipo", TipoSolicitante),
        _check_enum("prioridad_defecto", Prioridad),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True)
    tipo: Mapped[str] = mapped_column(String(20))
    prioridad_defecto: Mapped[str] = mapped_column(String(20), default=Prioridad.NORMAL.value)
    requiere_aprobacion: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Permite ocultar un solicitante sin borrar su historial.
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Plantilla(Base):
    """Actividad frecuente o recurrente que se propone al planear el día."""

    __tablename__ = "plantillas"
    __table_args__ = (_check_enum("recurrencia", Recurrencia),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(160))
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id", ondelete="SET NULL"))
    tiempo_estimado_min: Mapped[int | None] = mapped_column(Integer)
    recurrencia: Mapped[str] = mapped_column(String(20), default=Recurrencia.NINGUNA.value)
    #: Días separados por coma, ej. ``"0,1,2,3,4"`` (solo si recurrencia = dias_semana).
    dias_semana: Mapped[str | None] = mapped_column(String(20))
    intervalo_recordatorio_min: Mapped[int | None] = mapped_column(Integer)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)

    categoria: Mapped[Categoria | None] = relationship()


class Configuracion(Base):
    """Parámetros clave-valor (pesos de la fórmula, meta, sonido, etc.)."""

    __tablename__ = "configuracion"

    clave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Jornadas y actividades
# ---------------------------------------------------------------------------


class Jornada(Base):
    """Un día de trabajo. Se crea al iniciar la primera actividad del día."""

    __tablename__ = "jornadas"
    __table_args__ = (_check_enum("estado", EstadoJornada),)

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Única: la app es de un solo usuario por PC.
    fecha: Mapped[date] = mapped_column(Date, unique=True)
    hora_inicio: Mapped[datetime | None] = mapped_column(DateTime)
    hora_fin: Mapped[datetime | None] = mapped_column(DateTime)
    #: Falso si el día no tiene horario (domingo, festivo): sin porcentaje.
    es_laboral: Mapped[bool] = mapped_column(Boolean, default=True)
    duracion_jornada_seg: Mapped[int] = mapped_column(Integer, default=0)
    #: Porcentaje 0-100; ``None`` en días no laborales o jornada abierta.
    productividad: Mapped[float | None] = mapped_column(Float)
    tiempo_efectivo_seg: Mapped[int] = mapped_column(Integer, default=0)
    estado: Mapped[str] = mapped_column(String(20), default=EstadoJornada.ABIERTA.value)

    actividades: Mapped[list[Actividad]] = relationship(back_populates="jornada")
    pausas: Mapped[list[Pausa]] = relationship(back_populates="jornada")


class Actividad(Base):
    """Actividad (o pieza, o revisión) con su cronómetro.

    Una actividad arrastrada pertenece a la jornada en que se creó; el tiempo
    de cada día se calcula a partir de sus ``sesiones_tiempo``.
    """

    __tablename__ = "actividades"
    __table_args__ = (
        _check_enum("tipo", TipoActividad),
        _check_enum("prioridad", Prioridad),
        _check_enum("estado", EstadoActividad),
        _check_enum("revision_tipo", TipoRevision),
        _check_enum("revision_motivo", MotivoRevision),
        _check_enum("canal_solicitud", CanalSolicitud),
        _check_enum("aprobacion_canal", CanalSolicitud),
        _check_enum("aprobacion_estado", EstadoAprobacion),
        CheckConstraint("avance_pct IS NULL OR avance_pct BETWEEN 0 AND 100", name="avance_pct"),
        CheckConstraint(
            "editado = 0 OR (editado_motivo IS NOT NULL AND TRIM(editado_motivo) <> '')",
            name="editado_motivo",
        ),
        CheckConstraint(
            "es_revision = 0 OR actividad_padre_id IS NOT NULL", name="revision_padre"
        ),
        Index("ix_actividades_jornada_estado", "jornada_id", "estado"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    jornada_id: Mapped[int] = mapped_column(ForeignKey("jornadas.id", ondelete="RESTRICT"))
    categoria_id: Mapped[int | None] = mapped_column(ForeignKey("categorias.id", ondelete="SET NULL"))
    plantilla_id: Mapped[int | None] = mapped_column(ForeignKey("plantillas.id", ondelete="SET NULL"))

    nombre: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(20), default=TipoActividad.PLANEADA.value)
    solicitante_id: Mapped[int | None] = mapped_column(ForeignKey("solicitantes.id", ondelete="SET NULL"))
    prioridad: Mapped[str] = mapped_column(String(20), default=Prioridad.NORMAL.value)
    estado: Mapped[str] = mapped_column(String(20), default=EstadoActividad.PENDIENTE.value)

    # Revisiones (RF-03b)
    actividad_padre_id: Mapped[int | None] = mapped_column(ForeignKey("actividades.id", ondelete="RESTRICT"))
    es_revision: Mapped[bool] = mapped_column(Boolean, default=False)
    revision_solicitante_id: Mapped[int | None] = mapped_column(
        ForeignKey("solicitantes.id", ondelete="SET NULL")
    )
    revision_tipo: Mapped[str | None] = mapped_column(String(20))
    revision_que_cambiar: Mapped[str | None] = mapped_column(Text)
    revision_motivo: Mapped[str | None] = mapped_column(String(30))

    # Reasignación (RF-03c)
    reasignada_a: Mapped[str | None] = mapped_column(String(120))
    reasignacion_motivo: Mapped[str | None] = mapped_column(Text)

    # Corrección manual (RF-07)
    editado: Mapped[bool] = mapped_column(Boolean, default=False)
    editado_motivo: Mapped[str | None] = mapped_column(Text)

    tiempo_estimado_min: Mapped[int | None] = mapped_column(Integer)
    notas: Mapped[str | None] = mapped_column(Text)
    descripcion: Mapped[str | None] = mapped_column(Text)

    # Extras (RF-03)
    motivo_urgencia: Mapped[str | None] = mapped_column(Text)
    fecha_limite: Mapped[datetime | None] = mapped_column(DateTime)
    canal_solicitud: Mapped[str | None] = mapped_column(String(20))
    aprobacion_estado: Mapped[str] = mapped_column(String(20), default=EstadoAprobacion.NO_REQUERIDA.value)
    aprobacion_fecha: Mapped[datetime | None] = mapped_column(DateTime)
    aprobacion_canal: Mapped[str | None] = mapped_column(String(20))

    avance_pct: Mapped[int | None] = mapped_column(Integer)
    intervalo_recordatorio_min: Mapped[int | None] = mapped_column(Integer)

    creada_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    finalizada_en: Mapped[datetime | None] = mapped_column(DateTime)

    jornada: Mapped[Jornada] = relationship(back_populates="actividades")
    categoria: Mapped[Categoria | None] = relationship()
    plantilla: Mapped[Plantilla | None] = relationship()
    solicitante: Mapped[Solicitante | None] = relationship(foreign_keys=[solicitante_id])
    revision_solicitante: Mapped[Solicitante | None] = relationship(foreign_keys=[revision_solicitante_id])
    actividad_padre: Mapped[Actividad | None] = relationship(
        remote_side=[id], back_populates="revisiones"
    )
    revisiones: Mapped[list[Actividad]] = relationship(back_populates="actividad_padre")
    sesiones: Mapped[list[SesionTiempo]] = relationship(
        back_populates="actividad", cascade="all, delete-orphan", order_by="SesionTiempo.inicio"
    )
    pausas: Mapped[list[Pausa]] = relationship(back_populates="actividad", order_by="Pausa.inicio")
    recordatorios: Mapped[list[RecordatorioLog]] = relationship(
        back_populates="actividad", cascade="all, delete-orphan"
    )


class SesionTiempo(Base):
    """Un tramo continuo de cronómetro de una actividad."""

    __tablename__ = "sesiones_tiempo"
    __table_args__ = (
        _check_enum("lugar", Lugar),
        CheckConstraint("fin IS NULL OR fin >= inicio", name="rango"),
        Index("ix_sesiones_tiempo_inicio", "inicio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades.id", ondelete="CASCADE"), index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime)
    #: ``None`` mientras el cronómetro está corriendo.
    fin: Mapped[datetime | None] = mapped_column(DateTime)
    duracion_seg: Mapped[int] = mapped_column(Integer, default=0)
    #: No cuenta en el porcentaje del día (RF-05b).
    fuera_horario: Mapped[bool] = mapped_column(Boolean, default=False)
    lugar: Mapped[str] = mapped_column(String(20), default=Lugar.OFICINA.value)

    actividad: Mapped[Actividad] = relationship(back_populates="sesiones")


class Pausa(Base):
    """Pausa de una actividad, o pausa general de la jornada (ej. almuerzo)."""

    __tablename__ = "pausas"
    __table_args__ = (
        _check_enum("tipo", TipoPausa),
        CheckConstraint("fin IS NULL OR fin >= inicio", name="rango"),
        CheckConstraint("avance_pct IS NULL OR avance_pct BETWEEN 0 AND 100", name="avance_pct"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    jornada_id: Mapped[int] = mapped_column(ForeignKey("jornadas.id", ondelete="RESTRICT"), index=True)
    #: Opcional: el almuerzo puede registrarse sin actividad en curso.
    actividad_id: Mapped[int | None] = mapped_column(ForeignKey("actividades.id", ondelete="CASCADE"), index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime)
    fin: Mapped[datetime | None] = mapped_column(DateTime)
    motivo: Mapped[str | None] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(20), default=TipoPausa.OTRO.value)
    #: Las pausas por causa externa no penalizan el Foco.
    es_externa: Mapped[bool] = mapped_column(Boolean, default=False)
    #: Solo en pausas de fin de jornada.
    avance_pct: Mapped[int | None] = mapped_column(Integer)

    jornada: Mapped[Jornada] = relationship(back_populates="pausas")
    actividad: Mapped[Actividad | None] = relationship(back_populates="pausas")


class RecordatorioLog(Base):
    """Registro de cada aviso "¿Sigues con...?" y su respuesta."""

    __tablename__ = "recordatorios_log"
    __table_args__ = (_check_enum("respuesta", RespuestaRecordatorio),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actividad_id: Mapped[int] = mapped_column(ForeignKey("actividades.id", ondelete="CASCADE"), index=True)
    momento: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    respuesta: Mapped[str] = mapped_column(String(20))

    actividad: Mapped[Actividad] = relationship(back_populates="recordatorios")


# ---------------------------------------------------------------------------
# Soporte
# ---------------------------------------------------------------------------


class CopiaSeguridad(Base):
    """Registro de las copias de seguridad realizadas."""

    __tablename__ = "copias_seguridad"
    __table_args__ = (_check_enum("tipo", TipoCopia),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    ruta: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(20))


class EdicionLog(Base):
    """Trazabilidad de correcciones manuales (RF-07). Un registro por campo cambiado."""

    __tablename__ = "ediciones_log"
    __table_args__ = (
        CheckConstraint("TRIM(motivo) <> ''", name="motivo"),
        Index("ix_ediciones_log_registro", "tabla", "registro_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    momento: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    tabla: Mapped[str] = mapped_column(String(60))
    registro_id: Mapped[int] = mapped_column(Integer)
    campo: Mapped[str] = mapped_column(String(60))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_nuevo: Mapped[str | None] = mapped_column(Text)
    motivo: Mapped[str] = mapped_column(Text)
