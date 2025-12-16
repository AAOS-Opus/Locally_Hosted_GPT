#!/bin/bash

################################################################################
# Sovereign Assistant API - Environment Setup Script
################################################################################
#
# Purpose:
#   Automates complete Ubuntu 24.04 LTS server preparation for the Sovereign
#   Assistant API Phase 1 implementation. Sets up GPU support (CUDA 12.0+),
#   Python 3.11 virtual environment, vLLM inference server, directory structure,
#   systemd services, and all application dependencies.
#
# Prerequisites:
#   - Ubuntu 24.04 LTS (or compatible Debian-based system)
#   - NVIDIA GPU (A6000 or equivalent with 48GB+ VRAM)
#   - NVIDIA drivers already installed
#   - sudo/root access
#   - Internet connectivity for package downloads
#   - ~150GB free disk space
#
# Usage:
#   sudo bash setup_environment.sh [--clean]
#
#   Options:
#     --clean    Remove existing installation and start fresh
#
# Output:
#   - Console: Real-time progress with color-coded status messages
#   - Log file: /var/log/sovereign-assistant/setup_environment.log
#   - Directory structure: /opt/sovereign-assistant/
#
# Author: Sovereign Assistant Project
# Date: November 5, 2025
#
################################################################################

set -euo pipefail

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly APP_BASE_DIR="/opt/sovereign-assistant"
readonly APP_USER="sovereign-assistant"
readonly APP_GROUP="sovereign-assistant"
readonly LOG_DIR="/var/log/sovereign-assistant"
readonly VENV_PATH="${APP_BASE_DIR}/venv"
readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)
readonly LOG_FILE="${LOG_DIR}/setup_environment_${TIMESTAMP}.log"

# Global state
SCRIPT_EXIT_CODE=0
CLEANUP_ON_EXIT=false

################################################################################
# Logging and Output Functions
################################################################################

log() {
    local level="$1"
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $@" | tee -a "${LOG_FILE}"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $@" | tee -a "${LOG_FILE}"
}

log_error() {
    echo -e "${RED}[✗]${NC} $@" | tee -a "${LOG_FILE}"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $@" | tee -a "${LOG_FILE}"
}

print_section() {
    echo "" | tee -a "${LOG_FILE}"
    echo "═══════════════════════════════════════════════════════════════════" | tee -a "${LOG_FILE}"
    echo "  $@" | tee -a "${LOG_FILE}"
    echo "═══════════════════════════════════════════════════════════════════" | tee -a "${LOG_FILE}"
}

################################################################################
# Error Handling and Cleanup
################################################################################

error_exit() {
    log_error "$@"
    SCRIPT_EXIT_CODE=1
    cleanup_on_exit
    exit 1
}

cleanup_on_exit() {
    if [[ "${CLEANUP_ON_EXIT}" == "true" ]]; then
        log_warning "Cleaning up partial installation..."

        # Remove created directories
        if [[ -d "${APP_BASE_DIR}" ]]; then
            log_info "Removing application directory: ${APP_BASE_DIR}"
            rm -rf "${APP_BASE_DIR}" 2>/dev/null || true
        fi

        # Remove service files
        if [[ -f /etc/systemd/system/sovereign-assistant-vllm.service ]]; then
            systemctl stop sovereign-assistant-vllm.service 2>/dev/null || true
            rm -f /etc/systemd/system/sovereign-assistant-vllm.service
            systemctl daemon-reload
        fi

        log_info "Cleanup complete. System returned to previous state."
    fi
}

trap cleanup_on_exit EXIT

################################################################################
# Prerequisite Checks
################################################################################

