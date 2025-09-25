# YOUTILITY5 AI Integration Setup Guide

## 🎯 Overview

This guide provides comprehensive instructions for setting up the AI integration in YOUTILITY5, including txtai (semantic search & RAG with PostgreSQL/pgvector), MindsDB (ML database automation), and a unified smart dashboard system.

**Architecture Update**: This implementation uses a simplified architecture with PostgreSQL + pgvector for vector storage, eliminating the need for separate vector databases like ChromaDB.

## 📋 What's Been Created

### Phase 1: Foundation & Infrastructure ✅ COMPLETED

#### 1.1 Django Apps Structure ✅
- **`apps/txtai_engine/`** - Semantic search and RAG functionality
- **`apps/mindsdb_engine/`** - Machine learning and predictive analytics
- **`apps/ai_orchestrator/`** - Workflow coordination across AI engines
- **`apps/smart_dashboard/`** - Unified AI dashboard interface

#### 1.2 Database Models ✅
- Complete model definitions for all AI engines
- Vector storage models for semantic search
- ML model registry and prediction tracking
- Workflow orchestration models
- Dashboard and widget management models

#### 1.3 Infrastructure Setup ✅
- Docker Compose configuration for all AI services
- Nginx API Gateway with rate limiting
- Redis for caching and task queuing
- PostgreSQL with pgvector extension for vector storage
- MindsDB for ML automation
- Prometheus & Grafana for monitoring
- Celery for background task processing

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- PostgreSQL (existing YOUTILITY5 database)
- Minimum 8GB RAM, 5GB disk space

### 1. Deploy AI Infrastructure

```bash
# Make the deployment script executable
chmod +x scripts/deploy_ai_infrastructure.sh

# Run the full deployment
./scripts/deploy_ai_infrastructure.sh deploy
```

### 2. Configure Environment

```bash
# Copy and customize the AI environment file
cp .env.ai .env.ai.local

# Edit with your specific configurations
nano .env.ai.local
```

### 3. Verify Deployment

```bash
# Check all services are healthy
./scripts/deploy_ai_infrastructure.sh check-health

# View service logs
./scripts/deploy_ai_infrastructure.sh logs
```

## 🌐 Service URLs

After deployment, the following services will be available:

| Service | URL | Description |
|---------|-----|-------------|
| AI Gateway | http://localhost:8080 | Main application with AI routing |
| MindsDB API | http://localhost:47334 | ML database automation |
| Model Server | http://localhost:8001 | Custom model serving |
| Grafana | http://localhost:3000 | Monitoring dashboards (admin/admin123) |
| Prometheus | http://localhost:9090 | Metrics collection |
| PostgreSQL | localhost:5432 | Main database with pgvector for embeddings |

## 📁 Project Structure

```
YOUTILITY5/
├── apps/
│   ├── txtai_engine/          # Semantic search & RAG
│   │   ├── models.py          # Vector storage models
│   │   ├── services.py        # Search & RAG services
│   │   ├── views.py           # API endpoints
│   │   ├── admin.py           # Admin interface
│   │   └── signals.py         # Auto-indexing
│   │
│   ├── mindsdb_engine/        # ML & Predictions
│   │   ├── models.py          # ML model registry
│   │   ├── services.py        # Prediction services
│   │   ├── views.py           # ML API endpoints
│   │   └── admin.py           # Model management
│   │
│   ├── ai_orchestrator/       # Workflow coordination
│   │   ├── models.py          # Workflow definitions
│   │   ├── services.py        # Orchestration logic
│   │   └── views.py           # Workflow management
│   │
│   └── smart_dashboard/       # Unified dashboards
│       ├── models.py          # Dashboard & widgets
│       ├── services.py        # Dashboard services
│       ├── views.py           # Dashboard interface
│       └── templates/         # Dashboard templates
│
├── config/                    # Configuration files
│   ├── nginx/                 # API Gateway config
│   ├── prometheus/            # Monitoring config
│   ├── grafana/               # Dashboard config
│   ├── mindsdb_config.json    # MindsDB settings
│   └── celery.py              # Task queue config
│
├── scripts/
│   └── deploy_ai_infrastructure.sh  # Deployment script
│
├── requirements/
│   └── ai_requirements.txt    # AI dependencies
│
├── docker-compose.ai.yml      # AI services
├── Dockerfile.ai              # AI-enabled container
├── Dockerfile.model-server    # Model serving
└── .env.ai                    # Environment template
```

