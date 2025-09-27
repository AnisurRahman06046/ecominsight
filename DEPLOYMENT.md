# Deployment Guide

Complete deployment guide for the E-Commerce Insights Server in various environments.

## 🚀 Quick Deployment Options

### Local Development
- **Setup Time**: 5-10 minutes
- **Requirements**: Python 3.9+, MongoDB, Ollama
- **Use Case**: Development and testing

### Docker Compose
- **Setup Time**: 10-15 minutes
- **Requirements**: Docker, Docker Compose
- **Use Case**: Local production testing

### Kubernetes
- **Setup Time**: 30-60 minutes
- **Requirements**: K8s cluster, kubectl
- **Use Case**: Scalable production deployment

### Cloud Deployment
- **Setup Time**: 20-30 minutes
- **Requirements**: Cloud provider account
- **Use Case**: Managed production environment

## 📋 Prerequisites

### System Requirements

#### Minimum (Development)
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 20GB SSD
- **Network**: 100 Mbps

#### Recommended (Production)
- **CPU**: 8+ cores
- **RAM**: 16GB+
- **Storage**: 100GB+ SSD
- **Network**: 1 Gbps

#### Optimal (High Performance)
- **CPU**: 16+ cores
- **RAM**: 32GB+
- **Storage**: 500GB+ NVMe SSD
- **Network**: 10 Gbps
- **GPU**: Optional for faster inference

### Software Dependencies

```bash
# Core Requirements
Python 3.9+
MongoDB 5.0+
Redis 6.0+ (optional)

# AI/ML Requirements
Ollama with mistral:7b-instruct
HuggingFace Transformers
PyTorch (CPU/GPU)

# Development Tools
Git
Docker (optional)
kubectl (for K8s)
```

## 🏗️ Local Development Setup

### Step 1: Environment Preparation

```bash
# Clone repository
git clone https://github.com/yourorg/ecom-insights-server.git
cd ecom-insights-server

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Database Setup

#### MongoDB Installation
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y mongodb

# macOS
brew install mongodb/brew/mongodb-community

# Start MongoDB
sudo systemctl start mongod  # Linux
brew services start mongodb/brew/mongodb-community  # macOS
```

#### Redis Installation (Optional)
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS
brew install redis

# Start Redis
sudo systemctl start redis  # Linux
brew services start redis   # macOS
```

### Step 3: Ollama Setup

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull required model (7GB download)
ollama pull mistral:7b-instruct

# Verify installation
ollama list
```

### Step 4: Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

**Environment Configuration**:
```env
# Database
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=ecommerce_insights

# Ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=mistral:7b-instruct
OLLAMA_TIMEOUT=120

# Cache (Optional)
REDIS_URL=redis://localhost:6379
ENABLE_CACHE=true
CACHE_TTL=3600

# Performance
MAX_QUERY_TIMEOUT=30
USE_TEMPLATE_FIRST=true
USE_RAG_FOR_ANALYTICS=true

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

### Step 5: Launch Application

```bash
# Start the server
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload

# Verify installation
curl http://localhost:8000/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "ollama": "available",
    "cache": "connected",
    "formatter": "initialized"
  }
}
```

### Step 6: Test Deployment

```bash
# Test basic query
curl -X POST "http://localhost:8000/api/ask" \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "10", "question": "How many orders do I have?"}'
```

## 🐳 Docker Deployment

### Docker Setup

#### 1. Create Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 2. Create Docker Compose

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - MONGODB_URL=mongodb://mongo:27017
      - REDIS_URL=redis://redis:6379
      - OLLAMA_HOST=http://ollama:11434
    depends_on:
      - mongo
      - redis
      - ollama
    restart: unless-stopped
    volumes:
      - ./logs:/app/logs

  mongo:
    image: mongo:5
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
      - ./mongo-init:/docker-entrypoint-initdb.d
    restart: unless-stopped
    environment:
      MONGO_INITDB_DATABASE: ecommerce_insights

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped
    environment:
      - OLLAMA_HOST=0.0.0.0

volumes:
  mongo_data:
  redis_data:
  ollama_data:

networks:
  default:
    driver: bridge
```

#### 3. Deploy with Docker Compose

```bash
# Build and start services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f app

# Pull Ollama model
docker-compose exec ollama ollama pull mistral:7b-instruct

# Test deployment
curl http://localhost:8000/health
```

#### 4. Production Docker Optimizations

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.prod
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
    environment:
      - WORKERS=4
      - LOG_LEVEL=WARNING
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped
```

## ☸️ Kubernetes Deployment

### 1. Namespace and ConfigMap

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ecom-insights

---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: ecom-insights
data:
  MONGODB_URL: "mongodb://mongo-service:27017"
  REDIS_URL: "redis://redis-service:6379"
  OLLAMA_HOST: "http://ollama-service:11434"
  LOG_LEVEL: "INFO"
  MAX_QUERY_TIMEOUT: "30"
  ENABLE_CACHE: "true"
```