check_prerequisites() {
    print_section "Checking Prerequisites"

    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        error_exit "This script must be run as root. Use: sudo bash $0"
    fi
    log_success "Running with root privileges"

    # Check Ubuntu version
    if ! grep -q "24.04" /etc/os-release 2>/dev/null; then
        log_warning "Not Ubuntu 24.04 LTS detected. Script may not work correctly."
        log_info "Continuing anyway (use at your own risk)..."
    else
        log_success "Ubuntu 24.04 LTS detected"
    fi

    # Check for NVIDIA GPU
    if ! command -v nvidia-smi &> /dev/null; then
        error_exit "nvidia-smi not found. NVIDIA drivers must be installed first."
    fi
    log_success "NVIDIA drivers installed (nvidia-smi found)"

    # Check GPU accessibility
    if ! nvidia-smi &>/dev/null; then
        error_exit "GPU not accessible. Please verify NVIDIA drivers are properly installed."
    fi
    log_success "GPU is accessible and responsive"

    # Check available disk space (require 150GB)
    local available_space=$(df /opt 2>/dev/null | tail -1 | awk '{print $4}')
    if [[ ${available_space} -lt 153600000 ]]; then
        log_warning "Less than 150GB available in /opt. Installation may fail."
    else
        log_success "Sufficient disk space available (>150GB)"
    fi

    # Check internet connectivity
    if ! ping -c 1 8.8.8.8 &> /dev/null; then
        log_warning "Internet connectivity check failed. Package downloads may fail."
    else
        log_success "Internet connectivity confirmed"
    fi
}

################################################################################
# System Updates
################################################################################

update_system() {
    print_section "Updating System Packages"

    log_info "Running apt update..."
    apt-get update -qq >> "${LOG_FILE}" 2>&1 || error_exit "Failed to update package lists"
    log_success "Package lists updated"

    # Install essential build tools
    log_info "Installing essential build tools..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        build-essential \
        curl \
        wget \
        git \
        pkg-config \
        ca-certificates \
        software-properties-common \
        >> "${LOG_FILE}" 2>&1 || error_exit "Failed to install build tools"
    log_success "Build tools installed"
}

################################################################################
# CUDA Toolkit Installation
################################################################################

install_cuda() {
    print_section "Installing CUDA Toolkit 12.0+"

    # Check if CUDA is already installed
    if command -v nvcc &> /dev/null; then
        local cuda_version=$(nvcc --version 2>/dev/null | grep -oP 'release \K[0-9.]+' || true)
        if [[ -n "${cuda_version}" ]]; then
            log_success "CUDA ${cuda_version} already installed"
            return 0
        fi
    fi

    log_info "Adding NVIDIA CUDA repository..."
    wget -O /tmp/cuda-keyring.deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb >> "${LOG_FILE}" 2>&1 \
        || error_exit "Failed to download CUDA keyring"
    dpkg -i /tmp/cuda-keyring.deb >> "${LOG_FILE}" 2>&1 || error_exit "Failed to install CUDA keyring"
    rm /tmp/cuda-keyring.deb
    log_success "CUDA repository added"

    log_info "Updating apt with CUDA repository..."
    apt-get update -qq >> "${LOG_FILE}" 2>&1 || error_exit "Failed to update apt with CUDA repo"
    log_success "Apt updated with CUDA repository"

    log_info "Installing CUDA Toolkit 12.4..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        cuda-toolkit-12-4 \
        >> "${LOG_FILE}" 2>&1 || error_exit "Failed to install CUDA Toolkit"
    log_success "CUDA Toolkit 12.4 installed"

    # Verify CUDA installation
    log_info "Verifying CUDA installation..."
    export PATH=/usr/local/cuda-12.4/bin:$PATH
    export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH

    if ! nvcc --version >> "${LOG_FILE}" 2>&1; then
        error_exit "CUDA verification failed: nvcc not working"
    fi

    local cuda_ver=$(nvcc --version 2>/dev/null | grep -oP 'release \K[0-9.]+')
    log_success "CUDA ${cuda_ver} verified and working"
}

################################################################################
# Python Environment Setup
################################################################################

setup_python_environment() {
    print_section "Setting up Python 3.11 Environment"

    log_info "Installing Python 3.11 and venv..."
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        python3.11 \
        python3.11-venv \
        python3.11-dev \
        >> "${LOG_FILE}" 2>&1 || error_exit "Failed to install Python 3.11"
    log_success "Python 3.11 installed"

    # Verify Python version
    if ! python3.11 --version >> "${LOG_FILE}" 2>&1; then
        error_exit "Python 3.11 verification failed"
    fi
    log_success "Python 3.11 verified: $(python3.11 --version)"

    log_info "Creating virtual environment at ${VENV_PATH}..."
    python3.11 -m venv "${VENV_PATH}" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to create virtual environment"
    log_success "Virtual environment created"

    # Activate virtual environment for this script
    source "${VENV_PATH}/bin/activate" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to activate virtual environment"
    log_success "Virtual environment activated"

    # Verify Python in venv
    if ! python --version >> "${LOG_FILE}" 2>&1; then
        error_exit "Python in venv verification failed"
    fi
    log_success "Python in venv verified: $(python --version)"

    # Upgrade pip
    log_info "Upgrading pip..."
    python -m pip install --upgrade pip setuptools wheel -q >> "${LOG_FILE}" 2>&1 || error_exit "Failed to upgrade pip"
    log_success "pip upgraded to latest version"
}

