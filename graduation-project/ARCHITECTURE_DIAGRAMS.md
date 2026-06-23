# Oil Spill Detection: Architecture Diagrams and Flowcharts

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend (React/Vite)                       │
│          http://localhost:5173 (Development Server)                 │
└────────────────────────────────┬──────────────────────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    │            │            │
                    ▼            ▼            ▼
          POST /api/pipeline   GET /verify  GET /api/results/:runId
          (Upload Image)      (Check Auth)  (Fetch Results)
                    │            │            │
                    └────────────┼────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Express.js Server    │
                    │  (Node.js Runtime)     │
                    │  Port 5000             │
                    └────────┬───────────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
        ┌──────────────┐  ┌─────────────────────┐  ┌────────────┐
        │   Auth       │  │  Pipeline Service   │  │  Results   │
        │ Controller   │  │  (Child Process)    │  │  Routes    │
        │              │  │                     │  │            │
        └──────────────┘  │  spawn('python      │  └────────────┘
                          │         main.py')   │
                          └─────────┬───────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  Python Pipeline      │
                        │  (Isolated Process)   │
                        │                       │
                        │ ├─ Step 0: CV         │
                        │ ├─ Step 1: Extract    │
                        │ ├─ Step 2: ERA5       │
                        │ ├─ Step 3: MEDSLIK    │
                        │ ├─ Step 4: Physics    │
                        │ ├─ Step 5: RF         │
                        │ ├─ Step 6: Ensemble   │
                        │ └─ Step 7: NLP        │
                        └───────────┬───────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  Filesystem           │
                        │  /uploads/            │
                        │  /runs/[timestamp]/   │
                        └───────────┬───────────┘
                                    │
                        ┌───────────▼───────────┐
                        │ PostgreSQL 15-alpine  │
                        │ Docker Container      │
                        │ Port 5432             │
                        │                       │
                        │ ├─ users table        │
                        │ ├─ auth tokens        │
                        │ └─ session data       │
                        └───────────────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │  Docker Volume        │
                        │  postgres_data:/      │
                        │  var/lib/postgresql   │
                        │  data/                │
                        └───────────────────────┘
```

## 2. Docker Compose Networking

```
Host OS
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   Docker Daemon                                                  │
│   ┌────────────────────────────────────────────────────────┐   │
│   │                                                        │   │
│   │  oil_spill_network (Overlay Network)                  │   │
│   │  ┌──────────────────────────────────────────────┐    │   │
│   │  │                                              │    │   │
│   │  │  ┌──────────────┐    ┌──────────────┐        │   │   │
│   │  │  │ Backend      │    │ PostgreSQL   │        │   │   │
│   │  │  │ Container    │◄──►│ Container    │        │   │   │
│   │  │  │              │    │              │        │   │   │
│   │  │  │ localhost    │    │ postgres:    │        │   │   │
│   │  │  │ :5000        │    │ 5432         │        │   │   │
│   │  │  │              │    │              │        │   │   │
│   │  │  │ DC_HOST:     │    │ Vol: pg_data │        │   │   │
│   │  │  │ postgres     │    │              │        │   │   │
│   │  │  └──────────────┘    └──────────────┘        │   │   │
│   │  │         ▲                    ▲                │   │   │
│   │  │         │ DNS Resolution    │ Health Check  │   │   │
│   │  │         │                   │               │   │   │
│   │  └────────────────────────────────────────────┘   │   │
│   │              ▲                                    │   │
│   │              │ Port Mapping                       │   │
│   │              │                                    │   │
│   └──────────┬───┴────────────────────────────────────┘   │
│              │                                             │
│         ┌────▼─────┐                                       │
│         │ Localhost│                                       │
│         │ :5432    │◄─── Host OS (port 5432)             │
│         └──────────┘                                       │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

## 3. Authentication Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        REGISTRATION FLOW                         │
└─────────────────────────────────────────────────────────────────┘

  Frontend                Backend              PostgreSQL
     │                       │                     │
     │  1. POST /auth/       │                     │
     │    register            │                     │
     │  {email, password}    │                     │
     ├──────────────────────►│                     │
     │                       │ 2. Hash Password    │
     │                       │    bcrypt.hash()    │
     │                       │                     │
     │                       │ 3. Check existence  │
     │                       │    SELECT * FROM    │
     │                       │    users WHERE      │
     │                       │    email = $1      │
     │                       ├────────────────────►│
     │                       │◄────────────────────┤
     │                       │                     │
     │                       │ 4. INSERT user      │
     │                       │    INSERT INTO      │
     │                       │    users (id,       │
     │                       │    email, pass_h)   │
     │                       ├────────────────────►│
     │                       │◄────────────────────┤
     │                       │                     │
     │                       │ 5. Generate JWT     │
     │                       │    jwt.sign(        │
     │                       │    {userId,email},  │
     │                       │    JWT_SECRET)      │
     │                       │                     │
     │  6. 201 Created       │                     │
     │  {token, user}        │                     │
     │◄──────────────────────┤                     │
     │                       │                     │
     └───────────────────────┴─────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                          LOGIN FLOW                              │
└─────────────────────────────────────────────────────────────────┘

  Frontend                Backend              PostgreSQL
     │                       │                     │
     │  1. POST /auth/login  │                     │
     │  {email, password}    │                     │
     ├──────────────────────►│                     │
     │                       │ 2. SELECT * FROM    │
     │                       │    users WHERE      │
     │                       │    email = $1      │
     │                       ├────────────────────►│
     │                       │ Result: {id,email,  │
     │                       │ password_hash}     │
     │                       │◄────────────────────┤
     │                       │                     │
     │                       │ 3. bcrypt.compare() │
     │                       │    input_pwd vs     │
     │                       │    hash_from_db     │
     │                       │    ▼                │
     │                       │    MATCH? YES       │
     │                       │                     │
     │                       │ 4. jwt.sign()       │
     │                       │    Create token:    │
     │                       │    Header.Payload.  │
     │                       │    Signature        │
     │                       │                     │
     │  5. 200 OK            │                     │
     │  {token, user}        │                     │
     │◄──────────────────────┤                     │
     │                       │                     │
     └───────────────────────┴─────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              AUTHORIZATION (Protected Route) FLOW                │
└─────────────────────────────────────────────────────────────────┘

  Frontend                Backend              PostgreSQL
     │                       │                     │
     │  GET /api/results     │                     │
     │  Authorization:       │                     │
     │  Bearer eyJhb...      │                     │
     ├──────────────────────►│                     │
     │                       │ authMiddleware:     │
     │                       │ 1. Extract token    │
     │                       │    from header      │
     │                       │ 2. jwt.verify()     │
     │                       │    Verify with      │
     │                       │    JWT_SECRET       │
     │                       │    ▼                │
     │                       │    Signature valid? │
     │                       │    Token expired?   │
     │                       │                     │
     │                       │ 3. Decode payload   │
     │                       │    {userId, email}  │
     │                       │ 4. req.user =       │
     │                       │    decoded          │
     │                       │                     │
     │                       │ resultsController:  │
     │                       │ Access req.user     │
     │                       │ Fetch results from  │
     │                       │ filesystem          │
     │                       │                     │
     │  200 OK               │                     │
     │  {results, pipeline}  │                     │
     │◄──────────────────────┤                     │
     │                       │                     │
     └───────────────────────┴─────────────────────┘
```

## 4. JWT Token Structure

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.
eyJ1c2VySWQiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJlbWFpbCI6Im5vb3JiYXJha2F0NzU5QGdtYWlsLmNvbSIsImlhdCI6MTcxMTcwMDAwMCwiZXhwIjoxNzEyMzA0ODAwfQ.
TJVA95OrM7E2cBab30RMHrHDcEfxjoYZgeFONFh7HgQ

│                               │                                  │                         │
└────── HEADER ────────────────►└─────────── PAYLOAD ──────────────►└──── SIGNATURE ────────┘

┌──────────────────────────────┐
│   HEADER (Base64URL)         │
├──────────────────────────────┤
│ {                            │
│   "alg": "HS256",            │
│   "typ": "JWT"               │
│ }                            │
└──────────────────────────────┘

┌──────────────────────────────┐
│   PAYLOAD (Base64URL)        │
├──────────────────────────────┤
│ {                            │
│   "userId": "550e8400-...",  │
│   "email": "noor@gmail.",    │
│   "iat": 1711700000,         │
│   "exp": 1712304800,         │
│   "sub": "550e8400...",      │
│ }                            │
└──────────────────────────────┘

┌──────────────────────────────┐
│  SIGNATURE (HS256)           │
├──────────────────────────────┤
│ HMAC-SHA256(                 │
│   base64(header)."."         │
│   base64(payload),           │
│   JWT_SECRET                 │
│ )                            │
│                              │
│ (Only server knows secret)   │
└──────────────────────────────┘

Verification Process:
┌─────────┐
│ Receive │  Extract     Verify      If MATCH:
│  Token  │  Components  Signature   ✓ Token valid
└────┬────┘       │          │       │ Proceed
     │            ▼          ▼       │
     │        ┌──────┐  ┌──────┐    │
     │        │Decode│  │Compute    │
     │        │Header│  │New Sig    │
     │        └──────┘  │using      │
     │            │     │JWT_SECRET │
     │            │     └──────┘    │
     │            │        │        │
     │            └────┬───┘        │
     │                 │            │
     │          ┌──────▼──────┐     │
     │          │Compare      │     │
     │          │Signatures   │─────┘
     │          └─────────────┘     If NO MATCH:
     │                        ✗ Reject token
```

## 5. Pipeline Execution Architecture

```
Frontend Upload                Backend Process              Python Pipeline
      │                              │                            │
      │  POST /api/pipeline/run      │                            │
      │  Content-Type: multipart      │                            │
      │  [binary image]              │                            │
      ├─────────────────────────────►│                            │
      │                              │                            │
      │                          1. multer.diskStorage()          │
      │                          │ Save to /uploads/               │
      │                          │ File: 2401_satelite.tif        │
      │                          │                                │
      │                          2. runPipeline(imagePath)        │
      │                          │                                │
      │                          3. Process Spawning              │
      │                          │ spawn(command, {shell: true})  │
      │                          │ cwd: oilspill_analysis/        │
      │                          │                                │
      │                          4. Environment Setup            │
      │                          │ PIPELINE_PYTHON: python3       │
      │                          │ scriptPath: src/main/...       │
      │                          │ csvPath: data/raw/...          │
      │                          │                                │
      │                          ├───────────────────────────────►│
      │                          │                                │ Python Process
      │                          │                                │ (Child Process)
      │                          │                                │
      │                          │◄─────────stdout: "Step 0..."───┤
      │                          │                                │ Reads input image
      │                          │                                │ Loads CV model
      │                          │◄─────────stdout: "Mask gen"────┤ Generates mask
      │                          │                                │
      │                          │◄─────────stdout: "runs/2401T22"┤ Creates run dir
      │                          │  (extractRunId = "2401T22")    │
      │                          │                                │
      │                          │◄─────────stdout: "Step 7 NLP"──┤ Runs all steps
      │                          │                                │
      │                          │◄──────────exit code: 0─────────┤ Process ends
      │                          │                                │ Writes results JSON
      │                          │                                │
      │  5. Response (runId)     │                                │
      │  {message, runId: "..."}│                                │
      │◄──────────────────────────┤                               │
      │                           │                               │
```

## 6. Data Flow: From Upload to Dashboard

```
┌─────────┐
│  User   │
│ Selects │
│  Image  │
└────┬────┘
     │
     ▼
┌──────────────────┐
│ Frontend         │
│ POST to backend  │
│ /api/pipeline/run│
└────┬─────────────┘
     │
     ▼
┌──────────────────┐      ┌─────────────┐
│  Express Server  │      │   Multer    │
│  Port 5000       │      │ Middleware  │
└────┬─────────────┘      └─────┬───────┘
     │                          │
     ▼                          ▼
┌──────────────────┐      ┌──────────────┐
│ Save Image to    │      │ /uploads/    │
│ Filesystem       │      │ 2401_sat.tif │
└────┬─────────────┘      └──────┬───────┘
     │                           │
     ▼                           ▼
┌──────────────────────────────────────┐
│ pipelineService.runPipeline()        │
│ ├─ Validate image exists            │
│ ├─ Construct Python command          │
│ └─ spawn() child process             │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│   Python Pipeline (Independent)      │
│                                      │
│ ├─ Step 0: CV Inference              │
│ ├─ Step 1: Extract Coordinates       │
│ ├─ Step 2: Download ERA5 Data        │
│ ├─ Step 3: Run MEDSLIK Simulation    │
│ ├─ Step 4: Physics-Guided Classification
│ ├─ Step 5: Random Forest             │
│ ├─ Step 6: Ensemble Decision         │
│ └─ Step 7: NLP Validation            │
│                                      │
│ └─ Output: pipeline_results.json     │
└─────────────────┬────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────┐
│ File System Storage                  │
│ /backend/oilspill_analysis/runs/     │
│ 20260314T2222Z/                      │
│ ├─ pipeline_results.json             │
│ ├─ detection_mask.npy                │
│ ├─ trajectory.csv                    │
│ └─ metadata.json                     │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│ Frontend Polls Results               │
│ GET /api/results/20260314T2222Z     │
│                                      │
│ authMiddleware                       │
│ ├─ Extract JWT from header           │
│ ├─ Verify signature                  │
│ └─ Attach user to request            │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│ resultsController                    │
│ ├─ Locate run directory              │
│ ├─ Load pipeline_results.json        │
│ ├─ Extract ML predictions            │
│ ├─ Parse physics validation          │
│ ├─ Format trajectory data            │
│ └─ Return JSON response              │
└────────────────┬─────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────┐
│ Frontend Displays Results            │
│ ├─ Classification: OIL_SPILL         │
│ ├─ Confidence: 91%                   │
│ ├─ Risk Level: CRITICAL              │
│ ├─ Plot Trajectory on Map            │
│ └─ Download CSV Button               │
└──────────────────────────────────────┘
```

## 7. Error Handling Pathways

```
Request: POST /api/pipeline/run [image]
         │
         ▼
    Processing
         │
    ┌────┴────────────────────┐
    │                         │
    ▼                         ▼
Image Found            Image Not Found
    │                         │
    ▼                         ▼
Spawn Python           Return 400
Process                └─ "No image uploaded"
    │
    ▼
Python Execution
    │
    ├─── Exit Code 0 ──┐
    │                  │
    │         ┌────────┴─────────┐
    │         │                  │
    │    runId?              runId not found?
    │         │                  │
    │    ✓    │                  ✗
    │         ▼                  ▼
    │    Return 200          Return 500
    │    {runId}             "No runId found"
    │
    ├─── Exit Code ≠ 0 ─────────────┐
    │                               │
    ▼                               ▼
Parse stderr                    Return 500
    │                           {error, details}
    ├─ ModuleNotFoundError?      │
    │  └─ Return 500 with        ├─ ImportError?
    │     solution hint          │  └─ "Missing dependencies"
    │                            │
    └─ General execution error   └─ Provide Python stderr
       └─ Return 500 with
          technical details
```

## 8. Docker Volume Data Persistence

```
Before Crash                    After Container Restart
┌──────────────────┐            ┌──────────────────┐
│ Container:       │            │ Container:       │
│ postgres         │            │ postgres (NEW)   │
│                  │            │                  │
│ /var/lib/        │            │ /var/lib/        │
│ postgresql/data  │            │ postgresql/data  │
└────────┬─────────┘            └────────┬─────────┘
         │ (writes)                      │ (reads)
         │                               │
         └───────────┬───────────────────┘
                     │
                ┌────▼────┐
                │  Volume │
                │postgres_│
                │  data   │
                │         │
                │ [data   │
                │  files] │ ◄─── PERSISTED
                │         │
                │[indexes]│
                └─────────┘

Scenario: Container crash/OOM kill
         │
         ▼
   Container Dies
         │
         ▼
   Volume Untouched
   └─ Data on disk
   └─ Indexes intact
         │
         ▼
   New Container Started
         │
         ▼
   Mount same volume
   /var/lib/postgresql/data
         │
         ▼
   PostgreSQL Recovery
   └─ Replay WAL logs
   └─ Restore data
         │
         ▼
   Database Online
   └─ Same users table
   └─ Same auth tokens
```

## 9. Security Boundaries

```
┌─────────────────────────────────────────────────────────┐
│                      Host OS                            │
│                     (Untrusted)                         │
│                                                         │
│  ┌───────────────────────────────────────────────────┐ │
│  │        Docker Security Boundary                  │ │
│  │        (Process Isolation)                       │ │
│  │                                                  │ │
│  │  ┌─────────────────────────────────────────────┐ │ │
│  │  │    Backend Container (Trusted Context)     │ │ │
│  │  │    - Limited privileges                    │ │ │
│  │  │    - Read: /app/src, /uploads             │ │ │
│  │  │    - Write: /app/src (dev mode)           │ │ │
│  │  │    - Network: Can connect to postgres     │ │ │
│  │  │    - Env: JWT_SECRET (memory only)        │ │ │
│  │  │                                           │ │ │
│  │  │    ┌────────────────────────────────────┐ │ │ │
│  │  │    │ Python Subprocess                 │ │ │ │
│  │  │    │ (Spawned by Backend)              │ │ │ │
│  │  │    │ - Inherits environment            │ │ │ │
│  │  │    │ - Isolated stderr/stdin/stdout   │ │ │ │
│  │  │    │ - Limited to Python runtime      │ │ │ │
│  │  │    └────────────────────────────────────┘ │ │ │
│  │  └─────────────────────────────────────────────┘ │ │
│  │                                                  │ │
│  │  ┌─────────────────────────────────────────────┐ │ │
│  │  │   PostgreSQL Container                    │ │ │
│  │  │   - Limited privileges                    │ │ │
│  │  │   - Read/Write: /var/lib/postgresql      │ │ │
│  │  │   - Network: Listen on 5432              │ │ │
│  │  │   - Cannot execute host commands         │ │ │
│  │  │   - No access to host filesystem         │ │ │
│  │  └─────────────────────────────────────────────┘ │ │
│  │                                                  │ │
│  │  ┌─────────────────────────────────────────────┐ │ │
│  │  │  Docker Overlay Network (oil_spill_network)│ │ │
│  │  │  - Internal DNS: postgres resolves to IP  │ │ │
│  │  │  - Containers communicate via this bridge │ │ │
│  │  │  - Traffic isolated from host network     │ │ │
│  │  └─────────────────────────────────────────────┘ │ │
│  │                                                  │ │
│  │  ┌─────────────────────────────────────────────┐ │ │
│  │  │  Volume Mount (postgres_data)             │ │ │
│  │  │  Host: /var/lib/docker/volumes/...       │ │ │
│  │  │  Container: /var/lib/postgresql/data     │ │ │
│  │  │  - Mounted read/write for postgres       │ │ │
│  │  │  - No direct host access                 │ │ │
│  │  └─────────────────────────────────────────────┘ │ │
│  │                                                  │ │
│  │  Port Mapping                                   │ │
│  │  Host:5432 ◄──► Container:5432                 │ │
│  │  (Controlled by Docker)                        │ │
│  │                                                  │ │
│  └───────────────────────────────────────────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘

Security Implications:
✓ Host OS cannot be compromised via container escape (kernel isolation)
✓ Container cannot access host credentials or SSH keys
✓ Database password isolated in environment variables
✓ Python subprocess inherits Node context, cannot escalate privileges
✓ Filesystem paths enforce access control
✓ Networks isolated unless explicitly exposed
```

---

**Diagram Version**: 1.0  
**Use Case**: Thesis Documentation & Technical Communication  
**Format**: ASCII Diagrams (compatible with Markdown, GitHub, GitLab)
