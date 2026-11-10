"""Pantalla 8: Configuración — RF-09, RF-12.

Permite configurar en un solo lugar:
- Datos del usuario y empresa, tema visual (Gente Util Corporativo, Claro, Oscuro, Azul Pizarra).
- Inicio automático con Windows (`HKCU`, sin permisos de administrador) y opción de
  abrir la ventana al encender el portátil o iniciar oculta en la bandeja.
- Atajos de teclado opcionales (vacíos/desactivados por defecto para no interferir
  mientras se trabaja; cada persona puede asignarlos o limpiarlos a su gusto).
- Intervalos de recordatorios, meta de tiempo efectivo y pesos de la fórmula.
- Plantillas y actividades recurrentes.
- PIN opcional (establecer o desactivar).
- Copias de seguridad: copia manual ahora, copiar a USB/carpeta externa y
  restaurar desde archivo `.db`.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from data.db import BaseDatos
from data.enums import Recurrencia, TipoCopia
from data.models import Usuario
from data.repositorios.catalogos import RepoCategorias, RepoPlantillas
from data.repositorios.configuracion import RepoConfiguracion
from services.backups import ServicioBackups
from services.inicio_windows import ServicioInicioWindows
from services.seguridad_pin import ServicioPIN
from ui.temas import TEMAS


class PantallaConfiguracion(QWidget):
    """Pantalla de configuración general de la aplicación."""

    def __init__(
        self,
        bd: BaseDatos,
        *,
        al_cambiar_tema: Callable[[str], None] | None = None,
        al_cambiar_atajos: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.bd = bd
        self.al_cambiar_tema = al_cambiar_tema
        self.al_cambiar_atajos = al_cambiar_atajos

        layout_raiz = QVBoxLayout(self)
        layout_raiz.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        contenedor = QWidget(scroll)
        layout = QVBoxLayout(contenedor)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(14)

        lbl_tit = QLabel("Configuración y Personalización", self)
        lbl_tit.setObjectName("tituloPantalla")
        layout.addWidget(lbl_tit)

        # 1. Perfil, Tema e Inicio con Windows
        card_gen = QFrame(self)
        card_gen.setProperty("card", True)
        form_gen = QFormLayout(card_gen)
        form_gen.setSpacing(10)
        form_gen.addRow(QLabel("<b>1. Apariencia, Empresa e Inicio con Windows</b>"))

        self.txt_usuario = QLineEdit(self)
        self.txt_usuario.setPlaceholderText("Ej. Andrés")
        self.txt_empresa = QLineEdit(self)
        self.txt_color_empresa = QLineEdit(self)
        self.txt_color_empresa.setPlaceholderText("#0F4C81")
        self.txt_logo_ruta = QLineEdit(self)
        self.txt_logo_ruta.setPlaceholderText("Automático (logo corporativo Gente Util)")
        self.btn_elegir_logo = QPushButton("Elegir logo...", self)
        self.btn_elegir_logo.setProperty("rol", "secundario")
        self.btn_elegir_logo.clicked.connect(self.accion_elegir_logo)

        fila_logo = QHBoxLayout()
        fila_logo.addWidget(self.txt_logo_ruta, 1)
        fila_logo.addWidget(self.btn_elegir_logo)

        self.combo_tema = QComboBox(self)
        for cod, paleta in TEMAS.items():
            self.combo_tema.addItem(paleta.nombre, cod)

        self.chk_autostart = QCheckBox(
            "Iniciar automáticamente al encender el portátil (inicio de sesión de Windows)",
            self,
        )
        self.chk_iniciar_oculta = QCheckBox(
            "Al iniciar con Windows, arrancar oculta en la bandeja (desmarca para abrir la ventana en pantalla)",
            self,
        )

        form_gen.addRow("Tu nombre (para reportes y WhatsApp):", self.txt_usuario)
        form_gen.addRow("Empresa:", self.txt_empresa)
        form_gen.addRow("Color primario en reportes PDF:", self.txt_color_empresa)
        form_gen.addRow("Logo para reportes PDF:", fila_logo)
        form_gen.addRow("Tema visual:", self.combo_tema)
        form_gen.addRow("", self.chk_autostart)
        form_gen.addRow("", self.chk_iniciar_oculta)
        layout.addWidget(card_gen)

        # 2. Atajos de teclado opcionales (desactivados por defecto)
        card_atajos = QFrame(self)
        card_atajos.setProperty("card", True)
        form_atajos = QFormLayout(card_atajos)
        form_atajos.setSpacing(10)
        form_atajos.addRow(
            QLabel(
                "<b>2. Atajos de teclado (opcionales — vacíos por defecto para no interferir con otros programas)</b>"
            )
        )

        self.key_iniciar_pausar = QKeySequenceEdit(self)
        self.key_finalizar = QKeySequenceEdit(self)
        self.key_siguiente = QKeySequenceEdit(self)
        self.key_mini = QKeySequenceEdit(self)

        form_atajos.addRow(
            "Iniciar / Pausar actividad:",
            self._fila_key_edit(self.key_iniciar_pausar),
        )
        form_atajos.addRow(
            "Finalizar actividad en curso:",
            self._fila_key_edit(self.key_finalizar),
        )
        form_atajos.addRow(
            "Finalizar y empezar siguiente pieza:",
            self._fila_key_edit(self.key_siguiente),
        )
        form_atajos.addRow(
            "Mostrar / Ocultar Mini-ventana:",
            self._fila_key_edit(self.key_mini),
        )

        self.btn_limpiar_atajos = QPushButton(
            "🗑 Desactivar / Limpiar todos los atajos", self
        )
        self.btn_limpiar_atajos.setProperty("rol", "secundario")
        self.btn_limpiar_atajos.clicked.connect(self.accion_limpiar_todos_los_atajos)
        form_atajos.addRow("", self.btn_limpiar_atajos)
        layout.addWidget(card_atajos)

        # 3. Recordatorios, Meta y Fórmula de Productividad
        card_rec = QFrame(self)
        card_rec.setProperty("card", True)
        form_rec = QFormLayout(card_rec)
        form_rec.setSpacing(10)
        form_rec.addRow(QLabel("<b>3. Recordatorios, Meta de Tiempo y Fórmula</b>"))

        self.spin_rec_cont = QSpinBox(self)
        self.spin_rec_cont.setRange(1, 180)
        self.spin_rec_cont.setSuffix(" min")

        self.spin_rec_rep = QSpinBox(self)
        self.spin_rec_rep.setRange(1, 60)
        self.spin_rec_rep.setSuffix(" min")

        self.spin_rec_inact = QSpinBox(self)
        self.spin_rec_inact.setRange(1, 120)
        self.spin_rec_inact.setSuffix(" min")

        self.chk_sonido = QCheckBox("Reproducir sonido en los avisos", self)

        self.spin_meta_pct = QSpinBox(self)
        self.spin_meta_pct.setRange(10, 100)
        self.spin_meta_pct.setSuffix(" % de la jornada")

        self.spin_peso_c = QSpinBox(self)
        self.spin_peso_c.setRange(0, 100)
        self.spin_peso_c.setSuffix(" %")
        self.spin_peso_e = QSpinBox(self)
        self.spin_peso_e.setRange(0, 100)
        self.spin_peso_e.setSuffix(" %")
        self.spin_peso_f = QSpinBox(self)
        self.spin_peso_f.setRange(0, 100)
        self.spin_peso_f.setSuffix(" %")

        fila_pesos = QHBoxLayout()
        fila_pesos.addWidget(QLabel("Cumplimiento:"))
        fila_pesos.addWidget(self.spin_peso_c)
        fila_pesos.addWidget(QLabel("Eficiencia:"))
        fila_pesos.addWidget(self.spin_peso_e)
        fila_pesos.addWidget(QLabel("Foco:"))
        fila_pesos.addWidget(self.spin_peso_f)

        form_rec.addRow("Intervalo «¿Sigues con...?»:", self.spin_rec_cont)
        form_rec.addRow("Repetir si no hay respuesta cada:", self.spin_rec_rep)
        form_rec.addRow("Avisar si no hay actividad tras:", self.spin_rec_inact)
        form_rec.addRow("", self.chk_sonido)
        form_rec.addRow("Meta de tiempo efectivo diario:", self.spin_meta_pct)
        form_rec.addRow("Pesos de productividad:", fila_pesos)

        self.btn_guardar_cfg = QPushButton("💾 Guardar configuración general y atajos", self)
        self.btn_guardar_cfg.clicked.connect(self.accion_guardar_general)
        form_rec.addRow("", self.btn_guardar_cfg)
        layout.addWidget(card_rec)

        # 4. Crear Plantilla / Recurrente
        card_plant = QFrame(self)
        card_plant.setProperty("card", True)
        form_plant = QFormLayout(card_plant)
        form_plant.setSpacing(10)
        form_plant.addRow(QLabel("<b>4. Nueva plantilla o actividad recurrente</b>"))

        self.txt_plant_nombre = QLineEdit(self)
        self.txt_plant_nombre.setPlaceholderText("Ej. Flyers vacantes, Posts de Instagram...")
        self.txt_plant_cat = QLineEdit(self)
        self.txt_plant_cat.setPlaceholderText("Categoría (opcional)")
        self.spin_plant_est = QSpinBox(self)
        self.spin_plant_est.setRange(0, 480)
        self.spin_plant_est.setSuffix(" min")
        self.combo_plant_rec = QComboBox(self)
        self.combo_plant_rec.addItem("Diaria (todos los días)", Recurrencia.DIARIA.value)
        self.combo_plant_rec.addItem("Lunes a viernes", Recurrencia.DIAS_SEMANA.value)
        self.combo_plant_rec.addItem("Manual (sin recurrencia)", Recurrencia.NINGUNA.value)

        self.btn_crear_plant = QPushButton("+ Guardar plantilla", self)
        self.btn_crear_plant.clicked.connect(self.accion_crear_plantilla)

        form_plant.addRow("Nombre plantilla:", self.txt_plant_nombre)
        form_plant.addRow("Categoría:", self.txt_plant_cat)
        form_plant.addRow("Tiempo estimado:", self.spin_plant_est)
        form_plant.addRow("Recurrencia:", self.combo_plant_rec)
        form_plant.addRow("", self.btn_crear_plant)
        layout.addWidget(card_plant)

        # 5. PIN Opcional y Copias de Seguridad
        card_seg = QFrame(self)
        card_seg.setProperty("card", True)
        col_seg = QVBoxLayout(card_seg)
        col_seg.setSpacing(10)
        col_seg.addWidget(QLabel("<b>5. Seguridad (PIN opcional) y Copias de Seguridad</b>"))

        fila_pin = QHBoxLayout()
        self.txt_nuevo_pin = QLineEdit(self)
        self.txt_nuevo_pin.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_nuevo_pin.setPlaceholderText("Nuevo PIN (mín. 4 dígitos)")
        self.btn_fijar_pin = QPushButton("Establecer PIN", self)
        self.btn_quitar_pin = QPushButton("Quitar PIN", self)
        self.btn_quitar_pin.setProperty("rol", "secundario")
        self.btn_fijar_pin.clicked.connect(self.accion_establecer_pin)
        self.btn_quitar_pin.clicked.connect(self.accion_quitar_pin)
        fila_pin.addWidget(self.txt_nuevo_pin)
        fila_pin.addWidget(self.btn_fijar_pin)
        fila_pin.addWidget(self.btn_quitar_pin)
        col_seg.addLayout(fila_pin)

        fila_bak = QHBoxLayout()
        self.btn_backup_manual = QPushButton("📦 Crear copia manual ahora", self)
        self.btn_backup_usb = QPushButton("🔌 Copiar a USB / carpeta elegida", self)
        self.btn_restaurar = QPushButton("♻ Restaurar desde copia (.db)", self)
        self.btn_restaurar.setProperty("rol", "advertencia")

        self.btn_backup_manual.clicked.connect(self.accion_copia_manual)
        self.btn_backup_usb.clicked.connect(self.accion_copia_usb)
        self.btn_restaurar.clicked.connect(self.accion_restaurar)

        fila_bak.addWidget(self.btn_backup_manual)
        fila_bak.addWidget(self.btn_backup_usb)
        fila_bak.addWidget(self.btn_restaurar)
        col_seg.addLayout(fila_bak)
        layout.addWidget(card_seg)

        layout.addStretch()
        scroll.setWidget(contenedor)
        layout_raiz.addWidget(scroll)

        self.refrescar()

    def _fila_key_edit(self, editor: QKeySequenceEdit) -> QWidget:
        cont = QWidget(self)
        fila = QHBoxLayout(cont)
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(6)
        btn_limpiar = QPushButton("✖ Quitar", cont)
        btn_limpiar.setProperty("rol", "secundario")
        btn_limpiar.clicked.connect(editor.clear)
        fila.addWidget(editor, 1)
        fila.addWidget(btn_limpiar)
        return cont

    def accion_limpiar_todos_los_atajos(self) -> None:
        self.key_iniciar_pausar.clear()
        self.key_finalizar.clear()
        self.key_siguiente.clear()
        self.key_mini.clear()

    def refrescar(self) -> None:
        with self.bd.sesion() as s:
            usr = s.scalar(select(Usuario).limit(1))
            cfg = RepoConfiguracion(s)

            self.txt_usuario.setText(usr.nombre if usr else "")
            self.txt_empresa.setText(cfg.obtener("empresa.nombre", "Gente Util") or "Gente Util")
            self.txt_color_empresa.setText(
                cfg.obtener("empresa.color_primario", "#0F4C81") or "#0F4C81"
            )
            self.txt_logo_ruta.setText(cfg.obtener("empresa.logo_ruta", "") or "")

            tema_actual = usr.tema if usr and usr.tema else "gente_util"
            idx = self.combo_tema.findData(tema_actual)
            if idx >= 0:
                self.combo_tema.setCurrentIndex(idx)

            self.chk_autostart.setChecked(cfg.obtener_bool("sistema.inicio_con_windows", True))
            self.chk_iniciar_oculta.setChecked(
                cfg.obtener_bool("sistema.iniciar_minimizada_bandeja", False)
            )

            self.key_iniciar_pausar.setKeySequence(
                QKeySequence(cfg.obtener("atajo.iniciar_pausar", "") or "")
            )
            self.key_finalizar.setKeySequence(
                QKeySequence(cfg.obtener("atajo.finalizar", "") or "")
            )
            self.key_siguiente.setKeySequence(
                QKeySequence(cfg.obtener("atajo.siguiente_pieza", "") or "")
            )
            self.key_mini.setKeySequence(
                QKeySequence(cfg.obtener("atajo.mini_ventana", "") or "")
            )

            self.spin_rec_cont.setValue(cfg.obtener_int("recordatorio.continuidad_min", 10))
            self.spin_rec_rep.setValue(
                cfg.obtener_int("recordatorio.repetir_sin_respuesta_min", 2)
            )
            self.spin_rec_inact.setValue(
                cfg.obtener_int("recordatorio.inicio_sin_actividad_min", 10)
            )
            self.chk_sonido.setChecked(cfg.obtener_bool("aviso.sonido", True))
            self.spin_meta_pct.setValue(int(cfg.obtener_float("meta.tiempo_efectivo_pct", 80)))

            self.spin_peso_c.setValue(
                int(round(cfg.obtener_float("productividad.peso_cumplimiento", 0.40) * 100))
            )
            self.spin_peso_e.setValue(
                int(round(cfg.obtener_float("productividad.peso_eficiencia", 0.30) * 100))
            )
            self.spin_peso_f.setValue(
                int(round(cfg.obtener_float("productividad.peso_foco", 0.30) * 100))
            )

    def accion_guardar_general(self) -> None:
        suma_pesos = (
            self.spin_peso_c.value() + self.spin_peso_e.value() + self.spin_peso_f.value()
        )
        if suma_pesos != 100:
            QMessageBox.warning(
                self,
                "Pesos de fórmula",
                f"Los tres pesos deben sumar 100 % (actualmente suman {suma_pesos} %).",
            )
            return

        tema = str(self.combo_tema.currentData())
        autostart = self.chk_autostart.isChecked()
        iniciar_oculta = self.chk_iniciar_oculta.isChecked()

        with self.bd.sesion() as s:
            usr = s.scalar(select(Usuario).limit(1))
            if usr:
                usr.nombre = self.txt_usuario.text().strip()
                usr.tema = tema

            cfg = RepoConfiguracion(s)
            cfg.guardar("empresa.nombre", self.txt_empresa.text().strip() or "Gente Util")
            cfg.guardar(
                "empresa.color_primario", self.txt_color_empresa.text().strip() or "#0F4C81"
            )
            cfg.guardar("empresa.logo_ruta", self.txt_logo_ruta.text().strip())
            cfg.guardar("sistema.inicio_con_windows", autostart)
            cfg.guardar("sistema.iniciar_minimizada_bandeja", iniciar_oculta)

            cfg.guardar(
                "atajo.iniciar_pausar", self.key_iniciar_pausar.keySequence().toString()
            )
            cfg.guardar("atajo.finalizar", self.key_finalizar.keySequence().toString())
            cfg.guardar(
                "atajo.siguiente_pieza", self.key_siguiente.keySequence().toString()
            )
            cfg.guardar("atajo.mini_ventana", self.key_mini.keySequence().toString())

            cfg.guardar("recordatorio.continuidad_min", int(self.spin_rec_cont.value()))
            cfg.guardar(
                "recordatorio.repetir_sin_respuesta_min", int(self.spin_rec_rep.value())
            )
            cfg.guardar(
                "recordatorio.inicio_sin_actividad_min", int(self.spin_rec_inact.value())
            )
            cfg.guardar("aviso.sonido", self.chk_sonido.isChecked())
            cfg.guardar("meta.tiempo_efectivo_pct", int(self.spin_meta_pct.value()))
            cfg.guardar(
                "productividad.peso_cumplimiento",
                f"{self.spin_peso_c.value() / 100.0:.2f}",
            )
            cfg.guardar(
                "productividad.peso_eficiencia",
                f"{self.spin_peso_e.value() / 100.0:.2f}",
            )
            cfg.guardar(
                "productividad.peso_foco",
                f"{self.spin_peso_f.value() / 100.0:.2f}",
            )

        try:
            ServicioInicioWindows().sincronizar(autostart)
        except Exception:
            pass

        if self.al_cambiar_tema:
            self.al_cambiar_tema(tema)
        if self.al_cambiar_atajos:
            self.al_cambiar_atajos()

        QMessageBox.information(self, "Guardado", "Configuración actualizada correctamente.")

    def accion_elegir_logo(self) -> None:
        archivo, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar logo de la empresa",
            "",
            "Imágenes (*.svg *.png *.jpg *.jpeg)",
        )
        if archivo:
            self.txt_logo_ruta.setText(archivo)

    def accion_crear_plantilla(self) -> None:
        nombre = self.txt_plant_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Nombre requerido", "Escribe el nombre de la plantilla.")
            return
        cat_txt = self.txt_plant_cat.text().strip()
        est = int(self.spin_plant_est.value()) or None
        rec = str(self.combo_plant_rec.currentData())
        dias = [0, 1, 2, 3, 4] if rec == Recurrencia.DIAS_SEMANA.value else None

        with self.bd.sesion() as s:
            cat_id = RepoCategorias(s).obtener_o_crear(cat_txt).id if cat_txt else None
            RepoPlantillas(s).crear(
                nombre,
                categoria_id=cat_id,
                tiempo_estimado_min=est,
                recurrencia=rec,
                dias_semana=dias,
            )

        self.txt_plant_nombre.clear()
        QMessageBox.information(
            self, "Plantilla creada", f"La plantilla «{nombre}» se propondrá al planear el día."
        )

    def accion_establecer_pin(self) -> None:
        pin = self.txt_nuevo_pin.text().strip()
        try:
            with self.bd.sesion() as s:
                ServicioPIN(s).establecer_pin(pin)
        except ValueError as exc:
            QMessageBox.warning(self, "PIN inválido", str(exc))
            return
        self.txt_nuevo_pin.clear()
        QMessageBox.information(self, "PIN activo", "El PIN quedó activado para este PC.")

    def accion_quitar_pin(self) -> None:
        with self.bd.sesion() as s:
            ServicioPIN(s).desactivar_pin()
        self.txt_nuevo_pin.clear()
        QMessageBox.information(self, "PIN desactivado", "La app ya no pedirá PIN al abrir.")

    def accion_copia_manual(self) -> None:
        with self.bd.sesion() as s:
            copia = ServicioBackups(s).crear_copia(TipoCopia.MANUAL)
            ruta = copia.ruta
        QMessageBox.information(self, "Copia creada", f"Copia guardada en:\n{ruta}")

    def accion_copia_usb(self) -> None:
        carpeta = QFileDialog.getExistingDirectory(
            self, "Elegir USB o carpeta para la copia de seguridad"
        )
        if not carpeta:
            return
        with self.bd.sesion() as s:
            copia = ServicioBackups(s).copiar_a_carpeta_externa(carpeta)
            ruta = copia.ruta
        QMessageBox.information(self, "Copia en carpeta/USB", f"Copia guardada en:\n{ruta}")

    def accion_restaurar(self) -> None:
        archivo, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo de copia de seguridad (.db)",
            "",
            "Base de datos SQLite (*.db)",
        )
        if not archivo:
            return
        with self.bd.sesion() as s:
            try:
                ServicioBackups(s).restaurar_desde_archivo(archivo)
            except Exception as exc:
                QMessageBox.warning(self, "Archivo inválido", str(exc))
                return
        QMessageBox.information(
            self,
            "Copia restaurada",
            "Los datos fueron restaurados correctamente.",
        )