################################################################################
# PyTorch and vLLM Installation
################################################################################

install_pytorch_and_vllm() {
    print_section "Installing PyTorch with CUDA Support and vLLM"

    # Ensure venv is activated
    source "${VENV_PATH}/bin/activate" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to activate venv for PyTorch install"

    log_info "Installing PyTorch with CUDA 12.4 support..."
    python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 -q \
        >> "${LOG_FILE}" 2>&1 || error_exit "Failed to install PyTorch with CUDA support"
    log_success "PyTorch with CUDA support installed"

    # Verify PyTorch
    if ! python -c "import torch; print(f'PyTorch {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')" >> "${LOG_FILE}" 2>&1; then
        error_exit "PyTorch verification failed"
    fi
    log_success "PyTorch verified with CUDA support"

    log_info "Installing vLLM..."
    python -m pip install vllm -q --no-cache-dir >> "${LOG_FILE}" 2>&1 || error_exit "Failed to install vLLM"
    log_success "vLLM installed"

    # Verify vLLM
    log_info "Verifying vLLM installation and GPU support..."
    if ! python -c "from vllm import LLM; print('vLLM import successful')" >> "${LOG_FILE}" 2>&1; then
        error_exit "vLLM import verification failed"
    fi
    log_success "vLLM import verified"

    # Check GPU availability for vLLM
    if ! python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'; print(f'GPU available: {torch.cuda.get_device_name(0)}')" >> "${LOG_FILE}" 2>&1; then
        error_exit "GPU not available for vLLM"
    fi
    log_success "GPU available for vLLM inference"
}

################################################################################
# Create Directory Structure
################################################################################

create_directory_structure() {
    print_section "Creating Application Directory Structure"

    log_info "Creating base application directory..."
    mkdir -p "${APP_BASE_DIR}" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to create ${APP_BASE_DIR}"
    log_success "Base directory created: ${APP_BASE_DIR}"

    # Create subdirectories
    local subdirs=(
        "models"
        "configs"
        "logs"
        "data/assistants"
        "data/threads"
        "data/messages"
        "scripts"
        "backups"
        "migrations"
    )

    for subdir in "${subdirs[@]}"; do
        mkdir -p "${APP_BASE_DIR}/${subdir}" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to create ${subdir}"
    done
    log_success "All subdirectories created"

    # Create README files explaining purpose of each directory
    cat > "${APP_BASE_DIR}/models/README.md" << 'EOF'
# Models Directory

Contains downloaded LLM model files.

## Current Model
- Llama 3.1 70B Instruct (AWQ 4-bit quantization)
  - Size: ~40GB
  - Location: llama-3.1-70b-instruct-awq/ (after download)

## Expected Structure
```
models/
├── llama-3.1-70b-instruct-awq/
│   ├── model.safetensors
│   ├── config.json
│   ├── tokenizer.model
│   └── ...
```
EOF

    cat > "${APP_BASE_DIR}/configs/README.md" << 'EOF'
# Configuration Directory

Contains configuration files for all components.

## Files
- vllm_config.yml: vLLM inference server configuration
- app_config.yml: Application settings
- logging_config.yml: Logging configuration

## Customization
Configuration files contain placeholder values ready for Phase 1 customization.
EOF

    cat > "${APP_BASE_DIR}/data/README.md" << 'EOF'
# Data Directory

Contains persistent application data.

## Subdirectories
- assistants/: Assistant configurations and metadata
- threads/: Conversation thread records
- messages/: Message history (managed by SQLite)

Note: Primary persistence is SQLite at data.db in this directory.
EOF

    cat > "${APP_BASE_DIR}/scripts/README.md" << 'EOF'
# Scripts Directory

Contains operational scripts.

## Typical Contents
- backup.sh: Database backup procedures
- restore.sh: Database restore procedures
- health_check.sh: System health verification
- cleanup.sh: Maintenance and cleanup tasks
EOF

    log_success "README files created in key directories"
}

################################################################################
# Create Service User
################################################################################

