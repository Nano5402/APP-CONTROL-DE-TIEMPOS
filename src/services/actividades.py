"""Servicio de gestión de actividades: planeadas, lotes, extras, revisiones,
reasignaciones, estados manuales y correcciones con trazabilidad (Fase 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.enums import (
    CanalSolicitud,
    EstadoActividad,
    EstadoAprobacion,
    Lugar,
    MotivoRevision,
    Prioridad,
    TipoActividad,
    TipoRevision,
)
from data.models import Actividad, EdicionLog, Jornada, Plantilla, SesionTiempo, Solicitante
from data.repositorios.jornadas import RepoJornadas
from data.tiempo import ahora
from services.numeracion import nombres_lote_piezas


@dataclass(frozen=True)
class DesgloseTiempoActividad:
    """Resumen de tiempos de una actividad y sus revisiones (RF-03b)."""

    segundos_original: int
    segundos_revisiones: int
    segundos_total: int
    segundos_fuera_horario: int
    cantidad_revisiones: int

    @property
    def solicitaron_cambios(self) -> bool:
        return self.cantidad_revisiones > 0


class ServicioActividades:
    """Operaciones de creación, consulta y ciclo de vida de actividades."""

    def __init__(self, s: Session) -> None:
        self.s = s
        self.repo_jornadas = RepoJornadas(s)

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def listar_visibles_jornada(self, jornada_id: int) -> list[Actividad]:
        """Lista las actividades de una jornada excluyendo las eliminadas."""
        consulta = (
            select(Actividad)
            .where(
                Actividad.jornada_id == jornada_id,
                Actividad.estado != EstadoActividad.ELIMINADA.value,
            )
            .order_by(Actividad.id)
        )
        return list(self.s.scalars(consulta))

    def listar_arrastradas_pendientes(self, antes_de_fecha: date) -> list[Actividad]:
        """Actividades que quedaron arrastradas en jornadas anteriores (RF-05)."""
        consulta = (
            select(Actividad)
            .join(Jornada, Actividad.jornada_id == Jornada.id)
            .where(
                Jornada.fecha < antes_de_fecha,
                Actividad.estado == EstadoActividad.ARRASTRADA.value,
            )
            .order_by(Jornada.fecha, Actividad.id)
        )
        return list(self.s.scalars(consulta))

    def nombres_para_autocompletado(self) -> list[str]:
        """Nombres únicos de actividades previas para autocompletar (RF-01, RF-12)."""
        consulta = (
            select(Actividad.nombre)
            .where(
                Actividad.es_revision.is_(False),
                Actividad.estado != EstadoActividad.ELIMINADA.value,
            )
            .distinct()
            .order_by(Actividad.nombre)
        )
        return list(self.s.scalars(consulta))

    def _nombres_en_jornada(self, jornada_id: int) -> list[str]:
        consulta = select(Actividad.nombre).where(
            Actividad.jornada_id == jornada_id,
            Actividad.estado != EstadoActividad.ELIMINADA.value,
        )
        return list(self.s.scalars(consulta))

    # ------------------------------------------------------------------
    # Creación: planeadas, lotes, desde plantilla y no planeadas
    # ------------------------------------------------------------------

    def crear_planeada(
        self,
        nombre: str,
        *,
        jornada: Jornada | None = None,
        categoria_id: int | None = None,
        tiempo_estimado_min: int | None = None,
        prioridad: Prioridad | str = Prioridad.NORMAL,
        descripcion: str | None = None,
        notas: str | None = None,
        intervalo_recordatorio_min: int | None = None,
        plantilla_id: int | None = None,
        momento: datetime | None = None,
    ) -> Actividad:
        """Crea una actividad planeada del día (RF-01)."""
        limpio = nombre.strip()
        if not limpio:
            raise ValueError("El nombre de la actividad no puede estar vacío")

        instante = momento or ahora()
        jornada_obj = jornada or self.repo_jornadas.obtener_o_crear(instante.date(), instante)

        act = Actividad(
            jornada_id=jornada_obj.id,
            categoria_id=categoria_id,
            plantilla_id=plantilla_id,
            nombre=limpio,
            tipo=TipoActividad.PLANEADA.value,
            prioridad=Prioridad(prioridad).value,
            estado=EstadoActividad.PENDIENTE.value,
            aprobacion_estado=EstadoAprobacion.NO_REQUERIDA.value,
            tiempo_estimado_min=tiempo_estimado_min,
            descripcion=descripcion,
            notas=notas,
            intervalo_recordatorio_min=intervalo_recordatorio_min,
            creada_en=instante,
        )
        self.s.add(act)
        self.s.flush()
        return act

    def crear_lote_piezas(
        self,
        nombre_base: str,
        cantidad: int,
        *,
        jornada: Jornada | None = None,
        categoria_id: int | None = None,
        tiempo_estimado_min: int | None = None,
        prioridad: Prioridad | str = Prioridad.NORMAL,
        tipo: TipoActividad | str = TipoActividad.PLANEADA,
        descripcion: str | None = None,
        intervalo_recordatorio_min: int | None = None,
        plantilla_id: int | None = None,
        momento: datetime | None = None,
    ) -> list[Actividad]:
        """Crea de golpe N actividades numeradas (ej. ``Flyer 1`` … ``Flyer 10``)."""
        instante = momento or ahora()
        jornada_obj = jornada or self.repo_jornadas.obtener_o_crear(instante.date(), instante)
        existentes = self._nombres_en_jornada(jornada_obj.id)
        nombres = nombres_lote_piezas(nombre_base, cantidad, existentes)

        creadas: list[Actividad] = []
        for nom in nombres:
            act = Actividad(
                jornada_id=jornada_obj.id,
                categoria_id=categoria_id,
                plantilla_id=plantilla_id,
                nombre=nom,
                tipo=TipoActividad(tipo).value,
                prioridad=Prioridad(prioridad).value,
                estado=EstadoActividad.PENDIENTE.value,
                aprobacion_estado=EstadoAprobacion.NO_REQUERIDA.value,
                tiempo_estimado_min=tiempo_estimado_min,
                descripcion=descripcion,
                intervalo_recordatorio_min=intervalo_recordatorio_min,
                creada_en=instante,
            )
            self.s.add(act)
            creadas.append(act)
        self.s.flush()
        return creadas

    def crear_desde_plantilla(
        self,
        plantilla: Plantilla,
        *,
        jornada: Jornada | None = None,
        cantidad: int = 1,
        nombre_personalizado: str | None = None,
        tiempo_estimado_min: int | None = None,
        momento: datetime | None = None,
    ) -> list[Actividad]:
        """Acepta una plantilla propuesta al planear el día (RF-01)."""
        base = (nombre_personalizado or plantilla.nombre).strip()
        estimado = (
            tiempo_estimado_min
            if tiempo_estimado_min is not None
            else plantilla.tiempo_estimado_min
        )
        return self.crear_lote_piezas(
            base,
            cantidad,
            jornada=jornada,
            categoria_id=plantilla.categoria_id,
            tiempo_estimado_min=estimado,
            intervalo_recordatorio_min=plantilla.intervalo_recordatorio_min,
            plantilla_id=plantilla.id,
            momento=momento,
        )

    def crear_no_planeada(
        self,
        nombre: str,
        *,
        jornada: Jornada | None = None,
        categoria_id: int | None = None,
        tiempo_estimado_min: int | None = None,
        descripcion: str | None = None,
        momento: datetime | None = None,
    ) -> Actividad:
        """Crea una actividad por iniciativa propia sin plan previo (RF-03)."""
        limpio = nombre.strip()
        if not limpio:
            raise ValueError("El nombre de la actividad no puede estar vacío")
        instante = momento or ahora()
        jornada_obj = jornada or self.repo_jornadas.obtener_o_crear(instante.date(), instante)

        act = Actividad(
            jornada_id=jornada_obj.id,
            categoria_id=categoria_id,
            nombre=limpio,
            tipo=TipoActividad.NO_PLANEADA.value,
            prioridad=Prioridad.NORMAL.value,
            estado=EstadoActividad.PENDIENTE.value,
            aprobacion_estado=EstadoAprobacion.NO_REQUERIDA.value,
            tiempo_estimado_min=tiempo_estimado_min,
            descripcion=descripcion,
            creada_en=instante,
        )
        self.s.add(act)
        self.s.flush()
        return act

    # ------------------------------------------------------------------
    # Actividades extra y aprobaciones (RF-03)
    # ------------------------------------------------------------------

    def crear_extra(
        self,
        nombre: str,
        solicitante: Solicitante,
        *,
        motivo_urgencia: str,
        canal_solicitud: CanalSolicitud | str,
        descripcion: str,
        jornada: Jornada | None = None,
        categoria_id: int | None = None,
        tiempo_estimado_min: int | None = None,
        fecha_limite: datetime | None = None,
        prioridad: Prioridad | str | None = None,
        aprobada_previamente: bool = False,
        aprobacion_canal: CanalSolicitud | str | None = None,
        momento: datetime | None = None,
    ) -> Actividad:
        """Crea una actividad extra aplicando las reglas del solicitante (RF-03):

        - Jefe y doctoras: prioridad máxima, no requiere aprobación, queda ``pendiente``.
        - Compañeros y terceros: requieren aprobación del ingeniero. Si
          ``aprobada_previamente=False``, se crea ``bloqueada`` y con aprobación
          ``pendiente`` (no se puede iniciar hasta registrar la decisión).
        """
        limpio = nombre.strip()
        if not limpio:
            raise ValueError("El nombre de la actividad extra no puede estar vacío")
        if not motivo_urgencia.strip():
            raise ValueError("El motivo de la urgencia es obligatorio en actividades extra")
        if not descripcion.strip():
            raise ValueError("La descripción es obligatoria en actividades extra")

        instante = momento or ahora()
        jornada_obj = jornada or self.repo_jornadas.obtener_o_crear(instante.date(), instante)
        canal_val = CanalSolicitud(canal_solicitud).value
        prioridad_val = (
            Prioridad(prioridad).value if prioridad is not None else solicitante.prioridad_defecto
        )

        if solicitante.requiere_aprobacion:
            if aprobada_previamente:
                aprob_estado = EstadoAprobacion.APROBADA.value
                estado_act = EstadoActividad.PENDIENTE.value
                aprob_fecha = instante
                aprob_canal = (
                    CanalSolicitud(aprobacion_canal).value if aprobacion_canal else canal_val
                )
            else:
                aprob_estado = EstadoAprobacion.PENDIENTE.value
                estado_act = EstadoActividad.BLOQUEADA.value
                aprob_fecha = None
                aprob_canal = None
        else:
            aprob_estado = EstadoAprobacion.NO_REQUERIDA.value
            estado_act = EstadoActividad.PENDIENTE.value
            aprob_fecha = None
            aprob_canal = None

        act = Actividad(
            jornada_id=jornada_obj.id,
            categoria_id=categoria_id,
            nombre=limpio,
            tipo=TipoActividad.EXTRA.value,
            solicitante_id=solicitante.id,
            prioridad=prioridad_val,
            estado=estado_act,
            motivo_urgencia=motivo_urgencia.strip(),
            descripcion=descripcion.strip(),
            fecha_limite=fecha_limite,
            canal_solicitud=canal_val,
            tiempo_estimado_min=tiempo_estimado_min,
            aprobacion_estado=aprob_estado,
            aprobacion_fecha=aprob_fecha,
            aprobacion_canal=aprob_canal,
            creada_en=instante,
        )
        self.s.add(act)
        self.s.flush()
        return act

    def registrar_decision_ingeniero(
        self,
        actividad: Actividad,
        *,
        aprobada: bool,
        canal: CanalSolicitud | str,
        momento: datetime | None = None,
    ) -> Actividad:
        """Registra la decisión del ingeniero sobre una solicitud bloqueada (RF-03)."""
        instante = momento or ahora()
        actividad.aprobacion_canal = CanalSolicitud(canal).value
        actividad.aprobacion_fecha = instante
        if aprobada:
            actividad.aprobacion_estado = EstadoAprobacion.APROBADA.value
            if actividad.estado == EstadoActividad.BLOQUEADA.value:
                actividad.estado = EstadoActividad.PENDIENTE.value
        else:
            actividad.aprobacion_estado = EstadoAprobacion.RECHAZADA.value
            actividad.estado = EstadoActividad.RECHAZADA.value
        self.s.flush()
        return actividad

    # ------------------------------------------------------------------
    # Revisiones (RF-03b)
    # ------------------------------------------------------------------

    def crear_revision(
        self,
        actividad_original: Actividad,
        *,
        solicitante: Solicitante,
        tipo_revision: TipoRevision | str,
        que_cambiar: str,
        motivo: MotivoRevision | str,
        jornada: Jornada | None = None,
        momento: datetime | None = None,
    ) -> Actividad:
        """Reabre una actividad finalizada creando una revisión vinculada con cronómetro propio."""
        raiz = actividad_original.actividad_padre or actividad_original
        if raiz.estado != EstadoActividad.COMPLETADA.value:
            raise ValueError("Solo se puede crear una revisión sobre una actividad completada")
        if not que_cambiar.strip():
            raise ValueError("Debe indicar qué se pidió cambiar en la revisión")

        instante = momento or ahora()
        jornada_obj = jornada or self.repo_jornadas.obtener_o_crear(instante.date(), instante)

        existentes = list(
            self.s.scalars(
                select(Actividad).where(
                    Actividad.actividad_padre_id == raiz.id,
                    Actividad.estado != EstadoActividad.ELIMINADA.value,
                )
            )
        )
        num = len(existentes) + 1
        nombre_rev = f"{raiz.nombre} → Revisión {num}"

        revision = Actividad(
            jornada_id=jornada_obj.id,
            categoria_id=raiz.categoria_id,
            nombre=nombre_rev,
            tipo=raiz.tipo,
            solicitante_id=solicitante.id,
            prioridad=solicitante.prioridad_defecto,
            estado=EstadoActividad.PENDIENTE.value,
            aprobacion_estado=EstadoAprobacion.NO_REQUERIDA.value,
            actividad_padre=raiz,
            es_revision=True,
            revision_solicitante_id=solicitante.id,
            revision_tipo=TipoRevision(tipo_revision).value,
            revision_que_cambiar=que_cambiar.strip(),
            revision_motivo=MotivoRevision(motivo).value,
            creada_en=instante,
        )
        self.s.add(revision)
        self.s.flush()
        return revision

    def desglose_tiempos(self, actividad: Actividad) -> DesgloseTiempoActividad:
        """Calcula el tiempo original, de revisiones y total sin alterar el original (RF-03b)."""
        raiz = actividad.actividad_padre or actividad
        sesiones_raiz = list(
            self.s.scalars(select(SesionTiempo).where(SesionTiempo.actividad_id == raiz.id))
        )
        seg_orig = sum(s.duracion_seg for s in sesiones_raiz)
        fuera = sum(s.duracion_seg for s in sesiones_raiz if s.fuera_horario)

        revs = list(
            self.s.scalars(
                select(Actividad).where(
                    Actividad.actividad_padre_id == raiz.id,
                    Actividad.estado != EstadoActividad.ELIMINADA.value,
                )
            )
        )
        seg_rev = 0
        for r in revs:
            sesiones_r = list(
                self.s.scalars(select(SesionTiempo).where(SesionTiempo.actividad_id == r.id))
            )
            seg_rev += sum(s.duracion_seg for s in sesiones_r)
            fuera += sum(s.duracion_seg for s in sesiones_r if s.fuera_horario)

        return DesgloseTiempoActividad(
            segundos_original=seg_orig,
            segundos_revisiones=seg_rev,
            segundos_total=seg_orig + seg_rev,
            segundos_fuera_horario=fuera,
            cantidad_revisiones=len(revs),
        )

    # ------------------------------------------------------------------
    # Reasignación y cambios manuales de estado (RF-03, RF-03c)
    # ------------------------------------------------------------------

    def cambiar_estado_manual(
        self,
        actividad: Actividad,
        nuevo_estado: EstadoActividad | str,
        *,
        motivo: str | None = None,
    ) -> Actividad:
        """Permite marcar una actividad como rechazada, aplazada o eliminada (RF-03)."""
        estado_enum = EstadoActividad(nuevo_estado)
        permitidos = {
            EstadoActividad.RECHAZADA,
            EstadoActividad.APLAZADA,
            EstadoActividad.ELIMINADA,
            EstadoActividad.PENDIENTE,
        }
        if estado_enum not in permitidos:
            raise ValueError(f"Transición manual no permitida hacia {estado_enum.value}")
        if actividad.estado == EstadoActividad.EN_CURSO.value:
            raise ValueError("Detenga o pause el cronómetro antes de cambiar el estado")
        actividad.estado = estado_enum.value
        if motivo and motivo.strip():
            actividad.notas = (
                f"{actividad.notas}\n{motivo.strip()}".strip()
                if actividad.notas
                else motivo.strip()
            )
        self.s.flush()
        return actividad

    # ------------------------------------------------------------------
    # Correcciones manuales con trazabilidad (RF-07)
    # ------------------------------------------------------------------

    def corregir_actividad(
        self,
        actividad: Actividad,
        *,
        motivo: str,
        nombre: str | None = None,
        categoria_id: int | None = None,
        tiempo_estimado_min: int | None = None,
        descripcion: str | None = None,
        momento: datetime | None = None,
    ) -> Actividad:
        """Edita datos de una actividad exigiendo motivo y guardando en ``ediciones_log``."""
        motivo_limpio = motivo.strip() if motivo else ""
        if not motivo_limpio:
            raise ValueError("El motivo es obligatorio para corregir un registro")

        instante = momento or ahora()
        cambios: list[tuple[str, object, object]] = []

        if nombre is not None and nombre.strip() != actividad.nombre:
            cambios.append(("nombre", actividad.nombre, nombre.strip()))
            actividad.nombre = nombre.strip()
        if categoria_id is not None and categoria_id != actividad.categoria_id:
            cambios.append(("categoria_id", actividad.categoria_id, categoria_id))
            actividad.categoria_id = categoria_id
        if tiempo_estimado_min is not None and tiempo_estimado_min != actividad.tiempo_estimado_min:
            cambios.append(("tiempo_estimado_min", actividad.tiempo_estimado_min, tiempo_estimado_min))
            actividad.tiempo_estimado_min = tiempo_estimado_min
        if descripcion is not None and descripcion != actividad.descripcion:
            cambios.append(("descripcion", actividad.descripcion, descripcion))
            actividad.descripcion = descripcion

        for campo, anterior, nuevo in cambios:
            self.s.add(
                EdicionLog(
                    momento=instante,
                    tabla="actividades",
                    registro_id=actividad.id,
                    campo=campo,
                    valor_anterior=None if anterior is None else str(anterior),
                    valor_nuevo=None if nuevo is None else str(nuevo),
                    motivo=motivo_limpio,
                )
            )

        actividad.editado = True
        actividad.editado_motivo = motivo_limpio
        self.s.flush()
        return actividad

    def corregir_sesion_tiempo(
        self,
        sesion: SesionTiempo,
        *,
        motivo: str,
        nuevo_inicio: datetime | None = None,
        nuevo_fin: datetime | None = None,
        lugar: Lugar | str | None = None,
        momento: datetime | None = None,
    ) -> SesionTiempo:
        """Corrige las horas de un tramo de cronómetro (ej. olvido de iniciar o finalizar)."""
        motivo_limpio = motivo.strip() if motivo else ""
        if not motivo_limpio:
            raise ValueError("El motivo es obligatorio para corregir un tramo de tiempo")

        instante = momento or ahora()
        inicio_final = nuevo_inicio or sesion.inicio
        fin_final = nuevo_fin if nuevo_fin is not None else sesion.fin

        if fin_final is not None and fin_final < inicio_final:
            raise ValueError("La hora de fin no puede ser anterior a la de inicio")

        if nuevo_inicio is not None and nuevo_inicio != sesion.inicio:
            self.s.add(
                EdicionLog(
                    momento=instante,
                    tabla="sesiones_tiempo",
                    registro_id=sesion.id,
                    campo="inicio",
                    valor_anterior=sesion.inicio.isoformat(),
                    valor_nuevo=nuevo_inicio.isoformat(),
                    motivo=motivo_limpio,
                )
            )
            sesion.inicio = nuevo_inicio

        if nuevo_fin is not None and nuevo_fin != sesion.fin:
            self.s.add(
                EdicionLog(
                    momento=instante,
                    tabla="sesiones_tiempo",
                    registro_id=sesion.id,
                    campo="fin",
                    valor_anterior=sesion.fin.isoformat() if sesion.fin else None,
                    valor_nuevo=nuevo_fin.isoformat(),
                    motivo=motivo_limpio,
                )
            )
            sesion.fin = nuevo_fin

        if lugar is not None:
            lugar_val = Lugar(lugar).value
            if lugar_val != sesion.lugar:
                self.s.add(
                    EdicionLog(
                        momento=instante,
                        tabla="sesiones_tiempo",
                        registro_id=sesion.id,
                        campo="lugar",
                        valor_anterior=sesion.lugar,
                        valor_nuevo=lugar_val,
                        motivo=motivo_limpio,
                    )
                )
                sesion.lugar = lugar_val

        if sesion.fin is not None:
            sesion.duracion_seg = int((sesion.fin - sesion.inicio).total_seconds())

        actividad = sesion.actividad
        actividad.editado = True
        actividad.editado_motivo = motivo_limpio
        self.s.flush()
        return sesion
