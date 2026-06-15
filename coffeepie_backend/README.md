# Server Proxmox DB

A FastAPI-based application for managing Proxmox VMs with MongoDB integration, featuring user authentication, company management, VM operations, and terminal access.

## Prerequisites

- Python 3.8+ (for venv installation)
- Docker & Docker Compose (for containerized setup)
- MongoDB (included in docker-compose.yml)
- Proxmox Server with API access

## Project Structure

```
app/
├── api/                 # API routes (auth, VMs, snapshots, etc.)
├── core/               # Security configurations
├── crud/               # Database operations
├── models/             # Data models
├── services/           # Business logic services
└── utilities/          # Helper functions
```

## Installation & Setup

### Option 1: Using Virtual Environment (venv)

#### 1. Create and Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv venv
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned)
.\venv\Scripts\Activate.ps1
```

**On macOS/Linux:**
```bash
python -m venv venv
source venv/bin/activate
```

#### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

#### 3. Configure Environment Variables

Create a `.env` file in the project root (see [Example .env File](#example-env-file) below):

```bash
cp .env.example .env
# Edit .env with your configuration
```

#### 4. Setup MongoDB (Local)

Ensure MongoDB is running locally or update `MONGO_URI` in `.env` to point to your MongoDB instance.

#### 5. Run the Application

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

The API will be available at `http://localhost:8000`

API Documentation:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

---

### Option 2: Using Docker Compose

#### 1. Configure Environment Variables

Create a `.env` file in the project root with your configuration:

```bash
cp .env.example .env
# Edit .env with your configuration
```

#### 2. Build and Run Containers

```bash
docker-compose up -d
```

This will start:
- FastAPI application on `http://localhost:8080`
- MongoDB on `mongodb://localhost:27017`

#### 3. View Logs

```bash
docker-compose logs -f app
```

#### 4. Stop Containers

```bash
docker-compose down
```

#### 5. Rebuild Containers (after code changes)

```bash
docker-compose up -d --build
```

---

## Example .env File

Create a `.env` file in the project root with the following configuration:

```env
# Proxmox Configuration
PROXMOX_URL=https://206.62.137.22:8006/api2/json
PROXMOX_USER=root@pam
PROXMOX_PASSWORD=your-proxmox-password
PROXMOX_ip=206.62.137.22:8006

# MongoDB Configuration
MONGO_INITDB_ROOT_USERNAME=root
MONGO_INITDB_ROOT_PASSWORD=password
MONGO_URI=mongodb://root:password@mongo:27017
MONGO_DB_NAME=serverproxmoxdb

# JWT Configuration
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=30

# Documentation API Key
DOCS_API_KEY=prx_doc_key_9bL4kM2wP7nR5vX3yC8qT1jF6sD0aE2lH
```

### Environment Variables Explanation

| Variable | Description | Example |
|----------|-------------|---------|
| `PROXMOX_URL` | Proxmox API endpoint | `https://your-proxmox-ip:8006/api2/json` |
| `PROXMOX_USER` | Proxmox username | `root@pam` |
| `PROXMOX_PASSWORD` | Proxmox password | `your-password` |
| `PROXMOX_ip` | Proxmox server IP and port | `206.62.137.22:8006` |
| `MONGO_INITDB_ROOT_USERNAME` | MongoDB root username | `root` |
| `MONGO_INITDB_ROOT_PASSWORD` | MongoDB root password | `password` |
| `MONGO_URI` | MongoDB connection string | `mongodb://root:password@mongo:27017` |
| `MONGO_DB_NAME` | MongoDB database name | `serverproxmoxdb` |
| `JWT_SECRET_KEY` | Secret key for JWT tokens | Generate a secure random string |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `JWT_EXPIRE_MINUTES` | JWT token expiration time | `30` |
| `DOCS_API_KEY` | Documentation API key | `prx_doc_key_...` |

---

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login user
- `POST /api/auth/register` - Register new user
- `POST /api/auth/refresh` - Refresh JWT token

### Users
- `GET /api/users/me` - Get current user
- `GET /api/users` - Get all users (admin)
- `POST /api/users` - Create user (admin)

### Companies
- `GET /api/companies` - Get all companies
- `GET /api/companies/{id}` - Get company details
- `POST /api/companies` - Create company

### Virtual Machines (VMs)
- `GET /api/vms` - List all VMs
- `GET /api/vms/{id}` - Get VM details
- `POST /api/vms` - Create VM
- `POST /api/vms/{id}/start` - Start VM
- `POST /api/vms/{id}/stop` - Stop VM
- `POST /api/vms/{id}/reboot` - Reboot VM
- `POST /api/vms/{id}/clone` - Clone VM
- `DELETE /api/vms/{id}` - Delete VM

### Snapshots
- `GET /api/snapshots` - List snapshots
- `POST /api/snapshots` - Create snapshot
- `DELETE /api/snapshots/{id}` - Delete snapshot

### Terminals
- `GET /api/terminals` - Get terminal access

---

## Development

### Install Development Dependencies

```bash
pip install -r requirements.txt
```

### Run Tests

```bash
pytest
```

### Code Style

The project follows PEP 8 guidelines.

---

## Troubleshooting

### MongoDB Connection Error
- Ensure MongoDB is running
- Verify `MONGO_URI` in `.env` is correct
- Check MongoDB credentials

### Proxmox Connection Error
- Verify `PROXMOX_URL` and credentials
- Ensure Proxmox server is accessible from your machine
- Check SSL certificate if using HTTPS

### Port Already in Use
- Change port in startup command: `--port 8001`
- Or kill process using port 8080

### Docker Issues
- Rebuild containers: `docker-compose up -d --build`
- Check logs: `docker-compose logs app`
- Remove volumes and restart: `docker-compose down -v && docker-compose up -d`

---

## License

Proprietary - All rights reserved

## Support

For issues or questions, contact your system administrator.