create_service_user() {
    print_section "Creating Service User and Setting Permissions"

    # Check if user already exists
    if id "${APP_USER}" &>/dev/null; then
        log_success "Service user ${APP_USER} already exists"
    else
        log_info "Creating service user ${APP_USER}..."
        useradd -r -s /bin/bash -d "${APP_BASE_DIR}" "${APP_USER}" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to create service user"
        log_success "Service user created: ${APP_USER}"
    fi

    # Create group if it doesn't exist
    if ! getent group "${APP_GROUP}" > /dev/null; then
        log_info "Creating service group ${APP_GROUP}..."
        groupadd -r "${APP_GROUP}" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to create service group"
        log_success "Service group created: ${APP_GROUP}"
    fi

    # Add user to group
    usermod -a -G "${APP_GROUP}" "${APP_USER}" >> "${LOG_FILE}" 2>&1 || true

    log_info "Setting directory ownership..."
    chown -R "${APP_USER}:${APP_GROUP}" "${APP_BASE_DIR}" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to set ownership"
    log_success "Directory ownership set to ${APP_USER}:${APP_GROUP}"

    log_info "Setting directory permissions..."
    find "${APP_BASE_DIR}" -type d -exec chmod 750 {} \; >> "${LOG_FILE}" 2>&1 || error_exit "Failed to set directory permissions"
    find "${APP_BASE_DIR}" -type f -exec chmod 640 {} \; >> "${LOG_FILE}" 2>&1 || error_exit "Failed to set file permissions"
    log_success "Directory permissions set (750 for dirs, 640 for files)"
}

################################################################################
# Install Python Packages
################################################################################

install_python_packages() {
    print_section "Installing Python Application Packages"

    # Ensure venv is activated
    source "${VENV_PATH}/bin/activate" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to activate venv"

    # Create requirements.txt
    log_info "Creating requirements.txt with package specifications..."
    cat > "${APP_BASE_DIR}/requirements.txt" << 'EOF'
# Core Web Framework
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
python-multipart==0.0.6

# Database and ORM
sqlalchemy==2.0.23
alembic==1.13.0
sqlite3==1.1.0

# LLM Inference
torch==2.1.0
vllm==0.3.0

# Monitoring and Logging
prometheus-client==0.19.0
python-json-logger==2.0.7

# Testing and Development
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0
black==23.12.0
ruff==0.1.8
mypy==1.7.1

# Utilities
requests==2.31.0
python-dotenv==1.0.0
pyyaml==6.0.1
EOF
    log_success "requirements.txt created"

    log_info "Installing packages from requirements.txt..."
    python -m pip install -r "${APP_BASE_DIR}/requirements.txt" -q \
        >> "${LOG_FILE}" 2>&1 || error_exit "Failed to install Python packages"
    log_success "All Python packages installed"

    # Verify critical packages
    log_info "Verifying critical package imports..."
    python -c "
import fastapi
import sqlalchemy
import alembic
import prometheus_client
import vllm
print('All critical packages verified')
" >> "${LOG_FILE}" 2>&1 || error_exit "Package verification failed"
    log_success "Critical package imports verified"
}

################################################################################
# Generate Configuration Files
################################################################################