### 2. Secrets

```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
  namespace: ecom-insights
type: Opaque
data:
  # Base64 encoded values
  mongodb-password: <base64-encoded-password>
  redis-password: <base64-encoded-password>
```

### 3. Application Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ecom-insights-app
  namespace: ecom-insights
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ecom-insights
  template:
    metadata:
      labels:
        app: ecom-insights
    spec:
      containers:
      - name: app
        image: ecom-insights:latest
        ports:
        - containerPort: 8000
        env:
        - name: WORKERS
          value: "4"
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
        resources:
          requests:
            memory: "2Gi"
            cpu: "1"
          limits:
            memory: "4Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: ecom-insights-service
  namespace: ecom-insights
spec:
  selector:
    app: ecom-insights
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

### 4. Database Services

```yaml
# mongodb.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: mongodb
  namespace: ecom-insights
spec:
  serviceName: mongo-service
  replicas: 1
  selector:
    matchLabels:
      app: mongodb
  template:
    metadata:
      labels:
        app: mongodb
    spec:
      containers:
      - name: mongodb
        image: mongo:5
        ports:
        - containerPort: 27017
        volumeMounts:
        - name: mongo-data
          mountPath: /data/db
        env:
        - name: MONGO_INITDB_DATABASE
          value: "ecommerce_insights"
  volumeClaimTemplates:
  - metadata:
      name: mongo-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 100Gi

---
apiVersion: v1
kind: Service
metadata:
  name: mongo-service
  namespace: ecom-insights
spec:
  selector:
    app: mongodb
  ports:
  - port: 27017
    targetPort: 27017
```

### 5. Load Balancer and Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ecom-insights-ingress
  namespace: ecom-insights
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "120"
spec:
  tls:
  - hosts:
    - api.yourcompany.com
    secretName: ecom-insights-tls
  rules:
  - host: api.yourcompany.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: ecom-insights-service
            port:
              number: 80
```

### 6. Horizontal Pod Autoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ecom-insights-hpa
  namespace: ecom-insights
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ecom-insights-app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### 7. Deploy to Kubernetes

```bash
# Apply all configurations
kubectl apply -f namespace.yaml
kubectl apply -f configmap.yaml
kubectl apply -f secrets.yaml
kubectl apply -f deployment.yaml
kubectl apply -f mongodb.yaml
kubectl apply -f ingress.yaml
kubectl apply -f hpa.yaml

# Check deployment status
kubectl get pods -n ecom-insights
kubectl get services -n ecom-insights
kubectl get ingress -n ecom-insights

# View logs
kubectl logs -f deployment/ecom-insights-app -n ecom-insights

# Scale deployment
kubectl scale deployment ecom-insights-app --replicas=5 -n ecom-insights
```

## ☁️ Cloud Platform Deployments

### AWS Deployment

#### 1. Using AWS EKS

```bash
# Create EKS cluster
eksctl create cluster --name ecom-insights --region us-west-2 --nodegroup-name standard-workers --node-type t3.xlarge --nodes 3 --nodes-min 1 --nodes-max 10

# Configure kubectl
aws eks update-kubeconfig --region us-west-2 --name ecom-insights

# Deploy application
kubectl apply -f k8s/
```

#### 2. Using AWS ECS

```json
{
  "family": "ecom-insights",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "app",
      "image": "your-repo/ecom-insights:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "MONGODB_URL",
          "value": "mongodb://your-mongodb-cluster"
        }
      ],
      "healthCheck": {
        "command": [
          "CMD-SHELL",
          "curl -f http://localhost:8000/health || exit 1"
        ],
        "interval": 30,
        "timeout": 5,
        "retries": 3
      },
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/ecom-insights",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### Google Cloud Platform (GCP)

#### 1. Using GKE

```bash
# Create GKE cluster
gcloud container clusters create ecom-insights \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-4 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 10

# Get credentials
gcloud container clusters get-credentials ecom-insights --zone us-central1-a

# Deploy
kubectl apply -f k8s/
```

#### 2. Using Cloud Run

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ecom-insights
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/maxScale: "10"
        run.googleapis.com/cpu-throttling: "false"
        run.googleapis.com/memory: "4Gi"
        run.googleapis.com/cpu: "2"
    spec:
      containers:
      - image: gcr.io/project-id/ecom-insights:latest
        ports:
        - containerPort: 8000
        env:
        - name: MONGODB_URL
          value: "mongodb://mongodb-service"
        resources:
          limits:
            memory: "4Gi"
            cpu: "2"
```

### Microsoft Azure

#### 1. Using AKS

```bash
# Create resource group
az group create --name ecom-insights --location eastus

