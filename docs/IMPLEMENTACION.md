# Guía de implementación práctica

## Alcance defendible para el 17 de agosto

### Incluido en el MVP

- Jira REST o datos demo.
- Swagger/OpenAPI.
- Documento funcional.
- Casos de prueba.
- Transcripción cargada manualmente.
- Grafo local y Neo4j opcional.
- Relaciones explícitas aprobadas automáticamente.
- Relaciones semánticas candidatas con validación humana.
- Riesgo heurístico.
- Buscador trazable.
- Reporte diario.
- Login y autorización por proyecto.
- Log de auditoría.

### Fuera del MVP

- Integración automática con Meet/Teams.
- MCP para Jira.
- Predicción estadística real de demoras.
- Extracción semántica totalmente autónoma.
- Nueve procesos independientes.
- Aprendizaje o ajuste del modelo.

## Decisión sobre el grafo

El grafo no “adivina” relaciones. El proceso tiene cuatro capas:

1. Extracción estructurada.
2. Referencias explícitas.
3. Relación candidata por similitud.
4. Aprobación humana.

Toda relación almacena:

- origen;
- destino;
- tipo;
- método;
- confianza;
- evidencia;
- estado.

## Modelo de riesgo

La evaluación es una heurística transparente:

- impacto: 25 %;
- dependencias críticas: 25 %;
- ausencia de pruebas: 20 %;
- documentación faltante: 15 %;
- historial de incidentes: 15 %.

No debe describirse como predicción.

## Seguridad

- Contraseñas con Argon2.
- JWT.
- Asociación usuario-proyecto.
- Validación de acceso en backend.
- Variables secretas en `.env`.
- Auditoría.
- CORS restringido.
- No exponer tokens de Jira al frontend.

## Sesión que debe grabarse

1. Login.
2. Carga demo.
3. Ejecución del ciclo.
4. Consulta HU-1234.
5. Visualización de impacto y riesgo.
6. Aprobación de relación.
7. Nueva consulta.
8. Reporte diario.
9. Log de auditoría.