generate_configuration_files() {
    print_section "Generating Configuration Files"

    # vLLM Configuration
    log_info "Generating vLLM configuration..."
    cat > "${APP_BASE_DIR}/configs/vllm_config.yml" << 'EOF'
# vLLM Inference Server Configuration
# Phase 1 placeholder - customize in Phase 1 Step 3

inference_server:
  host: 127.0.0.1
  port: 8000

model:
  name: "meta-llama/Llama-3.1-70B-Instruct-AWQ"
  quantization: "awq"
  dtype: "float16"

performance:
  max_num_seqs: 8
  gpu_memory_utilization: 0.90
  max_model_len: 32768

tensor_parallel_size: 1
pipeline_parallel_size: 1

logging:
  level: "INFO"
  enable_request_logging: true

monitoring:
  enable_metrics: true
  metrics_port: 8002
EOF
    log_success "vLLM configuration generated"

    # Application Configuration
    log_info "Generating application configuration..."
    cat > "${APP_BASE_DIR}/configs/app_config.yml" << 'EOF'
# Sovereign Assistant API Configuration
# Phase 1 placeholder - customize in Phase 1

application:
  name: "Sovereign Assistant API"
  version: "0.1.0"
  environment: "development"

api:
  host: 127.0.0.1
  port: 8001
  workers: 1

database:
  type: "sqlite"
  path: "/opt/sovereign-assistant/data/data.db"

inference:
  server_url: "http://127.0.0.1:8000"
  timeout: 300

logging:
  level: "INFO"
  file: "/var/log/sovereign-assistant/app.log"
EOF
    log_success "Application configuration generated"

    # Logging Configuration
    log_info "Generating logging configuration..."
    cat > "${APP_BASE_DIR}/configs/logging_config.yml" << 'EOF'
# Logging Configuration
# Defines log levels, formats, and output destinations

version: 1
disable_existing_loggers: false

formatters:
  standard:
    format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

  json:
    format: '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'

handlers:
  console:
    class: logging.StreamHandler
    level: INFO
    formatter: standard
    stream: ext://sys.stdout

  file:
    class: logging.handlers.RotatingFileHandler
    level: DEBUG
    formatter: standard
    filename: /var/log/sovereign-assistant/app.log
    maxBytes: 104857600
    backupCount: 5

loggers:
  sovereign_assistant:
    level: DEBUG
    handlers: [console, file]

  vllm:
    level: INFO
    handlers: [console, file]

  sqlalchemy:
    level: INFO
    handlers: [console, file]

root:
  level: INFO
  handlers: [console, file]
EOF
    log_success "Logging configuration generated"

    # Set proper permissions on config files
    chmod 640 "${APP_BASE_DIR}/configs/"* >> "${LOG_FILE}" 2>&1
    chown "${APP_USER}:${APP_GROUP}" "${APP_BASE_DIR}/configs/"* >> "${LOG_FILE}" 2>&1
}

################################################################################
# Generate Systemd Service Template
################################################################################

generate_systemd_service() {
    print_section "Generating Systemd Service Template"

    log_info "Creating vLLM systemd service template..."
    cat > /etc/systemd/system/sovereign-assistant-vllm.service << 'EOF'
[Unit]
Description=Sovereign Assistant API - vLLM Inference Server
Documentation=https://github.com/your-org/sovereign-assistant
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=sovereign-assistant
Group=sovereign-assistant
WorkingDirectory=/opt/sovereign-assistant

# Environment configuration
Environment="PATH=/opt/sovereign-assistant/venv/bin:/usr/local/cuda-12.4/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:/opt/sovereign-assistant/venv/lib/python3.11/site-packages/torch/lib"
Environment="CUDA_HOME=/usr/local/cuda-12.4"
Environment="PYTHONUNBUFFERED=1"

# Service execution - placeholder, will be customized in Phase 1 Step 4
ExecStart=/opt/sovereign-assistant/venv/bin/python -m vllm.entrypoints.openai.api_server \
    --model meta-llama/Llama-3.1-70B-Instruct-AWQ \
    --quantization awq \
    --tensor-parallel-size 1 \
    --max-model-len 32768 \
    --max-num-seqs 8 \
    --gpu-memory-utilization 0.90 \
    --port 8000

# Restart policy
Restart=on-failure
RestartSec=10
StartLimitInterval=300
StartLimitBurst=3

# Timeout for graceful shutdown
TimeoutStopSec=30

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=sovereign-vllm

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF
    log_success "vLLM systemd service template created"

    log_info "Reloading systemd daemon..."
    systemctl daemon-reload >> "${LOG_FILE}" 2>&1 || error_exit "Failed to reload systemd daemon"
    log_success "Systemd daemon reloaded"

    log_info "Enabling vLLM service (not starting yet)..."
    systemctl enable sovereign-assistant-vllm.service >> "${LOG_FILE}" 2>&1 || error_exit "Failed to enable service"
    log_success "vLLM service enabled for auto-start"

    # Create API server service template placeholder
    log_info "Creating FastAPI application service template..."
    cat > /etc/systemd/system/sovereign-assistant-api.service << 'EOF'
[Unit]
Description=Sovereign Assistant API - FastAPI Application Server
Documentation=https://github.com/your-org/sovereign-assistant
After=network-online.target sovereign-assistant-vllm.service
Wants=network-online.target
Requires=sovereign-assistant-vllm.service

[Service]
Type=simple
User=sovereign-assistant
Group=sovereign-assistant
WorkingDirectory=/opt/sovereign-assistant

# Environment configuration
Environment="PATH=/opt/sovereign-assistant/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin"
Environment="PYTHONUNBUFFERED=1"

# Service execution - placeholder, will be implemented in Phase 3
ExecStart=/opt/sovereign-assistant/venv/bin/uvicorn \
    main:app \
    --host 127.0.0.1 \
    --port 8001 \
    --workers 1

Restart=on-failure
RestartSec=10
TimeoutStopSec=30

StandardOutput=journal
StandardError=journal
SyslogIdentifier=sovereign-api

LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF
    log_success "FastAPI service template created"
    systemctl daemon-reload >> "${LOG_FILE}" 2>&1
}