## 🔧 Configuration Guide

### API Keys Setup

Edit `.env.ai.local` and configure your API keys:

```bash
# OpenAI (optional)
OPENAI_API_KEY=sk-your-openai-key-here

# Anthropic (optional) 
ANTHROPIC_API_KEY=your-anthropic-key-here

# Hugging Face (recommended)
HUGGINGFACE_HUB_TOKEN=your-huggingface-token-here

# Monitoring
SENTRY_DSN=your-sentry-dsn-here
```

### Feature Flags

Control which AI features are enabled:

```bash
FEATURE_SEMANTIC_SEARCH=True
FEATURE_RAG_CHAT=True
FEATURE_PREDICTION_MODELS=True
FEATURE_ANOMALY_DETECTION=True
FEATURE_AUTO_REPORTING=True
```

## 📊 Dashboard Templates

The system includes pre-built dashboard templates:

### Executive AI Dashboard
- AI Insights Feed
- Predictive Analytics Charts
- High-level KPI Metrics
- Strategic Recommendations

### Operational AI Dashboard
- Real-time Workflow Status
- Anomaly Alerts
- System Performance Metrics
- Task Queue Monitoring

### Analytics AI Dashboard
- Semantic Search Analytics
- Model Performance Tracking
- User Behavior Insights
- Cross-engine Metrics

## 🔍 AI Engine Capabilities

### txtai Engine (with PostgreSQL/pgvector)
- **Semantic Search**: Natural language search across all content using pgvector
- **RAG (Retrieval Augmented Generation)**: Contextual AI responses
- **Document Intelligence**: Automatic content analysis
- **Knowledge Bases**: Domain-specific AI assistants
- **Unified Storage**: Vector embeddings stored directly in PostgreSQL for ACID compliance

### MindsDB Engine
- **Time Series Forecasting**: Predict trends and patterns
- **Classification Models**: Automated categorization
- **Anomaly Detection**: Real-time outlier identification  
- **AutoML**: Automatic model selection and training

### AI Orchestrator
- **Multi-engine Workflows**: Coordinate different AI services
- **Smart Routing**: Intelligent request distribution
- **Cross-engine Insights**: Combined AI analysis
- **Performance Monitoring**: Unified metrics and alerts

### Smart Dashboard
- **Drag-and-drop Widgets**: Customizable AI interfaces
- **Real-time Updates**: Live data streaming
- **Export Capabilities**: PDF, Excel, PNG exports
- **User Permissions**: Granular access control

## 🔄 Vector Storage Migration

If upgrading from a previous version that used ChromaDB or JSON embeddings:

### 1. Install pgvector Extension
```bash
# Run the migration to enable pgvector
python manage.py migrate txtai_engine
```

### 2. Migrate Existing Embeddings
```bash
# Preview the migration (dry run)
python manage.py migrate_embeddings_to_pgvector --dry-run

# Perform the actual migration
python manage.py migrate_embeddings_to_pgvector --confirm
```

### 3. Clean Up Legacy Data (Optional)
```bash
# After confirming the migration worked correctly
python manage.py cleanup_legacy_embeddings --confirm
```

## 🚦 Management Commands

### Service Management
```bash
# Start all AI services
./scripts/deploy_ai_infrastructure.sh start

# Stop all AI services  
./scripts/deploy_ai_infrastructure.sh stop

# Restart services
./scripts/deploy_ai_infrastructure.sh restart

# View logs for specific service
./scripts/deploy_ai_infrastructure.sh logs mindsdb
```

