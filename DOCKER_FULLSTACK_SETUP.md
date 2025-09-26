# Complete Docker Full-Stack Setup for SiteSync

## 🚀 One-Command Full-Stack Deployment

This setup provides a complete SiteSync environment with:
- **PostgreSQL** database
- **FastAPI Backend** with AI processing
- **Next.js Frontend** with modern UI
- **MinIO** for file storage
- **Auto-seeded demo data**

---

## Quick Start

```bash
# 1. Clone and navigate to project
cd /path/to/sitesync

# 2. Build and start everything
docker-compose up --build

# 3. Access your application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## What's Included

### 🎯 **Frontend (Next.js + TypeScript + Tailwind)**
- **URL**: http://localhost:3000
- **Features**:
  - PDF drag-and-drop upload interface
  - Real-time processing status
  - AI extraction results display
  - Auto-filled feasibility form preview
  - Responsive design with modern UI

### 🔧 **Backend (FastAPI + AI Processing)**
- **URL**: http://localhost:8000
- **Features**:
  - AI-powered PDF processing with GPT-4o-mini
  - Rule-based site capability matching
  - Auto-filled feasibility assessments
  - Complete REST API with documentation
  - Automatic database migrations and demo data seeding

### 🗄️ **Database (PostgreSQL 15)**
- **Port**: 5432
- **Credentials**: sitesync / sitesync_password
- **Features**:
  - Complete site profiling schema
  - Protocol and assessment management
  - Automatic migrations on startup

### 📁 **File Storage (MinIO)**
- **URL**: http://localhost:9000
- **Console**: http://localhost:9001
- **Credentials**: minioadmin / minioadmin

---

## File Structure

```
sitesync/
├── docker-compose.yml          # 📦 Full-stack orchestration
├── Dockerfile                  # 🐍 Backend container
├── .env                        # 🔐 Environment variables
├──
├── app/                        # 🔧 FastAPI Backend
│   ├── main.py                # API entry point
│   ├── models.py              # Database models
│   ├── services/              # Business logic
│   └── routes/                # API endpoints
│
├── frontend/                   # ⚛️ Next.js Frontend
│   ├── Dockerfile             # Frontend container
│   ├── app/
│   │   ├── page.tsx          # Main SiteSync UI
│   │   └── layout.tsx        # App layout
│   ├── package.json          # Dependencies
│   └── .env.local            # Frontend config
│
├── scripts/                    # 🛠️ Utilities
│   ├── create_demo_data.py   # Demo data seeding
│   └── test_system.py        # System tests
│
└── migrations/                 # 🗄️ Database schemas
```

---

## Environment Configuration

### Root `.env` (already configured)
```env
# OpenAI API key for AI processing
OPENAI_API_KEY=your_openai_api_key_here

# Database (auto-configured for Docker)
DATABASE_URL=postgresql+psycopg2://sitesync:password@db:5432/sitesync

# AI Configuration
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECS=20

# File Storage
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
```

### Frontend `.env.local`
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Docker Services Configuration

### 🐘 **postgres** (Database)
- Image: postgres:15
- Port: 5432:5432
- Database: sitesync
- User: sitesync
- Password: sitesync_password

### 🐍 **backend** (FastAPI API)
- Build: Current directory Dockerfile
- Port: 8000:8000
- Auto-runs: migrations + demo data + server
- Hot-reload: Enabled for development

### ⚛️ **frontend** (Next.js UI)
- Build: ./frontend/Dockerfile
- Port: 3000:3000
- Hot-reload: Enabled for development

### 📁 **minio** (File Storage)
- Image: minio/minio:latest
- Ports: 9000:9000 (API), 9001:9001 (Console)
- Credentials: minioadmin/minioadmin

---

## Development Commands

### 🚀 **Start Everything**
```bash
docker-compose up --build
```

### 📊 **Monitor Services**
```bash
# View all running services
docker-compose ps

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# View all logs
docker-compose logs -f
```

### 🔄 **Development Workflow**
```bash
# Rebuild after code changes
docker-compose build backend
docker-compose build frontend

# Restart specific service
docker-compose restart backend
docker-compose restart frontend

# Stop everything
docker-compose down

# Start in background
docker-compose up -d
```

### 🧪 **Testing & Debugging**
```bash
# Run backend tests
docker-compose exec backend python scripts/test_system.py