################################################################################
# Install and Verify SQLite
################################################################################

install_and_verify_sqlite() {
    print_section "Installing and Verifying SQLite"

    # SQLite is typically pre-installed, but ensure it's present
    log_info "Verifying SQLite installation..."
    if command -v sqlite3 &> /dev/null; then
        local sqlite_version=$(sqlite3 --version | awk '{print $1}')
        log_success "SQLite ${sqlite_version} is installed"
    else
        log_info "Installing SQLite3..."
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq sqlite3 >> "${LOG_FILE}" 2>&1 \
            || error_exit "Failed to install SQLite3"
        log_success "SQLite3 installed"
    fi

    # Verify version meets minimum requirement (3.40+)
    local sqlite_version=$(sqlite3 --version | grep -oP '\d+\.\d+' | head -1)
    if (( $(echo "$sqlite_version >= 3.40" | bc -l) )); then
        log_success "SQLite version ${sqlite_version} meets minimum requirement (3.40+)"
    else
        log_warning "SQLite version ${sqlite_version} is older than recommended (3.40+)"
    fi

    # Test SQLite functionality
    log_info "Testing SQLite functionality..."
    echo "SELECT sqlite_version();" | sqlite3 >> "${LOG_FILE}" 2>&1 || error_exit "SQLite functionality test failed"
    log_success "SQLite functionality verified"
}

################################################################################
# Setup Logging Infrastructure
################################################################################

setup_logging_infrastructure() {
    print_section "Setting up Logging Infrastructure"

    log_info "Creating logging directory..."
    mkdir -p "${LOG_DIR}" >> "${LOG_FILE}" 2>&1 || error_exit "Failed to create log directory"
    log_success "Logging directory created: ${LOG_DIR}"

    log_info "Setting logging directory permissions..."
    chmod 755 "${LOG_DIR}" >> "${LOG_FILE}" 2>&1
    chown -R syslog:adm "${LOG_DIR}" >> "${LOG_FILE}" 2>&1 || true
    log_success "Logging directory permissions configured"

    # Configure logrotate for application logs
    log_info "Configuring log rotation..."
    cat > /etc/logrotate.d/sovereign-assistant << 'EOF'
/var/log/sovereign-assistant/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 sovereign-assistant sovereign-assistant
    sharedscripts
    postrotate
        systemctl reload-or-restart rsyslog > /dev/null 2>&1 || true
    endscript
}
EOF
    log_success "Log rotation configured"
}

################################################################################
# Comprehensive Validation
################################################################################

