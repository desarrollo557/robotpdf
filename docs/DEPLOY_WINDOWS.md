# Despliegue en Windows (Sin Virtualizaci\u0013n)

## \u001andice

1. [Requisitos Previos](#requisitos-previos)
2. [Instalaci\u0013n de Dependencias](#instalaci\u0013n-de-dependencias)
3. [Configuraci\u0013n del Entorno](#configuraci\u0013n-del-entorno)
4. [Configuraci\u0013n de la Base de Datos](#configuraci\u0013n-de-la-base-de-datos)
5. [Build del Frontend](#build-del-frontend)
6. [Instalaci\u0013n como Servicios de Windows](#instalaci\u0013n-como-servicios-de-windows)
7. [Configuraci\u0013n Final](#configuraci\u0013n-final)
8. [Operaciones B\u0001sicas](#operaciones-b\u0001sicas)
9. [Monitoreo](#monitoreo)
10. [Troubleshooting](#troubleshooting)
11. [Actualizaciones](#actualizaciones)

---

## Requisitos Previos

### 1. Sistema Operativo

- **Windows 10** (64-bit) o superior
- **Windows Server 2019** o 2022 (64-bit)
- **Requisito cr\u0001tico**: NO requiere Docker, WSL2, Hyper-V ni VirtualBox
- **Nota**: El equipo NO debe tener virtualizaci\u0013n habilitada en BIOS

### 2. Hardware M\u0001nimo

| Componente | M\u0001nimo | Recomendado (Alto Volumen) |
|-----------|---------|-----------------------------|
| CPU | 4 n\u000acleos | 8+ n\u000acleos |
| RAM | 8 GB | 16+ GB |
| Disco | 10 GB (SSD) | 50+ GB (SSD NVMe) |
| GPU | No requerido | Opcional (para PaddleOCR) |

### 3. Cuentas de Usuario

- El servicio se ejecutar\u0001 como **LocalSystem** (no requiere usuario interactivo)
- Alternativamente, se puede configurar para usar una cuenta de servicio espec\u0001fica

---

## Instalaci\u0013n de Dependencias

### Paso 1: Instalar Python 3.11+

1. **Descargar Python**: 
   - Ir a https://www.python.org/downloads/windows/
   - Descargar la \u000altima versi\u0013n de Python 3.11 o 3.12 (64-bit)

2. **Instalar**:
   - Ejecutar el instalador
   - **Marcar** "Add Python to PATH" (IMPORTANTE)
   - **No marcar** "Install launcher for all users" (opcional)
   - Completar la instalaci\u0013n

3. **Verificar**:
   ```cmd
   python --version
   pip --version
   ```
   Deber\u0001an mostrar versiones de Python 3.11+

---

### Paso 2: Instalar Node.js LTS

1. **Descargar Node.js**:
   - Ir a https://nodejs.org/
   - Descargar la versi\u0013n LTS (18.x o 20.x, 64-bit)

2. **Instalar**:
   - Ejecutar el instalador
   - Aceptar todos los valores por defecto

3. **Verificar**:
   ```cmd
   node --version
   npm --version
   ```
   Deber\u0001an mostrar versiones de Node.js 18+ y npm 8+

---

### Paso 3: Instalar PostgreSQL

#### Occi\u0013n A: Instalador Oficial de PostgreSQL

1. **Descargar PostgreSQL**:
   - Ir a https://www.postgresql.org/download/windows/
   - Descargar el instalador para Windows x86-64

2. **Instalar**:
   ```cmd
   # Ejecutar el instalador (ejemplo: postgresql-15.5-1-windows-x64.exe)
   # Seguir el asistente de instalaci\u0013n:
   ```

   - **Directorio de instalaci\u0013n**: `C:\Program Files\PostgreSQL\15`
   - **Data Directory**: `C:\Program Files\PostgreSQL\15\data`
   - **Password**: Establecer una contrase\u0011a segura (ej: `Postgres2024!`)
   - **Port**: `5432` (por defecto)
   - **Locale**: `Spanish_Spain.1252` o `C`
   - **Agregar a PATH**: Marcar esta opci\u0013n

3. **Verificar instalaci\u0013n**:
   ```cmd
   pg_isready
   psql --version
   ```

4. **Crear base de datos**:
   ```cmd
   # Conectar a PostgreSQL
   psql -U postgres
   
   # En el prompt de PostgreSQL:
   CREATE DATABASE pdf_resolution_bot;
   \q
   ```

#### Occi\u0013n B: Usar Chocolatey (Recomendado para usuarios avanzados)

1. **Instalar Chocolatey** (si no lo tienes):
   ```cmd
   Set-ExecutionPolicy Bypass -Scope Process -Force
   [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
   iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
   ```

2. **Instalar PostgreSQL**:
   ```cmd
   choco install postgresql -y --params "'/Password:Postgres2024!'"
   ```

3. **Crear base de datos**:
   ```cmd
   choco install psql
   psql -U postgres -c "CREATE DATABASE pdf_resolution_bot;"
   ```

---

### Paso 4: Instalar NSSM

1. **Descargar NSSM**:
   - Ir a https://nssm.cc/download
   - Descargar la \u000altima versi\u0013n (nssm-2.24-101-g8fe8701.zip o superior)

2. **Extraer y agregar a PATH**:
   ```cmd
   # Extraer el ZIP a C:\tools\nssm
   unzip nssm-*.zip -d C:\tools\nssm
   
   # Agregar al PATH
   setx /M PATH "%PATH%;C:\tools\nssm\win64"
   ```

3. **Verificar**:
   ```cmd
   where nssm
   nssm --version
   ```

---

### Paso 5: Instalar Tesseract OCR

#### Occi\u0013n A: Instalador Oficial

1. **Descargar Tesseract**:
   - Ir a https://github.com/UB-Mannheim/tesseract/wiki
   - Descargar el instalador para Windows (tesseract-ocr-w64-setup-5.3.2.20231005.exe o superior)

2. **Instalar**:
   - Ejecutar el instalador
   - Aceptar todos los valores por defecto
   - **Marcar** "Additional language data" e instalar "Spanish"

3. **Verificar**:
   ```cmd
   tesseract --version
   tesseract --list-langs
   ```
   Deber\u0001a mostrar `spa` en la lista de idiomas

#### Occi\u0013n B: Usar Chocolatey

```cmd
choco install tesseract -y
choco install tesseract-lang -y
```

---

### Paso 6: Instalar Dependencias de GPU (Opcional)

Si tu servidor tiene una GPU NVIDIA y quieres usar PaddleOCR con CUDA:

1. **Verificar GPU**:
   ```cmd
   nvidia-smi
   ```

2. **Instalar CUDA Toolkit**:
   - Descargar de https://developer.nvidia.com/cuda-downloads
   - Instalar CUDA 12.x

3. **Instalar cuDNN**:
   - Descargar de https://developer.nvidia.com/cudnn
   - Requiere registro en NVIDIA Developer Program

4. **Verificar**:
   ```cmd
   nvcc --version
   ```

---

## Configuraci\u0013n del Entorno

### Paso 1: Crear estructura de directorios

```cmd
# Crear directorio principal (ejemplo: C:\pdf_bot)
mkdir C:\pdf_bot
cd C:\pdf_bot

# Crear subdirectorios
mkdir uploads
mkdir output
mkdir temp
mkdir logs
```

### Paso 2: Clonar o copiar el proyecto

```cmd
# Si usas Git:
git clone <url-del-repositorio> backend

# O copiar manualmente la carpeta backend a C:\pdf_bot\backend
xcopy /E /I /Y "ruta\al\proyecto\backend" "C:\pdf_bot\backend"
```

### Paso 3: Crear entorno virtual

```cmd
cd C:\pdf_bot\backend

# Crear entorno virtual
python -m venv venv

# Activar entorno
venv\Scripts\activate
```

### Paso 4: Instalar dependencias Python

```cmd
# Instalar todas las dependencias
pip install -r requirements.txt

# Instalar adicionales para desarrollo (opcional)
pip install alembic
```

---

## Configuraci\u0013n de la Base de Datos

### Paso 1: Crear el archivo .env

```cmd
cd C:\pdf_bot\backend
copy .env.example .env
```

Editar `.env` con tus configuraciones:

```ini
# DeepSeek
DEEPSEEK_API_KEY=sk-tu-api-key-aqui
DEEPSEEK_MODEL=deepseek-chat

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://postgres:Postgres2024!@localhost:5432/pdf_resolution_bot
DATABASE_POOL_SIZE=20

# Directorios
UPLOAD_DIR=C:\pdf_bot\uploads
OUTPUT_DIR=C:\pdf_bot\output
TEMP_DIR=C:\pdf_bot\temp
MAX_UPLOAD_SIZE_MB=1024
AUTO_CLEANUP_DAYS=30

# Render
RENDER_DPI=150
RENDER_COLOR_SPACE=gray

# OCR
OCR_ENGINE=auto
OCR_CONFIDENCE_THRESHOLD=0.7
OCR_FALLBACK_ENABLED=true
TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSERACT_LANG=spa
PADDLEOCR_USE_GPU=false
PADDLEOCR_LANG=spa

# AI
AI_BATCH_SIZE=8
AI_MAX_CONCURRENCY=50
AI_RETRY_COUNT=3
AI_TIMEOUT=120.0

# Pipeline
WORKER_PROCESS_COUNT=0

# Web
HOST=0.0.0.0
PORT=8000
WORKERS=4
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000

# Prometheus
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090
```

### Paso 2: Inicializar la base de datos

```cmd
cd C:\pdf_bot\backend
venv\Scripts\activate

# Ejecutar migraciones
python -m alembic upgrade head
```

Si hay errores, verificar:
- Que PostgreSQL est\u0001 en ejecuci\u0013n
- Que las credenciales en DATABASE_URL sean correctas
- Que la base de datos exista

### Paso 3: Probar conexi\u0013n a la base de datos

```python
# En el prompt de Python
import asyncio
from app.db.base import AsyncSessionLocal

async def test_db():
    async with AsyncSessionLocal() as session:
        result = await session.execute("SELECT 1")
        print("Database connection OK:", result.scalar())

asyncio.run(test_db())
```

---

## Build del Frontend

### Paso 1: Navegar a la carpeta frontend

```cmd
cd C:\pdf_bot\frontend
```

### Paso 2: Instalar dependencias

```cmd
npm install
```

### Paso 3: Build para producci\u0013n

```cmd
npm run build
```

Esto generará los archivos est\u0001ticos en `C:\pdf_bot\backend\static`

### Paso 4: Verificar build

```cmd
# Deber\u0001a existir:
dir C:\pdf_bot\backend\static\index.html
```

---

## Instalaci\u0013n como Servicios de Windows

### Paso 1: Instalar servicio del backend

Navegar a `C:\pdf_bot\backend\scripts` y ejecutar:

```cmd
install_backend_service.bat
```

Este script:
1. Verifica que NSSM est\u0001 instalado
2. Verifica que el entorno virtual exista
3. Verifica que uvicorn est\u0001 instalado
4. Instala el servicio usando NSSM
5. Configura el servicio para inicio autom\u0001tico
6. Inicia el servicio

### Paso 2: Verificar servicio

```cmd
# Ver estado del servicio
nssm status pdf_bot_backend

# Ver logs del servicio
type C:\pdf_bot\backend\logs\backend_stdout.log

# Ver servicios instalados
sc query pdf_bot_backend
```

### Paso 3: Configuraciones adicionales (opcional)

#### Cambiar cuenta de servicio

```cmd
# Usar una cuenta espec\u0001fica en lugar de LocalSystem
nssm set pdf_bot_backend ObjectName "DOMAIN\username"
nssm set pdf_bot_backend ObjectPassword "password"
```

#### Cambiar configuraciones del servicio

```cmd
# Inicio r\u0001pido
nssm set pdf_bot_backend Start SERVICE_DEMAND_START

# Inicio autom\u0001tico (recomendado)
nssm set pdf_bot_backend Start SERVICE_AUTO_START

# Tipo de servicio
nssm set pdf_bot_backend Type SERVICE_INTERACTIVE_PROCESS

# Reinicio autom\u0001tico en fallo (5 segundos)
nssm set pdf_bot_backend AppRestartDelay 5000
```

### Paso 4: Administrar el servicio

```cmd
# Iniciar servicio
nssm start pdf_bot_backend

# Detener servicio
nssm stop pdf_bot_backend

# Reiniciar servicio
nssm restart pdf_bot_backend

# Desinstalar servicio
nssm remove pdf_bot_backend confirm
```

---

## Configuraci\u0013n Final

### 1. Abrir puertos en el firewall

```cmd
# Permitir puerto 8000 (backend)
netsh advfirewall firewall add rule name="PDF Bot Backend" dir=in action=allow protocol=TCP localport=8000

# Permitir puerto 9090 (Prometheus, opcional)
netsh advfirewall firewall add rule name="PDF Bot Prometheus" dir=in action=allow protocol=TCP localport=9090
```

### 2. Configurar variables de entorno del sistema (opcional)

Si prefieres no usar el archivo `.env`, puedes configurar variables de entorno del sistema:

```cmd
# DeepSeek API Key
setx DEEPSEEK_API_KEY "sk-tu-api-key-aqui"

# PostgreSQL URL
setx DATABASE_URL "postgresql+asyncpg://postgres:Postgres2024!@localhost:5432/pdf_resolution_bot"
```

### 3. Probar el sistema

1. **Verificar que el servicio est\u0001 en ejecuci\u0013n**:
   ```cmd
   sc query pdf_bot_backend
   ```

2. **Probar el endpoint de salud**:
   ```cmd
   curl http://localhost:8000/health
   ```
   Deber\u0001a devolver:
   ```json
   {
     "status": "healthy",
     "version": "1.0.0",
     "ws_connections": 0,
     "pipeline_running": true
   }
   ```

3. **Probar la API**:
   ```cmd
   curl http://localhost:8000/
   ```

4. **Probar la documentaci\u0013n de la API**:
   - Abrir en navegador: http://localhost:8000/docs

5. **Probar el frontend**:
   - Abrir en navegador: http://localhost:8000
   (El frontend build se sirve autom\u0001ticamente desde /static)

---

## Operaciones B\u0001sicas

### Iniciar/Detener el Servicio

```cmd
# Iniciar
nssm start pdf_bot_backend

# Detener
nssm stop pdf_bot_backend

# Reiniciar
nssm restart pdf_bot_backend
```

### Ver Logs

```cmd
# Logs de stdout (salida est\u0001ndar)
type C:\pdf_bot\backend\logs\backend_stdout.log

# Logs de stderr (errores)
type C:\pdf_bot\backend\logs\backend_stderr.log

# Seguir logs en tiempo real (PowerShell)
Get-Content -Path "C:\pdf_bot\backend\logs\backend_stdout.log" -Wait -Tail 10
```

### Limpiar Archivos Temporales

```cmd
# Eliminar archivos de m\u0001s de AUTO_CLEANUP_DAYS d\u0001as
# Esto se hace autom\u0001ticamente, pero puedes hacerlo manualmente:

# Eliminar uploads antiguos (ejemplo: 30 d\u0001as)
forfiles /P "C:\pdf_bot\uploads" /S /D -30 /C "cmd /c if @isdir==FALSE del @path"

# Eliminar output antiguo
forfiles /P "C:\pdf_bot\output" /S /D -30 /C "cmd /c if @isdir==FALSE del @path"

# Eliminar temp antiguo
forfiles /P "C:\pdf_bot\temp" /S /D -7 /C "cmd /c if @isdir==FALSE del @path"
```

### Backup de la Base de Datos

```cmd
# Usar pg_dump para crear backup
pg_dump -U postgres -d pdf_resolution_bot -F c -b -v -f "C:\pdf_bot\backups\pdf_bot_backup_$(date +%%Y%%m%%d_%%H%%M%%S).dump"

# Restaurar backup
pg_restore -U postgres -d pdf_resolution_bot -c -v "C:\pdf_bot\backups\pdf_bot_backup_20240101.dump"
```

---

## Monitoreo

### Endpoints de Monitoreo

| Endpoint | Descripci\u0013n | Ejemplo |
|----------|-------------|---------|
| `/health` | Salud del sistema | `http://localhost:8000/health` |
| `/metrics` | M\u0009tricas Prometheus | `http://localhost:9090/metrics` |
| `/docs` | Documentaci\u0013n API | `http://localhost:8000/docs` |

### M\u0009tricas Principales de Prometheus

Puedes configurar Grafana para visualizar estas m\u0009tricas:

```promql
# Throughput
rate(pdf_bot_pages_processed_total[1m])

# Latencia promedio de renderizado
rate(pdf_bot_render_latency_seconds_sum[1m]) / rate(pdf_bot_render_latency_seconds_count[1m])

# Tasa de error
sum(rate(pdf_bot_page_errors_total[5m])) by (error_type))

# Tama\u0011o de colas
pdf_bot_stage1_queue_size
pdf_bot_stage2_queue_size
pdf_bot_stage3_queue_size

# Jobs completados
rate(pdf_bot_job_completed_total[1h])
```

### Monitoreo de Windows

Usar el **Administrador de Tareas** para monitorizar:
- Uso de CPU
- Uso de memoria
- Discos y red

O usar **Resource Monitor** (`resmon`) para m\u0001s detalles.

---

## Troubleshooting

### Problema: El servicio no inicio

**Diagn\u0013stico:**

```cmd
# Ver estado del servicio
nssm dump pdf_bot_backend

# Ver logs de NSSM
nssm logs pdf_bot_backend

# Ver logs de la aplicaci\u0013n
type C:\pdf_bot\backend\logs\backend_stderr.log
```

**Soluciones comunes:**

1. **Falta de dependencias**:
   ```cmd
   cd C:\pdf_bot\backend
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Ruta incorrecta en el servicio**:
   ```cmd
   nssm set pdf_bot_backend AppDirectory "C:\pdf_bot\backend"
   nssm set pdf_bot_backend AppParameters "main.py"
   ```

3. **Permisos insuficientes**:
   - Asegurar que la cuenta del servicio tenga permisos en:
     - `C:\pdf_bot` (y subdirectorios)
     - Directorios de Python

4. **Puerto ya en uso**:
   ```cmd
   # Ver que proceso usa el puerto 8000
   netstat -ano | findstr 8000
   
   # Matar el proceso (reemplazar PID con el n\u000amero real)
   taskkill /PID <PID> /F
   ```

### Problema: Error de conexi\u0013n a PostgreSQL

**Diagn\u0013stico:**

```cmd
# Verificar que PostgreSQL est\u0001 en ejecuci\u0013n
pg_isready

# Probar conexi\u0013n manual
psql -U postgres -d pdf_resolution_bot -c "SELECT 1"
```

**Soluciones comunes:**

1. **PostgreSQL no est\u0001 en ejecuci\u0013n**:
   ```cmd
   net start postgresql-x64-15
   ```

2. **Credenciales incorrectas**:
   - Verificar DATABASE_URL en .env
   - Probar con psql usando las mismas credenciales

3. **Puerto bloqueado**:
   - Verificar firewall
   - Verificar que PostgreSQL escuche en 0.0.0.0 (no solo localhost)

### Problema: Error de Tesseract

**Diagn\u0013stico:**

```cmd
# Verificar instalaci\u0013n
tesseract --version

# Verificar idioma
tesseract --list-langs
```

**Soluciones comunes:**

1. **Tesseract no instalado**:
   - Reinstalar Tesseract

2. **Idioma no disponible**:
   ```cmd
   # Descargar idioma español manualmente
   # Desde: https://github.com/tesseract-ocr/tessdata
   # Copiar spa.traineddata a C:\Program Files\Tesseract-OCR\tessdata
   ```

3. **Ruta incorrecta en configuraci\u0013n**:
   ```ini
   TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```

### Problema: Error de pypdfium2

**Error**: `OSError: cannot load shared library`

**Soluciones:**

1. **Instalar Visual C++ Redistributable**:
   - Descargar de: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - Instalar y reiniciar

2. **Reinstalar pypdfium2**:
   ```cmd
   venv\Scripts\activate
   pip uninstall pypdfium2
   pip install pypdfium2
   ```

### Problema: Error de PaddleOCR

**Error**: `ModuleNotFoundError: No module named 'paddlepaddle'`

**Soluciones:**

1. **Instalar PaddlePaddle para CPU**:
   ```cmd
   pip install paddlepaddle
   ```

2. **Instalar PaddlePaddle para GPU** (si tienes CUDA):
   ```cmd
   pip install paddlepaddle-gpu==2.5.0.post118 -f https://www.paddlepaddle.org.cn/whl/linux/mkl/avx/stable.html
   ```

3. **O deshabilitar PaddleOCR**:
   ```ini
   OCR_ENGINE=tesseract
   OCR_FALLBACK_ENABLED=false
   ```

### Problema: Error de memoria (Out of Memory)

**Diagn\u0013stico:**
- El proceso consume mucha memoria
- Windows muestra advertencia de memoria baja

**Soluciones:**

1. **Reducir WORKER_PROCESS_COUNT**:
   ```ini
   WORKER_PROCESS_COUNT=2  # En lugar de 0 (auto)
   ```

2. **Reducir AI_MAX_CONCURRENCY**:
   ```ini
   AI_MAX_CONCURRENCY=20  # En lugar de 50
   ```

3. **Reducir RENDER_DPI**:
   ```ini
   RENDER_DPI=100  # En lugar de 150
   ```

4. **Aumentar memoria del sistema**:
   - A\u0011adir m\u0001s RAM al servidor

### Problema: El frontend no carga

**Diagn\u0013stico:**

1. **Verificar que el build exista**:
   ```cmd
   dir C:\pdf_bot\backend\static\index.html
   ```

2. **Verificar que el servicio est\u0001 sirviendo archivos est\u0001ticos**:
   ```cmd
   curl http://localhost:8000/static/index.html
   ```

**Soluciones:**

1. **Reconstruir el frontend**:
   ```cmd
   cd C:\pdf_bot\frontend
   npm run build
   ```

2. **Verificar configuraci\u0013n de Vite**:
   - En `vite.config.ts`, verificar que `build.outDir` apunte a `../backend/static`

---

## Actualizaciones

### Actualizar el Backend

1. **Detener el servicio**:
   ```cmd
   nssm stop pdf_bot_backend
   ```

2. **Actualizar el c\u0013digo**:
   ```cmd
   cd C:\pdf_bot\backend
   git pull origin main
   ```

3. **Actualizar dependencias**:
   ```cmd
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Ejecutar migraciones** (si hay cambios en el esquema):
   ```cmd
   python -m alembic upgrade head
   ```

5. **Iniciar el servicio**:
   ```cmd
   nssm start pdf_bot_backend
   ```

### Actualizar el Frontend

1. **Actualizar el c\u0013digo**:
   ```cmd
   cd C:\pdf_bot\frontend
   git pull origin main
   ```

2. **Actualizar dependencias**:
   ```cmd
   npm install
   ```

3. **Reconstruir**:
   ```cmd
   npm run build
   ```

4. **Reiniciar el backend** (para servir los nuevos archivos):
   ```cmd
   nssm restart pdf_bot_backend
   ```

---

## Checklist de Instalaci\u0013n

- [ ] Python 3.11+ instalado y en PATH
- [ ] Node.js LTS instalado y en PATH
- [ ] PostgreSQL instalado y en ejecuci\u0013n
- [ ] Base de datos `pdf_resolution_bot` creada
- [ ] NSSM instalado y en PATH
- [ ] Tesseract OCR instalado con idioma espa\u0011ol
- [ ] DeepSeek API Key obtenida
- [ ] Estructura de directorios creada (`C:\pdf_bot`)
- [ ] Backend copiado a `C:\pdf_bot\backend`
- [ ] Entorno virtual creado (`venv`)
- [ ] Dependencias Python instaladas (`requirements.txt`)
- [ ] Archivo `.env` configurado
- [ ] Migraciones de DB ejecutadas
- [ ] Frontend copiado a `C:\pdf_bot\frontend`
- [ ] Dependencias Node.js instaladas (`npm install`)
- [ ] Frontend build ejecutado (`npm run build`)
- [ ] Servicio de Windows instalado (`install_backend_service.bat`)
- [ ] Servicio en ejecuci\u0013n y funcional
- [ ] Puertos abiertos en firewall (8000, 9090)
- [ ] Prueba de salud exitosa (`/health`)
- [ ] Prueba de API exitosa (`/docs`)
- [ ] Prueba de frontend exitosa (navegador)

---

## Configuraci\u0013n para Producci\u0013n

### Seguridad Adicional

1. **Cambiar SECRET_KEY**:
   ```bash
   # Generar una clave segura
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Y configurarla en `.env`:
   ```ini
   SECRET_KEY=tua-clave-segura-aqui
   ```

2. **Configurar HTTPS**:
   - Usar un reverse proxy (Nginx, Apache) con HTTPS
   - O configurar Uvicorn con SSL directamente

3. **Restringir CORS**:
   ```ini
   CORS_ORIGINS=http://tu-dominio.com,https://tu-dominio.com
   ```

4. **Autenticaci\u0013n** (opcional):
   - Implementar autenticaci\u0013n JWT en la API
   - Configurar autenticaci\u0013n b\u0001sica en Nginx

### Escalabilidad

1. **Aumentar WORKERS**:
   ```ini
   WORKERS=8  # Igual al n\u000amero de n\u000acleos
   ```

2. **Aumentar WORKER_PROCESS_COUNT**:
   ```ini
   WORKER_PROCESS_COUNT=8  # Para Stage 1
   ```

3. **Aumentar AI_MAX_CONCURRENCY**:
   ```ini
   AI_MAX_CONCURRENCY=100  # Depende de tu rate limit de DeepSeek
   ```

### Monitoreo Avanzado

1. **Configurar Grafana**:
   - Conectar a Prometheus (`http://localhost:9090`)
   - Importar dashboard de ejemplo

2. **Alertas**:
   - Configurar alertas para:
     - Uso de CPU > 90% por 5 minutos
     - Tama\u0011o de cola > 1000
     - Tasa de error > 10%

3. **Logs centralizados**:
   - Configurar ELK Stack (Elasticsearch, Logstash, Kibana)
   - O usar Loki + Grafana

---

## Desinstalaci\u0013n

1. **Desinstalar el servicio**:
   ```cmd
   cd C:\pdf_bot\backend\scripts
   uninstall_backend_service.bat
   ```

2. **Eliminar directorios**:
   ```cmd
   rmdir /S /Q C:\pdf_bot
   ```

3. **Eliminar base de datos** (opcional):
   ```cmd
   psql -U postgres -c "DROP DATABASE pdf_resolution_bot;"
   ```

4. **Desinstalar PostgreSQL** (opcional):
   - Usar el desinstalador de PostgreSQL
   - O con Chocolatey: `choco uninstall postgresql`

5. **Desinstalar NSSM** (opcional):
   - Eliminar el directorio donde se extrajo NSSM
   - Remover NSSM del PATH

---

## Conclusiones

Este documento proporciona una gu\u0001a completa para instalar, configurar y mantener el Bot de Segmentaci\u0013n de PDFs por Resoluci\u0013n en un servidor Windows f\u0001sico, **sin depender de virtualizaci\u0013n alguna**.

El sistema est\u0001 dise\u0011ado para:
- Ejecutarse 24/7 como servicios de Windows
- Procesar decenas de miles de p\u0001ginas diarias
- Ser robusto ante fallos
- Proporcionar visibilidad completa del procesamiento
- Ser f\u0001cil de mantener y actualizar

Para m\u0001s detalles sobre la arquitectura interna, consultar `ARQUITECTURA.md`.