# Create AKS cluster
az aks create \
  --resource-group ecom-insights \
  --name ecom-insights-cluster \
  --node-count 3 \
  --node-vm-size Standard_D4s_v3 \
  --enable-addons monitoring \
  --generate-ssh-keys

# Get credentials
az aks get-credentials --resource-group ecom-insights --name ecom-insights-cluster

# Deploy
kubectl apply -f k8s/
```

#### 2. Using Container Instances

```bash
# Create container instance
az container create \
  --resource-group ecom-insights \
  --name ecom-insights-app \
  --image your-registry/ecom-insights:latest \
  --cpu 2 \
  --memory 4 \
  --ports 8000 \
  --environment-variables \
    MONGODB_URL=mongodb://your-mongodb \
    LOG_LEVEL=INFO
```

## 📊 Monitoring and Observability

### 1. Application Monitoring

```yaml
# prometheus-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-config
data:
  prometheus.yml: |
    global:
      scrape_interval: 15s
    scrape_configs:
    - job_name: 'ecom-insights'
      static_configs:
      - targets: ['ecom-insights-service:80']
      metrics_path: '/metrics'
      scrape_interval: 5s
```

### 2. Logging Setup

```yaml
# fluentd-config.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluentd-config
data:
  fluent.conf: |
    <source>
      @type tail
      path /var/log/containers/*ecom-insights*.log
      pos_file /var/log/ecom-insights.log.pos
      tag kubernetes.ecom-insights
      format json
    </source>

    <match kubernetes.ecom-insights>
      @type elasticsearch
      host elasticsearch-service
      port 9200
      index_name ecom-insights
    </match>
```

### 3. Health Checks

```python
# Custom health check endpoint
@app.get("/health/detailed")
async def detailed_health():
    checks = {
        "database": await check_mongodb_connection(),
        "ollama": await check_ollama_service(),
        "cache": await check_redis_connection(),
        "disk_space": check_disk_usage(),
        "memory": check_memory_usage(),
        "cpu": check_cpu_usage()
    }

    status = "healthy" if all(checks.values()) else "unhealthy"

    return {
        "status": status,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }
```

## 🔧 Production Optimizations

### 1. Performance Tuning

```bash
# MongoDB optimization
db.order.createIndex({shop_id: 1, created_at: -1})
db.product.createIndex({shop_id: 1, status: 1})
db.customer.createIndex({shop_id: 1})

# Connection pooling
MONGODB_MAX_POOL_SIZE=50
MONGODB_MIN_POOL_SIZE=10

# Redis optimization
redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
```

### 2. Security Hardening

```python
# Add security middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api.yourcompany.com", "*.yourcompany.com"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourcompany.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### 3. Load Testing

```python
# load_test.py
import asyncio
import httpx
import time

async def load_test(concurrent_users=10, duration=60):
    async def user_session():
        async with httpx.AsyncClient() as client:
            end_time = time.time() + duration
            while time.time() < end_time:
                await client.post(
                    "http://localhost:8000/api/ask",
                    json={"shop_id": "10", "question": "How many orders?"}
                )
                await asyncio.sleep(1)

    tasks = [user_session() for _ in range(concurrent_users)]
    await asyncio.gather(*tasks)

# Run load test
asyncio.run(load_test(concurrent_users=50, duration=300))
```

## 🚨 Disaster Recovery

### 1. Backup Strategy

```bash
# MongoDB backup
mongodump --host localhost:27017 --db ecommerce_insights --out /backup/$(date +%Y%m%d)

# Redis backup
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb

# Application backup
tar -czf /backup/app-$(date +%Y%m%d).tar.gz /path/to/app
```

### 2. Recovery Procedures

```bash
# MongoDB restore
mongorestore --host localhost:27017 --db ecommerce_insights /backup/20250925/ecommerce_insights

# Redis restore
cp /backup/redis-20250925.rdb /var/lib/redis/dump.rdb
systemctl restart redis

# Application restore
tar -xzf /backup/app-20250925.tar.gz -C /path/to/restore
```

## 📋 Deployment Checklist

### Pre-Deployment
- [ ] System requirements verified
- [ ] Dependencies installed
- [ ] Configuration reviewed
- [ ] Secrets configured
- [ ] Database initialized
- [ ] AI models downloaded
- [ ] Network connectivity tested

### Deployment
- [ ] Application deployed
- [ ] Health checks passing
- [ ] Load balancer configured
- [ ] SSL certificates installed
- [ ] Monitoring enabled
- [ ] Logging configured
- [ ] Backups scheduled

### Post-Deployment
- [ ] Smoke tests executed
- [ ] Performance benchmarks run
- [ ] Security scans completed
- [ ] Documentation updated
- [ ] Team notified
- [ ] Rollback plan verified

This comprehensive deployment guide ensures reliable, scalable, and maintainable deployments across various environments and platforms.