# Arquitectura del Bot de Segmentaci\u0019n de PDFs por Resoluci\u0019n

## \u001andice

1. [Visión General](#visión-general)
2. [Arquitectura de Alto Nivel](#arquitectura-de-alto-nivel)
3. [Pipeline de Procesamiento](#pipeline-de-procesamiento)
4. [Componentes del Backend](#componentes-del-backend)
5. [Componentes del Frontend](#componentes-del-frontend)
6. [Dise\u0011o para Alto Rendimiento](#diseño-para-alto-rendimiento)
7. [Mecanismos de Tolerancia a Fallos](#mecanismos-de-tolerancia-a-fallos)
8. [Monitoreo y Observabilidad](#monitoreo-y-observabilidad)
9. [Desiciones de Dise\u0011o](#decisiones-de-diseño)

---

## Visión General

El sistema est\u0011a dise\u0011ado para procesar documentos PDF de gran volumen (decenas de miles de p\u0001ginas por d\u0001a) e identificando autom\u0001ticamente "c\u0019digos de resoluci\u0019n" en cada p\u0001gina. La clave del dise\u0011o es un **pipeline de 3 etapas desacopladas** que permite que cada componente avance a su propia velocidad.

### Objetivos de Dise\u0011o

1. **Alto Rendimiento**: Procesar decenas de miles de p\u0001ginas diarias
2. **Escalabilidad**: Capacidad de escalar horizontalmente (m\u0001s trabajadores)
3. **Tolerancia a Fallos**: Manejo robusto de errores sin bloquear el procesamiento
4. **Bajo Acoplamiento**: Componentes independientes y reutilizables
5. **Monitoreo Integrado**: M\u0009tricas detalladas para identificar cuellos de botella
6. **Ejecuci\u0019n 24/7**: Dise\u0011ado para servicios de Windows

### Principios de Arquitectura

- **Single Responsibility**: Cada m\u0013dulo tiene una sola responsabilidad
- **Asincron\u0001a por Defecto**: Uso extensivo de async/await para I/O-bound
- **Pipeline Pattern**: Procesamiento en etapas con colas intermedias
- **Backpressure**: Control de flujo para evitar saturaci\u0019n
- **Idempotencia**: Reprocesar no debe duplicar resultados

---

## Arquitectura de Alto Nivel

```
┌─────────────────────────────────────────────────────────────────┐
│                           USUARIO                                 │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │   Uploader   │  │  Job List    │  │   Stats Panel        │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                        │              │                          │    │
│                        ▼              ▼                          ▼    │
│                 WebSocket      REST API        REST API         │
└────────────────────────────┬───────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                        │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    API LAYER                               ││
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   ││
│  │  │ /upload  │  │ /jobs    │  │ /status  │  │ /download│   ││
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘   ││
│  └─────────────────────────────────────────────────────────────┘│
│                                 │                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              PIPELINE ORCHESTRATOR                         ││
│  │  ┌─────────────────────────────────────────────────────────┐││
│  │  │  Stage 1 Queue ─────► Stage 2 Queue ─────► Stage 3 Queue │││
│  │  │       │                   │                     │         │││
│  │  │       ▼                   ▼                     ▼         │││
│  │  │  ┌─────────┐       ┌─────────┐           ┌─────────┐   │││
│  │  │  │ Stage 1 │       │ Stage 2 │           │ Stage 3 │   │││
│  │  │  │ (Render+│       │ (AI     │           │ (Group +│   │││
│  │  │  │  OCR)   │       │ Classif.)│           │  PDF)    │   │││
│  │  │  └─────────┘       └─────────┘           └─────────┘   │││
│  │  └─────────────────────────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────────┘│
│                                 │                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    SERVICES LAYER                            ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐││
│  │  │ PDF Renderer │  │ OCR Engine   │  │ DeepSeek Client     │││
│  │  │ (pypdfium2)  │  │ (Tesseract+  │  │ (httpx.AsyncClient) │││
│  │  └──────────────┘  │ PaddleOCR)   │  └─────────────────────┘││
│  │                     └──────────────┘                         ││
│  └─────────────────────────────────────────────────────────────┘│
│                                 │                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    DATA LAYER                               ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────┐││
│  │  │ PostgreSQL  │  │ File Storage │  │ Prometheus Metrics  │││
│  │  │ (asyncpg)   │  │ (Local Disk) │  │ (prometheus_client) │││
│  │  └──────────────┘  └──────────────┘  └─────────────────────┘││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## Pipeline de Procesamiento

### Concepto

El **pipeline de 3 etapas desacopladas** es el coraz\u0013n de la arquitectura. Cada etapa tiene caracter\u0001sticas diferentes:

| Etapa | Tipo | Parallelismo | Limitante | Descripci\u0019n |
|-------|------|-------------|-----------|--------------|
| 1 | CPU-bound | ProcessPoolExecutor | N\u0015cleos CPU | Renderizado + OCR |
| 2 | I/O-bound | asyncio + Semaphore | API Rate Limit | Clasificaci\u0019n AI |
| 3 | Ligera | Async simple | Disco | Agrupaci\u0019n + PDF |

### Flujo Detallado

```
1. UPLOAD PDF
   │
   ▼
2. CREAR JOB EN BASE DE DATOS
   │  - Insertar job en tabla `jobs`
   │  - Insertar todas las p\u0001ginas en tabla `pages`
   │  - Estado: PENDING
   ▼
3. SUBMIT A PIPELINE
   │
   ▼
4. STAGE 1: RENDER + OCR (CPU-bound)
   │
   ├─► Por cada p\u0001gina:
   │    1. Renderizar PDF page → Imagen (pypdfium2)
   │    2. Extraer texto con OCR (Tesseract/PaddleOCR)
   │    3. Guardar imagen temporal y texto en DB
   │    4. Marcar page.stage1_complete = true
   │
   ├─► Parallelismo: ProcessPoolExecutor(N-1)
   ├─► Queue: asyncio.Queue(maxsize=1000)
   ├─► Backpressure: Espera si cola est\u0001 llena
   │
   ▼
5. STAGE 2: AI CLASSIFICATION (I/O-bound)
   │
   ├─► Por cada p\u0001gina con texto OCR:
   │    1. Agrupar en lotes de AI_BATCH_SIZE (8-10)
   │    2. Enviar a DeepSeek: "¿Cual es el c\u0019digo de resoluci\u0019n?"
   │    3. Parsear respuesta JSON: {"codigo_resolucion": "..."}
   │    4. Guardar resolution_code en DB
   │    5. Marcar page.stage2_complete = true
   │
   ├─► Parallelismo: asyncio.Semaphore(max=50-150)
   ├─► Rate Limiting: Configurable seg\u001an API key
   ├─► Retries: Backoff exponencial (1s, 2s, 4s, ...)
   │
   ▼
6. STAGE 3: GROUPING + PDF (Ligera)
   │
   ├─► Cuando todas las p\u0001ginas tienen resolution_code:
   │    1. Agrupar p\u0001ginas consecutivas con mismo c\u0019digo
   │    2. Para cada grupo:
   │       a. Crear PDF con PyMuPDF (insert_pdf con rango)
   │       b. Guardar informaci\u0019n en resolution_groups
   │    3. Crear ZIP con todos los PDFs
   │    4. Marcar job.status = COMPLETED
   │
   ├─► Parallelismo: Sincrono (poco trabajo, no es cuello)
   │
   ▼
7. NOTIFICAR COMPLETADO
   │  - Actualizar DB
   │  - Notificar por WebSocket
   │  - Habilitar descargas
   ▼
8. DESCARGA DE RESULTADOS
```

### Caracter\u0001sticas del Pipeline

#### Desacoplamiento

- **Colas entre etapas**: Cada etapa consume de su cola y produce para la siguiente
- **Velocidades independientes**: Stage 1 (CPU) puede ser m\u0001s r\u0001pida que Stage 2 (API)
- **Backpressure**: Si Stage 2 se satura, Stage 1 se ralentiza autom\u0001ticamente

#### Tolerancia a Fallos

- **P\u0001gina individual**: Si una p\u0001gina falla, no bloquea el resto
- **Reintentos**: Configurables por etapa (default: 3 intentos)
- **Idempotencia**: Reprocesar una p\u0001gina no duplicar\u0001 resultados
- **Recovery**: Al reiniciar, los trabajos en curso contin\u0001an desde donde se quedaron

#### Eficiencia

- **Streaming**: Nunca carga el PDF completo en memoria
- **Procesamiento incremental**: Las m\u0009tricas se actualizan en tiempo real
- **Batch processing**: AI clasifica m\u0016ltiples p\u0001ginas en una sola llamada

---

## Componentes del Backend

### 1. API Layer (`app/api/`)

#### Routers

- **upload.py**: Maneja la subida de PDFs
  - Validaci\u0019n de archivo (tipo, tama\u0011o)
  - Creaci\u0019n de job en DB
  - Inicio de procesamiento

- **download.py**: Maneja descargas
  - ZIP completo del job
  - PDFs individuales por resoluci\u0019n
  - Im\u0001genes de p\u0001ginas (debug)
  - Texto OCR de p\u0001ginas (debug)

#### Middleware

- CORS: Configurado desde .env
- Logging: Todas las requests se loguean
- Error Handling: Respuestas JSON estructuradas

### 2. Core Layer (`app/core/`)

#### Settings (`settings.py`)

- Carga de variables de entorno con Pydantic Settings
- Validaci\u0019n de tipos y rangos
- Conversi\u0019n autom\u0001tica (ej: MB → bytes)
- Valores por defecto para desarrollo

#### Logging (`logging.py`)

- Formato estructurado para todos los logs
- M\u0016ltiples handlers (consola, archivo)
- Rotaci\u0019n de logs (10MB, 5 backups)
- Niveles configurables por entorno

#### Metrics (`metrics.py`)

- Prometheus Client para m\u0009tricas
- M\u0009tricas por etapa (latencia, throughput, errores)
- M\u0009tricas de sistema (colas, workers, etc.)
- Server HTTP para /metrics en puerto configurable

### 3. Database Layer (`app/db/`)

#### Base (`base.py`)

- SQLAlchemy 2.0 async con asyncpg
- Engine configurado con pool de conexiones
- Session factory para FastAPI
- Inicializaci\u0019n autom\u0001tica de tablas

#### Models (`models.py`)

- **Job**: Trabajo de procesamiento
- **Page**: P\u0001gina individual con estado detallado
- **ResolutionGroup**: Grupo de p\u0001ginas con mismo c\u0019digo
- **JobStats**: Estad\u0001sticas agregadas del trabajo
- **SystemStats**: Estad\u0001sticas del sistema

#### Migraciones (Alembic)

- Control de versiones de esquema
- Migraciones autom\u0001ticas en inicio
- Soporte para rollback

### 4. Render Layer (`app/render/`)

#### PDFRenderer (`pdf_renderer.py`)

- Usa **pypdfium2** (PDFium de Google)
- Renderizado en thread pool (no bloquea event loop)
- Configurable: DPI, escala, color space
- Optimizado para OCR (150-200 DPI, escala de grises)

```python
# Ejemplo de uso
image, render_time = await renderer.render_page(pdf_path, page_number)
```

### 5. OCR Layer (`app/ocr/`)

#### Interfaz OCREngine

```python
class OCREngine(ABC):
    async def extract_text(image: Image) -> Tuple[str, float, float]:
        """Extrae texto y devuelve (text, confidence, processing_time)"""
        pass
```

#### Implementaciones

1. **TesseractOCREngine**
   - R\u0001pido (CPU-optimizado)
   - Soporta m\u0016ltiples idiomas (spa, eng, etc.)
   - Devuelve score de confianza

2. **PaddleOCREngine**
   - M\u0001s preciso ( GPU/CPU)
   - Usado como fallback cuando Tesseract tiene baja confianza
   - Soporte para CUDA

3. **HybridOCREngine**
   - Usa Tesseract primero
   - Si confianza < OCR_CONFIDENCE_THRESHOLD, usa PaddleOCR
   - Configurable desde .env

### 6. AI Layer (`app/ai/`)

#### DeepSeekClient (`deepseek_client.py`)

- **httpx.AsyncClient**: Cliente HTTP asincr\u0019nico
- **asyncio.Semaphore**: Control de concurrencia
- **Batch processing**: 5-10 p\u0001ginas por llamada
- **Exponential backoff**: Reintentos inteligentes
- **Response parsing**: Extrae JSON estructurado

```python
# Ejemplo de uso
resolution_code, response, processing_time = await client.classify_resolution(text)
```

#### Prompt Engineering

El prompt para DeepSeek est\u0001 optimizado:

```
Eres un experto en procesamiento de documentos administrativos.
Tu tarea es identificar el 'código de resolución' en el texto.

INSTRUCCIONES:
1. Analiza el texto cuidadosamente.
2. Identifica el código de resolución (formato variable).
3. NO inventes un código si no lo encuentras claramente.
4. Si no encuentras código, devuelve cadena vacía.

TEXTO: ---{text}---

RESPONDE: {"codigo_resolucion": "..."}
```

### 7. PDF Layer (`app/pdf/`)

#### PDFAssembler (`assembler.py`)

- Usa **PyMuPDF (fitz)**
- Crea nuevos PDFs insertando p\u0001ginas de origen
- Sin recompresi\u0019n (preserva calidad original)
- Soporte para ZIP de m\u0016ltiples PDFs

```python
# Crear PDF para una resoluci\u0019n
output_path = await assembler.create_resolution_pdf(
    source_pdf, page_numbers, resolution_code
)

# Crear ZIP con todos los PDFs
await assembler.create_zip_archive(pdf_files, output_zip_path)
```

### 8. Pipeline Layer (`app/pipeline/`)

#### Orchestrator (`orchestrator.py`)

- Gestiona las 3 etapas del pipeline
- Crea y monitorea workers
- Mantiene estado de progreso
- Implementa backpressure

#### Tasas de Datos

```python
@dataclass
class Stage1Task:
    job_id: int
    page_id: int
    page_number: int
    pdf_path: Path
    temp_dir: Path

@dataclass
class Stage2Task:
    job_id: int
    page_id: int
    page_number: int
    ocr_text: str
    confidence: float
    engine: str
```

#### Progress Tracking

```python
@dataclass
class JobProgress:
    job_id: int
    total_pages: int
    stage1_pending: int
    stage1_processing: int
    stage1_completed: int
    stage1_failed: int
    # ... (similar para stage2 y stage3)
    
    # Throughput metrics
    render_times: List[float]
    ocr_times: List[float]
    ai_times: List[float]
    
    # Calculated metrics
    def get_overall_progress(self) -> float: ...
    def get_throughput(self) -> float: ...
    def get_eta(self) -> Optional[float]: ...
    def get_avg_latency(self, stage: str) -> float: ...
    def get_error_rate(self) -> float: ...
```

### 9. WebSocket Layer (`app/websocket/`)

#### WebSocketManager (`handler.py`)

- Maneja conexiones WebSocket
- Broadcast peri\u0013dico de updates (configurable: 2 segundos)
- Soporta suscripci\u0019n por job_id
- Reconexi\u0019n autom\u0001tica

```python
# Ejemplo de uso en FastAPI
@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: int):
    await ws_manager.connect(websocket, job_id)
```

---

## Componentes del Frontend

### Arquitectura

```
frontend/
├── src/
│   ├── api/           # Cliente HTTP tipado
│   │   └── client.ts  # Axios con interceptores
│   │
│   ├── components/    # Componentes React reutilizables
│   │   ├── Layout.tsx        # Layout principal
│   │   ├── PDFUploader.tsx   # Dropzone para PDF
│   │   ├── JobList.tsx       # Lista de trabajos
│   │   ├── JobFilter.tsx     # Filtros de estado
│   │   ├── ProgressBar.tsx   # Barra de progreso
│   │   ├── ResolutionList.tsx # Lista de resoluciones
│   │   ├── PageList.tsx      # Lista de p\u0001ginas
│   │   ├── StatsPanel.tsx    # Panel de estad\u0001sticas
│   │   └── status.ts         # Utilidades de estado
│   │
│   ├── hooks/         # React hooks personalizados
│   │   └── useWebSocket.ts   # Manejo de WebSocket
│   │
│   ├── pages/         # P\u0001ginas de la aplicaci\u0019n
│   │   ├── HomePage.tsx
│   │   ├── JobsPage.tsx
│   │   └── JobDetailPage.tsx
│   │
│   ├── utils/         # Utilidades
│   │   └── status.ts
│   │
│   ├── App.tsx        # Componente principal
│   ├── main.tsx       # Entry point
│   └── index.css      # Estilos (Tailwind)
│
├── package.json
├── vite.config.ts
└── tsconfig.json
```

### Cliente HTTP (`api/client.ts`)

- **Axios** con configuraci\u0019n base
- Interceptores para manejo de errores
- Toasts autom\u0001ticos para errores HTTP
- Funciones tipadas para cada endpoint

### WebSocket Hook (`hooks/useWebSocket.ts`)

```typescript
export function useWebSocket(options: UseWebSocketOptions = {}): WebSocketState {
    // Maneja conexi\u0019n, reconexi\u0019n, mensajes
    // Proporciona: isConnected, lastMessage, send, disconnect
}

export function useJobStatus(jobId: number): WebSocketState & { 
    jobStatus?: JobStatus; 
    isLoading: boolean 
} {
    // Hook especializado para un job
    // Combina WebSocket + fetch inicial
}
```

### StatsPanel Component

El componente m\u0001s importante, con:

- **Grafico de throughput**: Line chart con Chart.js
- **Contadores en vivo**: P\u0001ginas totales, procesadas, etc.
- **ETA din\u0001mico**: Recalculado cada 2 segundos
- **Latencia por etapa**: Grafico de l\u0001neas m\u0016ltiples
- **Tama\u0011os de cola**: del pipeline
- **Alerta visual**: Si error rate > 10%

---

## Dise\u0011o para Alto Rendimiento

### 1. Separaci\u0019n CPU-bound vs I/O-bound

| Componente | Tipo | Mecanismo | Razonamiento |
|-----------|------|-----------|-------------|
| Renderizado | CPU-bound | ThreadPoolExecutor | pypdfium2 es bloqueante |
| OCR | CPU-bound | ThreadPoolExecutor | Tesseract es CPU-intensivo |
| AI Classification | I/O-bound | asyncio + Semaphore | Esperando respuesta HTTP |
| PDF Assembly | Ligera | Async simple | Poco procesamiento |

### 2. Optimizaciones de Renderizado

- **150-200 DPI**: Suficiente para OCR, reduce tiempo a la mitad vs 300 DPI
- **Escala de grises**: Reduce tama\u0011o de imagen vs RGB
- **pypdfium2**: M\u0001s r\u0001pido que alternativas (Ghostscript, etc.)

### 3. Optimizaciones de OCR

- **Tesseract primero**: 3-5x m\u0001s r\u0001pido que PaddleOCR en CPU
- **Fallback inteligente**: Solo usa PaddleOCR si confianza < 0.7
- **Procesamiento paralelo**: ProcessPoolExecutor para m\u0016ltiples p\u0001ginas

### 4. Optimizaciones de AI

- **Batch processing**: 5-10 p\u0001ginas por llamada a DeepSeek
- **Concurrencia controlada**: Semaphore limita solicitudes simult\u0001neas
- **Backoff exponencial**: Para rate limiting y errores temporales
- **Prompt optimizado**: Minimiza tokens, maximiza precisi\u0019n

### 5. Optimizaciones de PDF

- **PyMuPDF insert_pdf**: Copia p\u0001ginas sin reconversi\u0019n
- **Sin recompresi\u0019n**: Preserva calidad original
- **ZIP eficiente**: Compresi\u0019n est\u0001ndar con zipfile

### 6. Optimizaciones de Database

- **asyncpg**: Driver asincr\u0019nico para PostgreSQL
- **SQLAlchemy 2.0 async**: Soporte nativo para async/await
- **Indices**: En todas las columnas frecuentes (job_id, status, etc.)
- **Pool de conexiones**: Tama\u0011o configurable

### 7. Pipeline Optimizations

- **Colas con limite**: Evita saturaci\u0019n de memoria
- **Backpressure**: Stage 1 se ralentiza si Stage 2 est\u0001 llena
- **Procesamiento incremental**: Estad\u0001sticas actualizadas en vivo
- **Idempotencia**: Reprocesar no duplica trabajo

---

## Mecanismos de Tolerancia a Fallos

### 1. Manejo de Errores por P\u0001gina

- Cada p\u0001gina se procesa independientemente
- Si una p\u0001gina falla, no bloquea el resto del job
- Estados en DB: pending → processing → completed/failed
- Retry count configurable

### 2. Reintentos Inteligentes

```python
# Stage 1 (Render+OCR)
max_retries = 3
backoff = [1, 2, 4]  # segundos

# Stage 2 (AI Classification)
max_retries = 3
backoff_base = 1.0
backoff_max = 30.0
# Para rate limit (429): usa Retry-After header
```

### 3. Recovery de Trabajos

- Al reiniciar el servicio, los trabajos en estado "processing" contin\u0001an
- El orchestrator verifica que p\u0001ginas tienen stage1_complete/stage2_complete
- Las p\u0001ginas sin completar se reprocesan

### 4. Validaciones

- **Tipo de archivo**: Solo .pdf
- **Tama\u0011o m\u0001ximo**: Configurable (default 1GB)
- **Page count**: Se valida que el PDF tenga p\u0001ginas
- **Sanitizaci\u0019n**: Nombres de archivo seguros

---

## Monitoreo y Observabilidad

### M\u0009tricas de Prometheus

#### Job Metrics
- `pdf_bot_job_created_total` (status)
- `pdf_bot_job_completed_total` (status)
- `pdf_bot_job_duration_seconds`

#### Page Metrics
- `pdf_bot_page_processed_total` (stage, status)
- `pdf_bot_page_errors_total` (stage, error_type)

#### Stage Latency
- `pdf_bot_render_latency_seconds`
- `pdf_bot_ocr_latency_seconds`
- `pdf_bot_ai_latency_seconds`
- `pdf_bot_pdf_assembly_latency_seconds`

#### Queue Metrics
- `pdf_bot_stage1_queue_size`
- `pdf_bot_stage2_queue_size`
- `pdf_bot_stage3_queue_size`

#### Throughput
- `pdf_bot_pages_per_minute`
- `pdf_bot_ai_requests_per_minute`

#### System
- `pdf_bot_active_workers`
- `pdf_bot_active_ai_requests`

#### Resolution
- `pdf_bot_resolutions_detected_total`
- `pdf_bot_pages_per_resolution`

### Endpoint de M\u0009tricas

```
GET /metrics
```

Devuelve todas las m\u0009tricas en formato Prometheus.

### Configuraci\u0019n

```env
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
```

---

## Decisiones de Dise\u0011o

### \u0009Por qu\u0009 pypdfium2 en lugar de PyMuPDF para renderizado?

**Razones:**
1. **Rendimiento**: pypdfium2 es significativamente m\u0001s r\u0001pido
2. **Precisi\u0019n**: Mejor calidad de renderizado para OCR
3. **Memoria**: M\u0001s eficiente en uso de memoria
4. **Simplicidad**: API m\u0001s simple y directa

**Compensaci\u0019n:**
- PyMuPDF se usa para el ensamblado final de PDFs (insert_pdf)
- Cada herramienta en lo que hace mejor

### \u0009Por qu\u0009 Tesseract + PaddleOCR en lugar de solo uno?

**Razones:**
1. **Velocidad**: Tesseract es 3-5x m\u0001s r\u0001pido en CPU
2. **Precisi\u0019n**: PaddleOCR tiene mejor accuracy para textos complejos
3. **Flexibilidad**: Configurable para usar solo Tesseract o solo PaddleOCR
4. **Fallback**: PaddleOCR como respaldo cuando Tesseract tiene baja confianza

**Configuraci\u0019n recomendada:**
- OCR_ENGINE=auto (hybrid)
- OCR_CONFIDENCE_THRESHOLD=0.7
- OCR_FALLBACK_ENABLED=true

### \u0009Por qu\u0009 asyncpg en lugar de psycopg2?

**Razones:**
1. **Asincr\u0019nico**: asyncpg es 100% async, psycopg2 es s\u0001ncrono
2. **Rendimiento**: asyncpg usa el protocolo binario de PostgreSQL
3. **Compatibilidad**: Dise\u0011ado para asyncio nativo
4. **Pool de conexiones**: Mejor implementaci\u0019n de connection pooling

**Compensaci\u0019n:**
- psycopg2 tiene m\u0001s documentaci\u0019n y comunidad
- Para migraciones, usamos psycopg2 temporalmente en Alembic

### \u0009Por qu\u0009 3 etapas desacopladas?

**Razones:**
1. **Diferentes caracter\u0001sticas**: CPU-bound vs I/O-bound vs Ligera
2. **Paralelismo \u0009ptimo**: Cada etapa usa el mecanismo adecuado
3. **Backpressure**: Control de flujo natural entre etapas
4. **Tolerancia a fallos**: Aislamiento de errores por etapa
5. **Monitoreo**: M\u0009tricas detalladas por etapa

**Alternativa rechazada:**
- Pipeline lineal: Todas las p\u0001ginas en secuencia
  - Problema: Cuello de botella en la etapa m\u0001s lenta
  - Problema: No aprovecha paralelismo CPU/I/O

### \u0009Por qu\u0009 WebSocket en lugar de Polling?

**Razones:**
1. **Eficiencia**: WebSocket usa 1 conexi\u0019n vs polling (m\u0016ltiples requests)
2. **Tiempo real**: Actualizaciones inmediatas vs delay de polling
3. **Escalabilidad**: Menos overhead en el servidor
4. **Bidireccional**: Permite notificaciones server-to-client

**Compensaci\u0019n:**
- Complejidad adicional en el backend
- Manejo de conexiones persistententes
- Reconexi\u0019n y heartbeats necesarios

### \u0009Por qu\u0009 NSSM en lugar de otros?

**Razones (Windows espec\u0001fico):**
1. **Nativo**: NSSM es espec\u0001fico para Windows Services
2. **Simple**: Configuraci\u0019n sencilla via line de comandos
3. **Fiable**: Mantenido y usado en producci\u0019n
4. **Flexible**: Soporta cualquier ejecutable

**Alternativas rechazadas:**
- Docker: Requiere virtualizaci\u0019n (no disponible en el servidor)
- WSL: Requiere virtualizaci\u0019n
- python-windows-service: Menos flexible, m\u0001s dif\u0001cil de configurar

### \u0009Por qu\u0009 no usar Celery+Redis?

**Razones:**
1. **Requisito**: No usar Docker (Celery+Redis t\u0001picamente en Docker)
2. **Complejidad**: Celery a\u0011ade m\u0001s componentes (broker, worker, beat)
3. **Windows**: Redis nativo en Windows no es oficial
4. **Alternativa**: asyncio + ProcessPoolExecutor es suficiente

**Compensaci\u0019n:**
- Menos "enterprise-ready" para flujos complejos
- Pero suficiente para este caso de uso

**Futuro:**
- Si se necesita broker real, usar Memurai (Redis-compatible, nativo Windows)
- La arquitectura actual est\u0001 preparada para esta migraci\u0019n

---

## Conclusiones

La arquitectura del Bot de Segmentaci\u0019n de PDFs por Resoluci\u0019n ha sido dise\u0011ada con los siguientes principios en mente:

1. **Alto Rendimiento**: Pipeline de 3 etapas desacopladas para m\u0001ximo throughput
2. **Escalabilidad**: Uso eficiente de recursos (CPU, I/O, memoria)
3. **Tolerancia a Fallos**: Manejo robusto de errores en cada nivel
4. **Observabilidad**: M\u0009tricas detalladas para monitoreo
5. **Simplicidad Operativa**: Despliegue y configuraci\u0019n sencillos en Windows
6. **Flexibilidad**: Configurable para diferentes entornos y necesidades

Esta arquitectura permite procesar decenas de miles de p\u0001ginas diarias en un servidor Windows f\u0001sico, sin depender de virtualizaci\u0019n, y con m\u0001nimo mantenimiento.
