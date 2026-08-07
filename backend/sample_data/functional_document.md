# Relevamiento funcional Prestadores

Documento: DOC-PRESTADORES-01

## Alcance

La historia HU-1234 modifica la búsqueda de prestadores y utiliza:

- GET /api/prestadores
- POST /api/prestadores/buscar

La historia HU-1250 agrega filtros de especialidad.

## Reglas

1. El usuario debe poder buscar por nombre, especialidad y ubicación.
2. Los cambios deben validarse mediante CP-1023.
3. El endpoint GET /api/prestadores/{cuit} debe validar el formato del CUIT.
