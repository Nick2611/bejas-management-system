# Bejas

## Ejecutar la aplicación

```bash
docker compose up --build
```

La aplicación queda disponible en `http://localhost:5173`. En una base vacía
se crea el administrador inicial configurado por
`BOOTSTRAP_ADMIN_USERNAME` y `BOOTSTRAP_ADMIN_PASSWORD`. Alembic crea el
esquema `public` si no existe y carga el catálogo inicial de productos sin
sobrescribir productos existentes.

## Ejecutar todas las pruebas

### Locales, sin Docker

```bash
./test-local.sh
```

Este comando sincroniza `back/.venv` desde `uv.lock` y ejecuta las pruebas
unitarias con `pytest`. La prueba de integración PostgreSQL se omite
automáticamente, por lo que no hace falta tener Docker ni una base levantada.

También pueden ejecutarse directamente desde `back/`:

```bash
uv sync --dev
uv run pytest -q
```

### Integración completa con Docker

```bash
./test.sh
```

El backend de pruebas usa una instancia PostgreSQL temporal y separada. Las
dependencias se instalan desde `uv.lock` y `package-lock.json`. El script
construye ambas imágenes, ejecuta backend y frontend en orden y detiene la base
temporal al finalizar.
