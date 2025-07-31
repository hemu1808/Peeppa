# Deployment Guide

This guide covers deploying the Price Tracker application in different environments.

## Local Development

### Prerequisites
- Python 3.8+
- MongoDB
- Git

### Setup
1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate virtual environment
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `env.example` to `.env` and configure
6. Start MongoDB
7. Run the application: `python start.py`

## Production Deployment

### Using Docker (Recommended)

#### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Start application
CMD ["python", "start.py"]
```

#### Docker Compose
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - MONGO_URI=mongodb://mongo:27017
      - SECRET_KEY=your-production-secret-key
    depends_on:
      - mongo
    restart: unless-stopped

  mongo:
    image: mongo:5.0
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped

volumes:
  mongo_data:
```

### Using Gunicorn (WSGI Server)

1. Install Gunicorn: `pip install gunicorn`
2. Create `wsgi.py`:
```python
from app import app

if __name__ == "__main__":
    app.run()
```

3. Run with Gunicorn:
```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 --timeout 120 wsgi:app
```

### Environment Variables

#### Required for Production
```bash
SECRET_KEY=your-super-secure-secret-key
DEBUG=False
MONGO_URI=mongodb://your-mongo-host:27017
SMTP_SERVER=smtp.gmail.com
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

#### Optional
```bash
PORT=5000
ALERT_CHECK_INTERVAL=3600
ALERT_THRESHOLD_PERCENT=0.5
```

## Cloud Deployment

### Heroku

1. Create `Procfile`:
```
web: gunicorn wsgi:app
```

2. Add buildpacks:
```bash
heroku buildpacks:add heroku/python
heroku buildpacks:add heroku/mongodb
```

3. Set environment variables:
```bash
heroku config:set SECRET_KEY=your-secret-key
heroku config:set MONGO_URI=your-mongo-uri
```

### AWS EC2

1. Launch EC2 instance
2. Install dependencies:
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-venv mongodb
```

3. Clone and setup application
4. Use systemd service:
```ini
[Unit]
Description=Price Tracker
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/price-tracker
Environment=PATH=/home/ubuntu/price-tracker/venv/bin
ExecStart=/home/ubuntu/price-tracker/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:5000 wsgi:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### Google Cloud Platform

1. Create `app.yaml`:
```yaml
runtime: python39
entrypoint: gunicorn -b :$PORT wsgi:app

env_variables:
  SECRET_KEY: "your-secret-key"
  MONGO_URI: "your-mongo-uri"

automatic_scaling:
  target_cpu_utilization: 0.6
  min_instances: 1
  max_instances: 10
```

## Security Considerations

### Production Checklist
- [ ] Use strong, unique SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Use HTTPS in production
- [ ] Configure proper CORS settings
- [ ] Set up rate limiting
- [ ] Use environment variables for secrets
- [ ] Regular security updates
- [ ] Database access control
- [ ] Log monitoring and alerting

### Rate Limiting
Add rate limiting to prevent abuse:
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)
```

### CORS Configuration
```python
from flask_cors import CORS

CORS(app, origins=['https://yourdomain.com'])
```

## Monitoring and Logging

### Application Logs
- Use structured logging
- Rotate log files
- Monitor error rates

### Database Monitoring
- Monitor MongoDB performance
- Set up alerts for connection issues
- Regular backups

### Health Checks
```python
@app.route('/health')
def health_check():
    try:
        # Test database connection
        db.client.admin.command('ping')
        return jsonify({'status': 'healthy'}), 200
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500
```

## Backup Strategy

### Database Backups
```bash
# MongoDB backup
mongodump --uri="mongodb://localhost:27017" --out=/backup/$(date +%Y%m%d)

# Restore
mongorestore --uri="mongodb://localhost:27017" /backup/20240101/
```

### Application Backups
- Version control for code
- Configuration backups
- Environment variable backups

## Performance Optimization

### Database Optimization
- Create proper indexes
- Monitor query performance
- Use connection pooling

### Application Optimization
- Enable caching
- Optimize database queries
- Use CDN for static files

### Scaling Considerations
- Horizontal scaling with load balancer
- Database sharding for large datasets
- Caching layer (Redis)
- Message queues for background tasks 