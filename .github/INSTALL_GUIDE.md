# IntelliWiz Installation Guide

Complete guide for setting up the IntelliWiz Enterprise Platform on macOS and Linux.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (Recommended)](#quick-start-recommended)
- [Platform-Specific Installation](#platform-specific-installation)
  - [macOS Installation](#macos-installation)
  - [Linux Installation](#linux-installation)
- [Post-Installation Setup](#post-installation-setup)
- [Troubleshooting](#troubleshooting)
- [Common Errors](#common-errors)

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Python | **3.11.9** (recommended) | Application runtime |
| PostgreSQL | 14.2+ with PostGIS | Primary database |
| Redis | 6.0+ | Caching and Celery broker |
| Git | 2.30+ | Version control |

### System Requirements

**macOS:**
- macOS 12.0 (Monterey) or later
- 8GB RAM minimum, 16GB recommended
- 10GB free disk space
- Intel or Apple Silicon CPU

**Linux:**
- Ubuntu 20.04+, RHEL 8+, or similar
- 8GB RAM minimum, 16GB recommended
- 10GB free disk space
- Optional: NVIDIA GPU with CUDA 12.1+ for ML acceleration

---

## Quick Start (Recommended)

This method uses our smart installer that automatically detects your platform and installs the correct dependencies.

### 1. Install Python 3.11.9

**Using pyenv (recommended for version management):**

```bash
# Install pyenv (if not already installed)
# macOS:
brew install pyenv

# Linux:
curl https://pyenv.run | bash

# Install Python 3.11.9
pyenv install 3.11.9

# Set as local version for this project
cd /path/to/DJANGO5-master
pyenv local 3.11.9

# Verify
python --version  # Should show: Python 3.11.9
```

**Using system package manager:**

```bash
# macOS:
brew install python@3.11

# Ubuntu/Debian:
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv python3.11-dev

# RHEL/CentOS:
sudo dnf install python3.11 python3.11-devel
```

### 2. Create Virtual Environment

```bash
# Navigate to project directory
cd /path/to/DJANGO5-master

# Remove old venv (if it exists)
rm -rf venv

# Create new venv with Python 3.11.9
~/.pyenv/versions/3.11.9/bin/python -m venv venv

# Activate venv
source venv/bin/activate

# Verify Python version in venv
python --version  # Should show: Python 3.11.9
```

### 3. Run Smart Installer

```bash
# Full installation (recommended)
python scripts/install_dependencies.py

# Or preview first (dry run)
python scripts/install_dependencies.py --dry-run

# Or minimal installation (core only)
python scripts/install_dependencies.py --minimal
```

The installer will:
- ✅ Detect your platform (macOS/Linux)
- ✅ Verify Python version
- ✅ Check virtual environment
- ✅ Install correct platform-specific dependencies
- ✅ Validate installation
- ✅ Provide next steps

### 4. Initialize Database

```bash
# Run migrations
python manage.py migrate

# Initialize database with default data
python manage.py init_intelliwiz default

# Create superuser (optional)
python manage.py createsuperuser
```

### 5. Start Development Server

```bash
# HTTP only
python manage.py runserver

# With WebSockets (recommended)
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

Access the application at: http://localhost:8000

---

## Platform-Specific Installation

If you prefer manual installation or the smart installer doesn't work for your setup.

### macOS Installation

#### Step 1: Install System Dependencies

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required packages
brew install postgresql@14 redis git python@3.11

# Start services
brew services start postgresql@14
brew services start redis
```

#### Step 2: Setup Python Environment

```bash
# Install Python 3.11.9 with pyenv
pyenv install 3.11.9
pyenv local 3.11.9

# Create virtual environment
~/.pyenv/versions/3.11.9/bin/python -m venv venv
source venv/bin/activate
```

#### Step 3: Install Python Dependencies

⚠️ **IMPORTANT**: Do NOT use `pip install -r requirements.txt` (this file has been removed).

```bash
# Install macOS-specific dependencies
pip install -r requirements/base-macos.txt
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
pip install -r requirements/concurrency.txt
pip install -r requirements/sentry.txt
pip install -r requirements/feature_flags.txt

# Optional: AI/ML features (TensorFlow, PyTorch, etc.)
pip install -r requirements/ai_requirements.txt
pip install -r requirements/speech_to_text_requirements.txt
```

**What gets installed on macOS:**
- ✅ Django 5.2.1 and REST framework
- ✅ PostgreSQL adapter (psycopg3 with connection pooling)
- ✅ Celery for task queue
- ✅ PyTorch with Metal Performance Shaders (MPS) support
- ✅ TensorFlow with CPU optimizations
- ❌ NO CUDA packages (not available on macOS)

#### Step 4: Configure Database

```bash
# Create PostgreSQL database
createdb intelliwiz_dev

# Enable PostGIS extension
psql intelliwiz_dev -c "CREATE EXTENSION postgis;"

# Create .env file (copy from example)
cp .env.example .env

# Edit .env with your database credentials
nano .env
```

#### Step 5: Run Migrations

```bash
python manage.py migrate
python manage.py init_intelliwiz default
```

---

### Linux Installation

#### Step 1: Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y \
    postgresql-14 postgresql-14-postgis-3 \
    redis-server \
    python3.11 python3.11-venv python3.11-dev \
    git build-essential \
    libpq-dev libgeos-dev libproj-dev \
    libjpeg-dev libpng-dev

# Start services
sudo systemctl start postgresql
sudo systemctl start redis
sudo systemctl enable postgresql
sudo systemctl enable redis
```

**RHEL/CentOS:**
```bash
sudo dnf install -y \
    postgresql14-server postgresql14-contrib postgis33_14 \
    redis \
    python3.11 python3.11-devel \
    git gcc gcc-c++ make \
    libpq-devel geos-devel proj-devel

# Initialize and start PostgreSQL
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl start redis
sudo systemctl enable postgresql
sudo systemctl enable redis
```

#### Step 2: Install NVIDIA CUDA (Optional - for GPU acceleration)

**Only if you have an NVIDIA GPU:**

```bash
# Check if NVIDIA GPU is present
lspci | grep -i nvidia

# Install NVIDIA drivers (Ubuntu)
sudo ubuntu-drivers autoinstall

# Install CUDA Toolkit 12.1
wget https://developer.download.nvidia.com/compute/cuda/12.1.0/local_installers/cuda_12.1.0_530.30.02_linux.run
sudo sh cuda_12.1.0_530.30.02_linux.run

# Verify installation
nvidia-smi
nvcc --version
```

#### Step 3: Setup Python Environment

```bash
# Install Python 3.11.9 with pyenv
curl https://pyenv.run | bash

# Add to ~/.bashrc (if not already present)
echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# Install Python 3.11.9
pyenv install 3.11.9
pyenv local 3.11.9

# Create virtual environment
~/.pyenv/versions/3.11.9/bin/python -m venv venv
source venv/bin/activate
```

#### Step 4: Install Python Dependencies

```bash
# Install Linux-specific dependencies (includes CUDA if available)
pip install -r requirements/base-linux.txt
pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
pip install -r requirements/concurrency.txt
pip install -r requirements/sentry.txt
pip install -r requirements/feature_flags.txt
pip install -r requirements/ai_requirements.txt
pip install -r requirements/speech_to_text_requirements.txt
```

**What gets installed on Linux:**
- ✅ Django 5.2.1 and REST framework
- ✅ PostgreSQL adapter (psycopg3 with connection pooling)
- ✅ Celery for task queue
- ✅ PyTorch with CUDA 12.1 support (if NVIDIA GPU present)
- ✅ TensorFlow with CUDA support
- ✅ NVIDIA CUDA libraries (14 packages for GPU acceleration)

#### Step 5: Configure Database

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE intelliwiz_dev;
CREATE USER intelliwiz WITH PASSWORD 'your_secure_password';
ALTER ROLE intelliwiz SET client_encoding TO 'utf8';
ALTER ROLE intelliwiz SET default_transaction_isolation TO 'read committed';
ALTER ROLE intelliwiz SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE intelliwiz_dev TO intelliwiz;

# Enable PostGIS
\c intelliwiz_dev
CREATE EXTENSION postgis;
\q

# Create .env file
cp .env.example .env
nano .env  # Edit with your credentials
```

#### Step 6: Run Migrations

```bash
python manage.py migrate
python manage.py init_intelliwiz default
```

---

## Post-Installation Setup

### 1. Verify Installation

```bash
# Check for CUDA packages (should be empty on macOS)
pip list | grep nvidia

# Verify critical packages
python -c "import django; print(f'Django: {django.__version__}')"
python -c "import rest_framework; print('DRF: OK')"
python -c "import celery; print('Celery: OK')"
python -c "import psycopg; print('PostgreSQL (psycopg3): OK')"

# Check PyTorch backend (macOS with Apple Silicon)
python -c "import torch; print(f'MPS Available: {torch.backends.mps.is_available() if hasattr(torch.backends, \"mps\") else False}')"

# Check PyTorch backend (Linux with NVIDIA GPU)
python -c "import torch; print(f'CUDA Available: {torch.cuda.is_available()}')"

# Run Django system check
python manage.py check
```

### 2. Start Background Services

```bash
# Start Celery workers
./scripts/celery_workers.sh start

# Or manually start individual workers
celery -A intelliwiz_config worker -Q default -n default_worker -c 4 --loglevel=info
celery -A intelliwiz_config worker -Q high_priority -n high_priority_worker -c 2 --loglevel=info
celery -A intelliwiz_config worker -Q ml_queue -n ml_worker -c 2 --loglevel=info

# Start Celery beat scheduler
celery -A intelliwiz_config beat --loglevel=info
```

### 3. Run Tests (Optional)

```bash
# Run full test suite
python -m pytest --cov=apps --cov-report=html:coverage_reports/html --tb=short -v

# Run specific app tests
python -m pytest apps/activity/tests/ -v
```

### 4. Access the Application

- **Django Admin**: http://localhost:8000/admin/
- **API Documentation**: http://localhost:8000/api/v2/docs/
- **Health Check**: http://localhost:8000/health/

---

## Troubleshooting

### Common Issues

#### 1. `nvidia-cublas-cu12` Not Found (macOS)

**Problem**: You're trying to install Linux CUDA packages on macOS.

**Solution**:
```bash
# DO NOT use root requirements.txt
# Use the smart installer:
python scripts/install_dependencies.py

# OR manually use macOS-specific file:
pip install -r requirements/base-macos.txt
```

#### 2. Python Version Mismatch

**Problem**: `pip` shows errors about Python version requirements.

**Solution**:
```bash
# Verify Python version
python --version  # Should be 3.11.9

# If wrong version, recreate venv
rm -rf venv
~/.pyenv/versions/3.11.9/bin/python -m venv venv
source venv/bin/activate
python --version  # Verify again
```

#### 3. scikit-learn Build Errors

**Problem**: `scikit-learn` fails to build on Python 3.13+.

**Solution**:
```bash
# Downgrade to Python 3.11.9 (recommended)
pyenv install 3.11.9
pyenv local 3.11.9

# Recreate venv
rm -rf venv
~/.pyenv/versions/3.11.9/bin/python -m venv venv
source venv/bin/activate
```

#### 4. PostgreSQL Connection Errors

**Problem**: `django.db.utils.OperationalError: could not connect to server`

**Solution**:
```bash
# Check if PostgreSQL is running
# macOS:
brew services list | grep postgresql

# Linux:
sudo systemctl status postgresql

# Verify connection settings in .env
cat .env | grep DB_

# Test connection manually
psql -h localhost -U intelliwiz -d intelliwiz_dev
```

#### 5. Redis Connection Errors

**Problem**: Celery can't connect to Redis.

**Solution**:
```bash
# Check if Redis is running
# macOS:
brew services list | grep redis

# Linux:
sudo systemctl status redis

# Test connection
redis-cli ping  # Should return PONG

# Check Redis URL in .env
cat .env | grep REDIS_URL
```

#### 6. Virtual Environment Not Found

**Problem**: Commands fail because venv is not activated.

**Solution**:
```bash
# Always activate venv first
source venv/bin/activate

# Verify activation
which python  # Should point to venv/bin/python
python --version
```

#### 7. Missing System Dependencies (Linux)

**Problem**: Build failures for packages like `psycopg` or `Pillow`.

**Solution**:
```bash
# Ubuntu/Debian:
sudo apt-get install -y \
    python3.11-dev \
    libpq-dev \
    libgeos-dev \
    libproj-dev \
    libjpeg-dev \
    libpng-dev \
    build-essential

# RHEL/CentOS:
sudo dnf install -y \
    python3.11-devel \
    libpq-devel \
    geos-devel \
    proj-devel \
    libjpeg-devel \
    libpng-devel \
    gcc gcc-c++ make
```

---

## Common Errors

### Error: "ModuleNotFoundError: No module named 'django'"

**Cause**: Virtual environment not activated or dependencies not installed.

**Fix**:
```bash
source venv/bin/activate
python scripts/install_dependencies.py
```

### Error: "django.core.exceptions.ImproperlyConfigured: Requested setting..."

**Cause**: Missing or incorrect `.env` file.

**Fix**:
```bash
cp .env.example .env
nano .env  # Edit with your settings
```

### Error: "psycopg.OperationalError: FATAL: password authentication failed"

**Cause**: Incorrect database credentials in `.env`.

**Fix**:
```bash
# Edit .env with correct credentials
nano .env

# Test connection
psql -h localhost -U intelliwiz -d intelliwiz_dev
```

### Error: "ImportError: cannot import name 'MPS' from 'torch.backends'"

**Cause**: Trying to use MPS on non-Apple Silicon Mac or old PyTorch version.

**Fix**:
```bash
# Upgrade PyTorch
pip install --upgrade torch torchvision torchaudio

# Or ignore MPS if on Intel Mac (it's optional)
```

---

## Next Steps

After successful installation:

1. **Read the Documentation**:
   - [CLAUDE.md](../CLAUDE.md) - Quick reference guide
   - [System Architecture](../docs/architecture/SYSTEM_ARCHITECTURE.md) - Understand the system
   - [Common Commands](../docs/workflows/COMMON_COMMANDS.md) - Useful commands

2. **Explore the Admin Interface**:
   - Visit http://localhost:8000/admin/
   - Login with superuser credentials
   - Explore the Security AI Mentor

3. **Run the Test Suite**:
   ```bash
   python -m pytest --cov=apps --cov-report=html -v
   ```

4. **Start Development**:
   - Review [Development Best Practices](../CLAUDE.md#development-best-practices)
   - Check [Architecture Limits](../docs/architecture/adr/001-file-size-limits.md)
   - Read [Refactoring Patterns](../docs/architecture/REFACTORING_PATTERNS.md)

---

## Getting Help

- **Installation Issues**: Check this guide's [Troubleshooting](#troubleshooting) section
- **Runtime Issues**: See [Common Issues](../docs/troubleshooting/COMMON_ISSUES.md)
- **Architecture Questions**: Review [System Architecture](../docs/architecture/SYSTEM_ARCHITECTURE.md)
- **Security Concerns**: Contact security team immediately

---

**Last Updated**: November 10, 2025
**Maintainer**: Development Team
**Version**: 1.0.0
