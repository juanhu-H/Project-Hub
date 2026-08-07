Project Intelligence Hub (PIH) — MVP UTN
MVP funcional basado en el Trabajo Práctico de Orquestación Agéntica Cíclica y Memoria Persistente.
Qué demuestra
Aplicación web con login.
Dashboard con buscador.
Carga de Jira de demostración, Swagger/OpenAPI, documento funcional y transcripción.
Orquestación cíclica:
`Captura → Conocimiento → Análisis → Recomendaciones → Evaluación/Feedback → Aprendizaje`.
Grafo de conocimiento local.
Extracción híbrida de relaciones:
referencias explícitas;
reglas determinísticas;
relaciones semánticas candidatas;
validación humana.
Análisis de consistencia.
Análisis de impacto.
Evaluación heurística y explicable de riesgo.
Reporte diario.
Memoria persistente en SQLite.
Integración opcional con Jira Cloud, Neo4j y un LLM.
Registro de una sesión real de uso.
Arquitectura del MVP
```text
Jira / Swagger / documentos / transcripciones
                      ↓
               Agente de Captura
                      ↓
             Agente de Conocimiento
        extracción de nodos y relaciones
                      ↓
          SQLite + grafo local + Neo4j opcional
                      ↓
                Agente de Análisis
       consistencia + impacto + riesgo heurístico
                      ↓
              Agente de Recomendaciones
                      ↓
           Dashboard + buscador + reporte diario
                      ↓
           validación y feedback del usuario
                      ↓
               Agente de Aprendizaje
```
Agentes implementados
CaptureAgent: incorpora y normaliza fuentes.
KnowledgeAgent: genera nodos y relaciones con evidencia, método y confianza.
AnalysisAgent: ejecuta consistencia, impacto y riesgo.
ReportAgent: responde consultas y genera el reporte diario.
LearningAgent: guarda aprobaciones, rechazos y lecciones.
Las responsabilidades conceptuales del TP se consolidan para reducir costo, latencia y complejidad operativa.
Requisitos
Python 3.11+
Node.js 20+
npm
Opcional: Docker Desktop
Ejecución rápida sin Docker
1. Backend
```bash
cd backend
python -m venv .venv
```
Windows:
```bash
.venv\Scripts\activate
```
Linux/macOS:
```bash
source .venv/bin/activate
```
Luego:
```bash
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```
En Linux/macOS reemplace `copy` por:
```bash
cp .env.example .env
```
API: http://localhost:8000  
Swagger: http://localhost:8000/docs
2. Frontend
En otra terminal:
```bash
cd frontend
npm install
npm run dev
```
Aplicación: http://localhost:5173
Usuario de demostración
Email: `admin@pih.local`
Contraseña: `admin123`
Flujo recomendado para la demo
Iniciar sesión.
Presionar Cargar datos demo.
Presionar Ejecutar ciclo.
Consultar: `¿Qué impacta la historia HU-1234?`
Revisar evidencias y puntaje de riesgo.
Aprobar o rechazar una relación candidata.
Abrir el reporte diario.
Descargar o mostrar el registro de sesión.
Integración real con Jira Cloud
Configure en `backend/.env`:
```env
JIRA_BASE_URL=https://tu-dominio.atlassian.net
JIRA_EMAIL=usuario@empresa.com
JIRA_API_TOKEN=token
JIRA_JQL=project = DEMO ORDER BY updated DESC
```
Después ejecute:
```http
POST /api/ingest/jira
```
El MVP usa Jira REST API como mecanismo principal. MCP queda como evolución futura.
Neo4j opcional
El sistema funciona con grafo local persistido en SQLite. Para sincronizar relaciones en Neo4j:
```env
NEO4J_ENABLED=true
NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=pih-password
```
Con Docker Compose, Neo4j queda disponible en http://localhost:7474.
LLM opcional
El MVP funciona sin LLM. Puede configurarse un proveedor compatible con OpenAI:
```env
LLM_ENABLED=true
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```
El LLM solo se usa para redactar una respuesta; las relaciones y el riesgo siempre se basan en evidencia persistida.
Ejecución con Docker
```bash
docker compose up --build
```
Frontend: http://localhost:5173
Backend: http://localhost:8000
Neo4j Browser: http://localhost:7474
Pruebas
```bash
cd backend
pytest
```
Entregables sugeridos
Repositorio GitHub.
Aplicación publicada.
Capturas reales.
Log de sesión: endpoint `/api/session-log`.
Arquitectura actualizada.
UML de componentes y secuencia.
Tabla de tecnologías.
Evaluación UX/UI con Nielsen.
Matriz de riesgos de ciberseguridad.
Reflexión sobre LLM/SLM local.