validate_installation() {
    print_section "Comprehensive Installation Validation"

    local validation_passed=true

    # Check CUDA
    log_info "Validating CUDA installation..."
    if command -v nvcc &> /dev/null && nvcc --version &>/dev/null; then
        log_success "✓ CUDA installed and functional"
    else
        log_error "✗ CUDA validation failed"
        validation_passed=false
    fi

    # Check Python
    log_info "Validating Python 3.11..."
    if python3.11 --version &>/dev/null && [[ $(python3.11 --version | grep -oP '3\.\d+') == "3.11" ]]; then
        log_success "✓ Python 3.11 installed"
    else
        log_error "✗ Python 3.11 validation failed"
        validation_passed=false
    fi

    # Check virtual environment
    log_info "Validating virtual environment..."
    if [[ -f "${VENV_PATH}/bin/activate" ]]; then
        source "${VENV_PATH}/bin/activate" 2>/dev/null
        if python --version &>/dev/null; then
            log_success "✓ Virtual environment functional"
        else
            log_error "✗ Virtual environment activation failed"
            validation_passed=false
        fi
    else
        log_error "✗ Virtual environment not found"
        validation_passed=false
    fi

    # Check PyTorch
    log_info "Validating PyTorch with CUDA support..."
    if python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
        local gpu_name=$(python -c "import torch; print(torch.cuda.get_device_name(0))" 2>/dev/null)
        log_success "✓ PyTorch with CUDA support verified (GPU: ${gpu_name})"
    else
        log_error "✗ PyTorch CUDA validation failed"
        validation_passed=false
    fi

    # Check vLLM
    log_info "Validating vLLM installation..."
    if python -c "from vllm import LLM" 2>/dev/null; then
        log_success "✓ vLLM installation verified"
    else
        log_error "✗ vLLM validation failed"
        validation_passed=false
    fi

    # Check SQLite
    log_info "Validating SQLite..."
    if command -v sqlite3 &> /dev/null && sqlite3 --version &>/dev/null; then
        log_success "✓ SQLite installed and functional"
    else
        log_error "✗ SQLite validation failed"
        validation_passed=false
    fi

    # Check Python packages
    log_info "Validating critical Python packages..."
    if python -c "import fastapi, sqlalchemy, alembic, prometheus_client" 2>/dev/null; then
        log_success "✓ All critical Python packages installed"
    else
        log_error "✗ Python package validation failed"
        validation_passed=false
    fi

    # Check directory structure
    log_info "Validating directory structure..."
    local dirs_ok=true
    for dir in models configs logs data scripts backups; do
        if [[ ! -d "${APP_BASE_DIR}/${dir}" ]]; then
            log_error "✗ Missing directory: ${dir}"
            dirs_ok=false
        fi
    done
    if [[ "${dirs_ok}" == "true" ]]; then
        log_success "✓ Directory structure complete"
    else
        validation_passed=false
    fi

    # Check service files
    log_info "Validating systemd service templates..."
    if [[ -f /etc/systemd/system/sovereign-assistant-vllm.service ]]; then
        log_success "✓ vLLM systemd service template created"
    else
        log_error "✗ vLLM service template missing"
        validation_passed=false
    fi

    # Check configuration files
    log_info "Validating configuration files..."
    local configs_ok=true
    for config in vllm_config.yml app_config.yml logging_config.yml; do
        if [[ ! -f "${APP_BASE_DIR}/configs/${config}" ]]; then
            log_error "✗ Missing configuration: ${config}"
            configs_ok=false
        fi
    done
    if [[ "${configs_ok}" == "true" ]]; then
        log_success "✓ All configuration files created"
    else
        validation_passed=false
    fi

    # Final result
    if [[ "${validation_passed}" == "true" ]]; then
        log_success "✓✓✓ All validation checks PASSED ✓✓✓"
        return 0
    else
        log_error "✗✗✗ Some validation checks FAILED ✗✗✗"
        return 1
    fi
}

################################################################################
# Print Summary and Next Steps
################################################################################