### Scaling
```bash
# Scale Celery workers
docker-compose -f docker-compose.ai.yml up -d --scale celery-worker=3

# Scale model servers
docker-compose -f docker-compose.ai.yml up -d --scale model-server=2
```

### Maintenance
```bash
# Clean up unused resources
docker system prune -f

# Full cleanup (⚠️ removes all data)
./scripts/deploy_ai_infrastructure.sh clean
```

## 📈 Monitoring & Alerts

### Grafana Dashboards
Access Grafana at http://localhost:3000 (admin/admin123) for:
- AI service performance metrics
- Resource utilization monitoring
- Custom alert configurations
- Business intelligence reports

### Prometheus Metrics
Key metrics being collected:
- Request rates and latencies
- Model inference times
- Vector search performance
- Queue processing stats
- Resource consumption

### Health Checks
Built-in health monitoring for:
- All AI service endpoints
- Database connections
- Cache availability
- Model server status
- Queue processor health

## 🔒 Security Features

- Rate limiting on all AI endpoints
- JWT authentication for API access
- Request/response logging
- Input validation and sanitization
- CORS protection
- SSL/TLS encryption ready

## 🎯 Next Steps: Phases 2-4

With Phase 1 complete, you can now proceed with:

**Phase 2: txtai Integration**
- Smart Document Search Hub
- Intelligent Report Analysis
- Smart Ticket Routing
- Asset Intelligence

**Phase 3: MindsDB Integration**
- Predictive Analytics Dashboard
- Automated Anomaly Detection
- Intelligent Scheduling
- Business Intelligence Portal

**Phase 4: Advanced AI Features**
- Conversational AI Assistant
- Automated Report Generation
- Smart Workflow Automation
- Unified AI Insights Hub

## 🆘 Troubleshooting

### Common Issues

1. **Services not starting**: Check Docker memory/disk space
2. **API timeouts**: Adjust timeout settings in nginx config
3. **Model loading errors**: Verify model file permissions
4. **Database connection issues**: Check PostgreSQL configuration

### Debug Mode
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with verbose output
./scripts/deploy_ai_infrastructure.sh deploy
```

### Support Channels
- Check service logs: `docker-compose -f docker-compose.ai.yml logs [service]`
- Monitor resource usage: Access Grafana dashboards
- Validate configuration: Run health checks

## 📚 Additional Resources

- [txtai Documentation](https://neuml.github.io/txtai/)
- [MindsDB Documentation](https://docs.mindsdb.com/)
- [Django REST Framework](https://www.django-rest-framework.org/)
- [Celery Documentation](https://docs.celeryproject.org/)

---

## 🎉 Congratulations!

You now have a complete AI integration infrastructure for YOUTILITY5! The system is ready for implementing advanced AI features across semantic search, machine learning, and intelligent automation.

Start exploring the capabilities through the smart dashboard interface and begin building the next phases of AI functionality.

## 🎨 Architecture Benefits

### Simplified Stack
- **Single Database**: All data (relational + vectors) in PostgreSQL
- **ACID Compliance**: Transactional consistency across all operations
- **Reduced Complexity**: Fewer services to manage and monitor
- **Lower Costs**: Reduced infrastructure and operational overhead

### Performance Benefits
- **pgvector Optimization**: Native PostgreSQL extension optimized for similarity search
- **Unified Queries**: Join vector search with relational data in single queries
- **Efficient Indexing**: Advanced vector indexing algorithms (IVFFlat, HNSW)
- **Memory Management**: PostgreSQL's mature memory management and caching

### Operational Advantages
- **Single Backup Strategy**: One database to backup and restore
- **Simplified Monitoring**: Monitor one database instead of multiple services
- **Easier Scaling**: PostgreSQL's proven scaling patterns
- **Better Security**: Centralized access control and encryption