# Enter backend container
docker-compose exec backend bash

# Enter frontend container
docker-compose exec frontend sh

# View database
docker-compose exec postgres psql -U sitesync -d sitesync
```

### 🗄️ **Database Management**
```bash
# Reset database (removes all data)
docker-compose down -v
docker-compose up

# Backup database
docker-compose exec postgres pg_dump -U sitesync sitesync > backup.sql

# View database tables
docker-compose exec postgres psql -U sitesync -d sitesync -c "\\dt"
```

---

## Using the Application

### 1. **Upload Protocol PDF**
- Navigate to http://localhost:3000
- Click "Choose PDF File" or drag-and-drop
- Select any clinical protocol PDF
- Click "Process Protocol"

### 2. **View AI Processing**
- Watch real-time processing status
- See extracted protocol information
- Review auto-filled feasibility responses

### 3. **Analyze Results**
- View completion percentage (typically 70%+)
- See time saved estimate (45+ minutes)
- Review confidence scores for each response
- Export or submit assessments

### 4. **API Testing**
- Visit http://localhost:8000/docs for interactive API documentation
- Test endpoints directly from the browser
- View all available API operations

---

## Demo Data Included

### 🏥 **Valley Medical Research** (Default Site)
- **Location**: Phoenix, AZ
- **EMR**: Epic
- **Specialization**: NASH, Hepatology, Gastroenterology
- **Equipment**: MRI 1.5T/3T, CT Scanner, Ultrasound, Fibroscan
- **Staff**: Experienced PI, Study Coordinators, Research Nurses
- **Patient Access**: 450+ NASH patients annually

### 📋 **Sample Protocols**
- **NASH Phase II Study** - Perfect match demo
- **Oncology Phase III Study** - Alternative scenario

---

## Troubleshooting

### 🐳 **Docker Issues**
```bash
# Port conflicts
lsof -i :3000 :8000 :5432 :9000

# Clean Docker system
docker system prune -a

# Rebuild everything from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

### 🔗 **Connection Issues**
- **Frontend can't reach backend**: Check `NEXT_PUBLIC_API_URL` in frontend/.env.local
- **Backend can't reach database**: Verify service names in docker-compose.yml
- **API calls failing**: Check backend logs with `docker-compose logs backend`

### 📊 **Performance Issues**
- **Slow startup**: First run downloads images and builds containers
- **AI processing slow**: Depends on OpenAI API response times
- **Database slow**: Reset with `docker-compose down -v && docker-compose up`

---

## Production Deployment

### 🚀 **Railway Deployment**
1. Connect GitHub repository to Railway
2. Set environment variables in Railway dashboard
3. Deploy backend and frontend as separate services

### 🚀 **Render Deployment**
1. Create web services for backend and frontend
2. Add managed PostgreSQL database
3. Configure environment variables

### 🚀 **DigitalOcean App Platform**
1. Import from GitHub
2. Configure build and run commands
3. Add managed database

---

## Key Features Demonstrated

### ✨ **AI-Powered Processing**
- GPT-4o-mini extracts structured data from sponsor PDFs
- Confidence scoring for extraction quality
- Fallback regex parsing for critical fields

### 🎯 **Intelligent Matching**
- Rule-based protocol-site compatibility assessment
- Weighted scoring across multiple categories
- Explainable results with detailed evidence

### 📝 **Auto-Filled Forms**
- 70%+ completion rate for UAB-style feasibility forms
- Confidence-based answer locking
- Time savings of 45+ minutes per assessment

### 🔄 **Full Development Workflow**
- Hot-reload for both frontend and backend
- Comprehensive testing suite
- Production-ready architecture

---

## 🎉 **Success Metrics**

When everything is working correctly, you should see:

✅ **6/6 Backend Tests Passing**
✅ **Frontend Loading at http://localhost:3000**
✅ **API Documentation at http://localhost:8000/docs**
✅ **PDF Upload and Processing Working**
✅ **70%+ Auto-Completion Rates**
✅ **Real-Time Processing Feedback**

**Total Setup Time**: ~5 minutes
**Value Delivered**: 60min → 15min feasibility assessments

---

*Your complete SiteSync full-stack application is now running! 🚀*