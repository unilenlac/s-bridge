# σ-Bridge

σ-Bridge is a FastAPI-based service designed to fetch manuscript transcriptions via a DTS (Distributed Text Services) endpoint, tokenize/lemmatize/parse them using NLP pipelines, perform collations via CollateX, and import/update traditions on the Stemmarest server.

---

##  Quick Start with Docker (Recommended)

To run the production deployment using Docker Compose (if you do not have Docker installed, follow the official [Docker Installation Guide](https://docs.docker.com/get-docker/)):

### 1. Clone & Navigate
```bash
git clone https://github.com/unilenlac/s-bridge.git
cd s-bridge
```

### 2. Configure Environment
Copy the example environment file and customize it to match your target services:
```bash
cp .env.example .env
```
Ensure that `COLLATEX_API_BASE_URL` and `STEMMAREST_API_BASE_URL` point to your running CollateX and Stemmarest instances.

> [!NOTE]
> **Network Binding & Ports**: By default, the service binds to the local loopback interface (`127.0.0.1:8500`) in [docker-compose.yml]. For production server deployment, adapt the `ports` configuration in [docker-compose.yml] to bind to your specific host IP (e.g., `"192.168.1.50:8500:8500"`) or expose it publicly (e.g., `"0.0.0.0:8500:8500"`).

### 3. Start the Application
Build and run the stack:
```bash
docker compose up --build -d
```
*(Or if you have `make` installed—which can be installed via `sudo apt install make` on Debian/Ubuntu—run `make build && make up`)*

The service will automatically run database migrations on start and listen on port `8500`.
- **API Documentation (Swagger UI)**: [http://yourhost:8500/docs]
- **API ReDoc**: [http://yourhost:8500/redoc]

---

## Or run the Local Development Setup (Not recommended)

If you wish to run the project locally without Docker:

### Prerequisites
- Python 3.14+
- [uv](https://github.com/astral-sh/uv) (recommended Python package manager)

### 1. Install Dependencies
```bash
uv sync
```
*(Or use `make install`)*

### 2. Configure Environment
Copy and adjust the environment template (make sure directories like `LOG_FILE` are writable locally):
```bash
cp .env.example .env
```

### 3. Run Database Migrations
Apply Alembic migrations to set up the SQLite database:
```bash
uv run alembic upgrade head
```
*(Or use `make db-migrate`)*

### 4. Start the Development Server
```bash
uv run uvicorn main:app --reload --host 127.0.0.1 --port 8500
```
*(Or use `make dev`)*

### 5. Running Tests
To execute the test suite:
```bash
uv run pytest
```
*(Or use `make test`)*

---

## Configuration

Settings are managed via environment variables (defined in [core/config.py] and loaded from `.env`). Edit either or.

Key parameters:

| Variable | Description | Default |
|---|---|---|
| `PIPELINE` | Processing pipeline (`classical` or `modern`) | `classical` |
| `LANGUAGE` | Language ISO 639-3 code (e.g. `anci1242` for Ancient Greek) | `anci1242` |
| `COLLATEX_API_BASE_URL` | Base URL of the CollateX API service |  |
| `STEMMAREST_API_BASE_URL`| Base URL of the Stemmarest API service |  |
| `ENVIRONMENT` | Target environment tier (`DEV` or `PROD`) | `DEV` (local default) |
| `TIMEZONE` | System timezone (e.g. `Europe/Zurich`) | `Europe/Zurich` |
| `TAG_CONFIG` | Absolute path to custom JSON tag dictionary file | `None` (defaults to [/utils/enlac_tags.json]) |

### Linguistic & XML Configuration
- **Custom XML Tags**: The TEI XML parser maps custom tags based on [utils/enlac_tags.json]. You can customize this mapping by creating your own JSON file and passing its absolute path via the `TAG_CONFIG` environment variable.
- **Classical Greek Abbreviations**: The parser expands Classical Greek abbreviations during token normalization using the static dictionary defined in [abbr_classical_greek.csv](file:///home/jbidaux/s-bridge/utils/abbr_classical_greek.csv).

---

## Key Files & Directories

- [Dockerfile](file:///home/jbidaux/s-bridge/Dockerfile): Multi-stage production Docker build configuration.
- [docker-compose.yml](file:///home/jbidaux/s-bridge/docker-compose.yml): Docker Compose service definitions.
- [.env.example](file:///home/jbidaux/s-bridge/.env.example): Template for environment configurations.
- [Makefile](file:///home/jbidaux/s-bridge/Makefile): Target shortcuts for building, running, formatting, and database management.