print_completion_summary() {
    cat << EOF | tee -a "${LOG_FILE}"

$(echo -e "${GREEN}")
╔════════════════════════════════════════════════════════════════════════════╗
║                 ENVIRONMENT SETUP COMPLETED SUCCESSFULLY                   ║
╚════════════════════════════════════════════════════════════════════════════╝
$(echo -e "${NC}")

Installation Summary:
═════════════════════════════════════════════════════════════════════════════

Application Base Directory:   ${APP_BASE_DIR}
Python Virtual Environment:   ${VENV_PATH}
Service User:                 ${APP_USER}:${APP_GROUP}
Log Directory:                ${LOG_DIR}
Setup Log File:               ${LOG_FILE}

Installed Components:
───────────────────────────────────────────────────────────────────────────
✓ Ubuntu 24.04 LTS with essential build tools
✓ NVIDIA CUDA Toolkit 12.4 with GPU support
✓ Python 3.11 with isolated virtual environment
✓ PyTorch with CUDA acceleration
✓ vLLM inference server framework
✓ SQLite 3.x database engine
✓ FastAPI, Uvicorn, SQLAlchemy, Alembic
✓ Prometheus metrics client
✓ Complete testing and development tools

Configuration & Infrastructure:
───────────────────────────────────────────────────────────────────────────
✓ Complete directory structure under ${APP_BASE_DIR}/
✓ Configuration files (placeholder values ready for customization)
✓ Systemd service templates for vLLM and API server
✓ Logging infrastructure with log rotation
✓ Service user with proper permissions (uid=$(id -u ${APP_USER}))

Next Steps - Phase 1 Step 2: Model Download
═════════════════════════════════════════════════════════════════════════════

The environment is ready for model download. Proceed with:

1. Download Llama 3.1 70B AWQ model to: ${APP_BASE_DIR}/models/
   - Model size: ~40GB (ensure sufficient disk space)
   - Expected download time: 30-60 minutes depending on bandwidth
   - Source: HuggingFace Hub (meta-llama/Llama-3.1-70B-Instruct-AWQ)

2. Verify model integrity after download

3. Proceed to Phase 1 Step 3: vLLM Configuration
   - Customize vLLM settings in: ${APP_BASE_DIR}/configs/vllm_config.yml
   - Adjust batch size, VRAM utilization, context limits as needed

4. Phase 1 Step 4: Service Configuration
   - Update systemd service with actual model path
   - Start vLLM service: systemctl start sovereign-assistant-vllm

Environment Verification Commands:
═════════════════════════════════════════════════════════════════════════════

# Verify CUDA
nvidia-smi
nvcc --version

# Activate virtual environment
source ${VENV_PATH}/bin/activate

# Verify Python and packages
python --version
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
python -c "from vllm import LLM; print('vLLM ready')"

# Check directory structure
ls -la ${APP_BASE_DIR}/

# View setup logs
tail -f ${LOG_FILE}

# Check service status
systemctl status sovereign-assistant-vllm.service

Important Notes:
═════════════════════════════════════════════════════════════════════════════

1. The vLLM service is ENABLED but NOT STARTED yet
   - Do not start until model is downloaded in Phase 1 Step 2
   - Do not start until configuration is finalized in Phase 1 Step 3

2. All configuration files contain placeholder values
   - These MUST be customized before service startup
   - Review and update: ${APP_BASE_DIR}/configs/*.yml

3. GPU Memory:
   - Current A6000: 48GB total VRAM
   - Model weights: 35-40GB
   - KV cache reserve: 4-10GB
   - Server overhead: 1-2GB
   - Configured headroom: 90% utilization limit

4. Logging:
   - Setup logs: ${LOG_FILE}
   - Application logs: ${LOG_DIR}/app.log
   - Service logs: journalctl -u sovereign-assistant-vllm.service -f

5. Security:
   - Service runs as: ${APP_USER} (non-root)
   - Directory permissions: 750 (owner rwx, group rx, others none)
   - File permissions: 640 (owner rw, group r, others none)

Support & Documentation:
═════════════════════════════════════════════════════════════════════════════

For troubleshooting and next steps, refer to:
- Architectural decisions: architectural_decisions.md
- Phase 1 implementation plan
- System logs: journalctl -u sovereign-assistant-* -f

Setup completed at: $(date)
═════════════════════════════════════════════════════════════════════════════

EOF
}

################################################################################
# Main Execution Flow
################################################################################

main() {
    print_section "Sovereign Assistant API - Environment Setup"

    # Create log directory first
    mkdir -p "${LOG_DIR}"

    log_info "Setup script started at $(date)"
    log_info "Log file: ${LOG_FILE}"

    # Handle --clean option
    if [[ "${1:-}" == "--clean" ]]; then
        log_warning "Removing existing installation for clean start..."
        CLEANUP_ON_EXIT=true
        rm -rf "${APP_BASE_DIR}" 2>/dev/null || true
        rm -f /etc/systemd/system/sovereign-assistant-*.service
        systemctl daemon-reload 2>/dev/null || true
        log_info "Clean start initiated"
    fi

    # Verify we have internet connectivity and can proceed
    if [[ ! -f /.dockerenv ]] && [[ ! -f /run/.containerenv ]]; then
        check_prerequisites
    else
        log_warning "Running in container environment - skipping some prerequisite checks"
    fi

    update_system
    install_cuda
    setup_python_environment
    install_pytorch_and_vllm
    create_directory_structure
    create_service_user
    install_python_packages
    generate_configuration_files
    generate_systemd_service
    install_and_verify_sqlite
    setup_logging_infrastructure

    # Run validation
    if validate_installation; then
        print_completion_summary
        log_success "Environment setup completed successfully"
        SCRIPT_EXIT_CODE=0
    else
        log_error "Environment setup completed with validation errors"
        log_error "Review the log file for details: ${LOG_FILE}"
        SCRIPT_EXIT_CODE=1
    fi

    return ${SCRIPT_EXIT_CODE}
}

# Run main function
main "$@"
exit $?
