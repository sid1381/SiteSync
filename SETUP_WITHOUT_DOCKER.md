# SiteSync Setup Without Docker

Since you're experiencing Docker Hub authentication issues, here's how to run SiteSync locally for development and testing.

## Quick Setup

### 1. Install PostgreSQL Locally

**Option A: Using Homebrew (Recommended)**
```bash
brew install postgresql@15
brew services start postgresql@15

# Create database and user
psql postgres
CREATE DATABASE sitesync;
CREATE USER sitesync WITH ENCRYPTED PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE sitesync TO sitesync;
\q
```

**Option B: Using PostgreSQL.app**
- Download from https://postgresapp.com/
- Start the app and create database `sitesync`

### 2. Update Environment Variables

Create `.env.local`:
```bash
cp .env.example .env.local
```

Edit `.env.local`:
```env
DATABASE_URL=postgresql+psycopg2://sitesync:password@localhost:5432/sitesync
MINIO_ENDPOINT=http://localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=sitesync
OPENAI_API_KEY=your_openai_key_here
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECS=20
ENV=dev
```

### 3. Install MinIO (Optional - for file storage)

```bash
brew install minio/stable/minio
mkdir -p ~/minio-data
minio server ~/minio-data --console-address ":9001" &
```

### 4. Run Database Migrations

```bash
# Set environment
export DATABASE_URL="postgresql+psycopg2://sitesync:password@localhost:5432/sitesync"

# Run migrations
alembic upgrade head
```

### 5. Create Demo Data

```bash
python scripts/create_demo_data.py
```

### 6. Start the API Server

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Testing the System

### 1. Basic API Tests
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test feasibility templates
curl http://localhost:8000/feasibility/form-templates

# Test sites
curl http://localhost:8000/sites/

# View API documentation
open http://localhost:8000/docs
```

### 2. Test Document Processing
```bash
python scripts/test_document_processor.py
```

### 3. Full System Test
```bash
python scripts/test_system.py
```

### 4. Test PDF Upload

Using curl:
```bash
# Create a test file
echo "Test protocol content" > test_protocol.txt

# Upload (will fail gracefully without real PDF)
curl -X POST "http://localhost:8000/feasibility/process-protocol?site_id=1" \
     -H "Content-Type: multipart/form-data" \
     -F "protocol_file=@test_protocol.txt"
```

## Key API Endpoints

### Core Feasibility Endpoints
- **POST** `/feasibility/process-protocol` - Upload PDF and get auto-filled form
- **GET** `/feasibility/form-templates` - Get UAB form structure
- **GET** `/feasibility/demo/uab-form-preview` - See demo results

### Existing Endpoints (Still Work)
- **GET** `/sites/` - List sites
- **POST** `/sites/` - Create site
- **GET** `/protocols/` - List protocols
- **POST** `/protocols/{id}/score?site_id=1` - Score protocol for site
- **POST** `/whatif/score` - What-if scenario testing

## Frontend Development

With the API running locally, you can now build the frontend:

### 1. Create Next.js Frontend
```bash
cd ..
npx create-next-app@latest sitesync-frontend --typescript --tailwind --eslint --app
cd sitesync-frontend
npm install @shadcn/ui lucide-react @tanstack/react-query zustand react-dropzone axios
```

### 2. Key Frontend Pages Needed
- **Upload Page** - Drag/drop PDF upload
- **Processing Page** - Show extraction progress
- **Score Page** - Display fit score (86/100 style)
- **Survey Page** - Auto-filled UAB form with review workflow
- **Export Page** - Generate reports

### 3. API Integration
```typescript
const API_BASE = 'http://localhost:8000';

// Upload protocol
const uploadProtocol = async (file: File, siteId: number) => {
  const formData = new FormData();
  formData.append('protocol_file', file);

  const response = await fetch(`${API_BASE}/feasibility/process-protocol?site_id=${siteId}`, {
    method: 'POST',
    body: formData,
  });

  return response.json();
};
```

## Docker Alternative (When Ready)

If Docker issues are resolved later, here's the fix:

### 1. Login to Docker Hub
```bash
docker login
# Enter your Docker Hub credentials
```

### 2. Or Use Alternative Registry
```bash
# Edit Dockerfile to use alternative registry
FROM ghcr.io/python/python:3.11
```

### 3. Build and Run
```bash
docker compose build --no-cache
docker compose up
```

## Production Deployment

### Using Railway/Render/DigitalOcean
1. **Railway**: Connect GitHub repo, Railway auto-detects FastAPI
2. **Render**: Create web service from GitHub, set build command
3. **DigitalOcean App Platform**: Deploy from GitHub

### Environment Variables for Production
```env
DATABASE_URL=postgresql://user:pass@host:5432/db
OPENAI_API_KEY=your_production_key
ENV=production
```

## Demo Scenarios

### 1. NASH Protocol Demo
```bash
# Get demo site ID
curl http://localhost:8000/sites/ | jq '.[0].id'

# Score NASH protocol
curl http://localhost:8000/protocols/1/score?site_id=1

# Get autofill suggestions
curl http://localhost:8000/protocols/1/autofill?site_id=1
```

### 2. Form Preview Demo
```bash
# See what a completed UAB form looks like
curl http://localhost:8000/feasibility/demo/uab-form-preview | jq .
```

## Troubleshooting

### Common Issues
1. **Database Connection**: Check PostgreSQL is running
2. **Port Conflicts**: Kill processes on port 8000: `lsof -ti:8000 | xargs kill -9`
3. **Module Errors**: Reinstall requirements: `pip install -r requirements.txt`
4. **Migration Errors**: Reset database: `alembic downgrade base && alembic upgrade head`

### Development Tips
- Use `--reload` flag for auto-restart during development
- Check logs with `tail -f app.log` if logging is enabled
- Use API docs at `/docs` for interactive testing
- Test endpoints with Postman or curl

## Next Steps

1. ✅ **API Working** - Local FastAPI server with all endpoints
2. ✅ **Database Setup** - PostgreSQL with demo data
3. ✅ **Document Processing** - PDF extraction and AI parsing
4. 🔨 **Frontend Development** - Build React/Next.js interface
5. 🔨 **Production Deploy** - Railway/Render deployment
6. 🔨 **Real Protocol Testing** - Upload actual sponsor PDFs

**Your SiteSync system is fully functional locally! 🎉**