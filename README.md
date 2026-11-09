# Control de Tiempos — Gente Util

App de escritorio **100 % local** para Windows 10/11 que permite planear el día,
medir con cronómetro el tiempo de cada actividad, recibir recordatorios, calcular
un porcentaje de productividad y exportar reportes en PDF.

> Estado: **Fase 6 completada** (historial filtrable con trazabilidad de ediciones y estadísticas con tendencia).
> Ver el plan completo en [docs/plan-app-control-tiempos.md](docs/plan-app-control-tiempos.md).

## Requisitos

- Windows 10/11
- Python 3.11 o superior (probado con 3.14)
- No requiere permisos de administrador ni internet (después de instalar dependencias)

## Instalación para desarrollo

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

> Si PowerShell bloquea `Activate.ps1`, no hace falta activarlo: basta con usar
> `.\.venv\Scripts\python.exe` directamente, como en los ejemplos.

## Ejecutar

```powershell
.\.venv\Scripts\python.exe src\main.py              # abre la app
.\.venv\Scripts\python.exe src\main.py --bandeja    # inicia minimizada en la bandeja del sistema
.\.venv\Scripts\python.exe src\main.py --verificar  # revisa la base de datos sin interfaz
```

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Dónde se guardan los datos

| Qué | Dónde |
|---|---|
| Base de datos y logs | `%LOCALAPPDATA%\ControlTiempos` |
| Copias de seguridad | `Documentos\ControlTiempos\Copias` |

Para usar otra carpeta (pruebas o versión portable) se define la variable de
entorno `CONTROL_TIEMPOS_DATA_DIR`.

## Estructura

```
├── alembic.ini            # migraciones desde la línea de comandos (desarrollo)
├── requirements*.txt
├── docs/                  # plan, decisiones, documentación técnica, changelog
├── src/
│   ├── main.py            # punto de entrada
│   ├── config/            # nombre, versión y rutas
│   ├── data/              # modelos, conexión, migraciones, semilla, repositorios
│   ├── services/          # lógica de negocio (desde la Fase 2)
│   ├── ui/                # interfaz PySide6
│   ├── reports/           # plantillas PDF (Fase 7)
│   └── assets/            # iconos, sonidos, logo
└── tests/                 # pruebas con pytest
```

## Documentación

- [Documentación técnica](docs/documentacion_tecnica.md)
- [Decisiones](docs/decisiones.md)
- [Changelog](docs/changelog.md)
- [Manual de usuario](docs/manual_usuario.md) (se completa en la Fase 9)
