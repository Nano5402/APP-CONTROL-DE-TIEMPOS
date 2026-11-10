"""Repositorios para categorías, solicitantes y plantillas/recurrentes."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.enums import Prioridad, Recurrencia, TipoSolicitante
from data.models import Categoria, Plantilla, Solicitante


CATEGORIAS_BASE: list[tuple[str, str]] = [
    ("Flyers", "#003D95"),
    ("Videos / Reels", "#0284C7"),
    ("Redes Sociales", "#7C3AED"),
    ("Banners / Pendones", "#D97706"),
    ("Comunicados", "#15803D"),
    ("Soporte / Ajustes", "#475569"),
]


class RepoCategorias:
    """Gestión de categorías libres creadas por el usuario (RF-01)."""

    def __init__(self, s: Session) -> None:
        self.s = s

    def asegurar_categorias_base(self) -> list[Categoria]:
        """Garantiza que las categorías iniciales (incluyendo ``Flyers``) existan si el catálogo está vacío."""
        from data.models import Configuracion

        clave = "catalogos.categorias_base_cargadas"
        ya_cargadas = self.s.get(Configuracion, clave)
        if not ya_cargadas:
            for nombre, color in CATEGORIAS_BASE:
                if self.buscar_por_nombre(nombre) is None:
                    self.s.add(
                        Categoria(
                            nombre=nombre,
                            color=color,
                            activo=True,
                        )
                    )
            self.s.add(Configuracion(clave=clave, valor="1"))
            self.s.flush()
        else:
            # Asegura siempre que Flyers exista
            if self.buscar_por_nombre("Flyers") is None:
                self.s.add(Categoria(nombre="Flyers", color="#003D95", activo=True))
                self.s.flush()
        return self.listar_activas()

    def desactivar(self, categoria_id: int) -> None:
        cat = self.s.get(Categoria, categoria_id)
        if cat is not None:
            cat.activo = False
            self.s.flush()

    def listar_activas(self) -> list[Categoria]:
        consulta = select(Categoria).where(Categoria.activo.is_(True)).order_by(Categoria.nombre)
        return list(self.s.scalars(consulta))

    def buscar_por_nombre(self, nombre: str) -> Categoria | None:
        limpio = nombre.strip()
        consulta = select(Categoria).where(Categoria.nombre.ilike(limpio))
        return self.s.scalar(consulta)

    def obtener_o_crear(
        self,
        nombre: str,
        color: str = "#6B7280",
        *,
        intervalo_recordatorio_min: int | None = None,
    ) -> Categoria:
        """Devuelve la categoría existente (sin importar mayúsculas) o la crea."""
        limpio = nombre.strip()
        if not limpio:
            raise ValueError("El nombre de la categoría no puede estar vacío")
        existente = self.buscar_por_nombre(limpio)
        if existente:
            existente.activo = True
            if intervalo_recordatorio_min is not None:
                existente.intervalo_recordatorio_min = intervalo_recordatorio_min
            self.s.flush()
            return existente
        nueva = Categoria(
            nombre=limpio,
            color=color,
            intervalo_recordatorio_min=intervalo_recordatorio_min,
            activo=True,
        )
        self.s.add(nueva)
        self.s.flush()
        return nueva


class RepoSolicitantes:
    """Gestión de solicitantes y sus reglas de prioridad/aprobación (RF-03)."""

    def __init__(self, s: Session) -> None:
        self.s = s

    def listar_activos(self) -> list[Solicitante]:
        consulta = select(Solicitante).where(Solicitante.activo.is_(True)).order_by(Solicitante.id)
        return list(self.s.scalars(consulta))

    def buscar_por_nombre(self, nombre: str) -> Solicitante | None:
        limpio = nombre.strip()
        return self.s.scalar(select(Solicitante).where(Solicitante.nombre.ilike(limpio)))

    def crear(
        self,
        nombre: str,
        tipo: TipoSolicitante | str,
        *,
        prioridad_defecto: Prioridad | str | None = None,
        requiere_aprobacion: bool | None = None,
    ) -> Solicitante:
        """Crea (o reactiva) un solicitante aplicando las reglas de la sección 5 (RF-03):

        - Jefe y doctoras: prioridad máxima, sin aprobación requerida.
        - Compañeros: prioridad mínima, requiere aprobación del ingeniero.
        - Terceros: prioridad según el caso (normal por defecto), requiere aprobación.
        """
        limpio = nombre.strip()
        if not limpio:
            raise ValueError("El nombre del solicitante no puede estar vacío")

        tipo_enum = TipoSolicitante(tipo)
        if prioridad_defecto is None:
            if tipo_enum in (TipoSolicitante.JEFE, TipoSolicitante.DOCTORA):
                prioridad_val = Prioridad.MAXIMA.value
            elif tipo_enum == TipoSolicitante.COMPANERO:
                prioridad_val = Prioridad.MINIMA.value
            else:
                prioridad_val = Prioridad.NORMAL.value
        else:
            prioridad_val = Prioridad(prioridad_defecto).value

        if requiere_aprobacion is None:
            requiere_val = tipo_enum in (TipoSolicitante.COMPANERO, TipoSolicitante.TERCERO)
        else:
            requiere_val = bool(requiere_aprobacion)

        existente = self.buscar_por_nombre(limpio)
        if existente:
            existente.tipo = tipo_enum.value
            existente.prioridad_defecto = prioridad_val
            existente.requiere_aprobacion = requiere_val
            existente.activo = True
            self.s.flush()
            return existente

        nuevo = Solicitante(
            nombre=limpio,
            tipo=tipo_enum.value,
            prioridad_defecto=prioridad_val,
            requiere_aprobacion=requiere_val,
            activo=True,
        )
        self.s.add(nuevo)
        self.s.flush()
        return nuevo


class RepoPlantillas:
    """Gestión de plantillas y actividades recurrentes (RF-01)."""

    def __init__(self, s: Session) -> None:
        self.s = s

    def listar_activas(self) -> list[Plantilla]:
        consulta = select(Plantilla).where(Plantilla.activo.is_(True)).order_by(Plantilla.nombre)
        return list(self.s.scalars(consulta))

    def propuestas_para_fecha(self, fecha: date) -> list[Plantilla]:
        """Devuelve las plantillas recurrentes que aplican para el día dado."""
        dia = str(fecha.weekday())
        propuestas: list[Plantilla] = []
        for p in self.listar_activas():
            if p.recurrencia == Recurrencia.DIARIA.value:
                propuestas.append(p)
            elif p.recurrencia == Recurrencia.DIAS_SEMANA.value and p.dias_semana:
                dias = {x.strip() for x in p.dias_semana.split(",") if x.strip()}
                if dia in dias:
                    propuestas.append(p)
        return propuestas

    def crear(
        self,
        nombre: str,
        *,
        categoria_id: int | None = None,
        tiempo_estimado_min: int | None = None,
        recurrencia: Recurrencia | str = Recurrencia.NINGUNA,
        dias_semana: list[int] | str | None = None,
        intervalo_recordatorio_min: int | None = None,
    ) -> Plantilla:
        limpio = nombre.strip()
        if not limpio:
            raise ValueError("El nombre de la plantilla no puede estar vacío")
        rec_enum = Recurrencia(recurrencia)
        if isinstance(dias_semana, list):
            dias_txt = ",".join(str(d) for d in sorted(set(dias_semana)))
        else:
            dias_txt = dias_semana

        plantilla = Plantilla(
            nombre=limpio,
            categoria_id=categoria_id,
            tiempo_estimado_min=tiempo_estimado_min,
            recurrencia=rec_enum.value,
            dias_semana=dias_txt,
            intervalo_recordatorio_min=intervalo_recordatorio_min,
            activo=True,
        )
        self.s.add(plantilla)
        self.s.flush()
        return plantilla
