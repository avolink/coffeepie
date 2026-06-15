# Docker Deployment Guide for CoffeePie

This guide explains how to build and run the CoffeePie Qt6 application in Docker with X11 display support.

## Prerequisites

### Linux
- Docker and Docker Compose installed
- X11 server running (typically default on Linux desktops)
- External service accessible at `http://127.0.0.1:8000` or update the URL in the Python backend

### macOS
- Docker Desktop with X11 forwarding support (e.g., XQuartz + socat)
- Run XQuartz: `open -a XQuartz`
- Forward X11: `socat TCP-LISTEN:6000,reuseaddr,fork UNIX-CONNECT:/tmp/.X11-unix/0 &`

### Windows
- Docker for Windows with WSL 2 backend (displays may not work well)
- Consider running headless or use a remote display server

## Building the Docker Image

### Option 1: Build with Docker Compose (Recommended)

```bash
cd /path/to/CoffeePie
docker-compose build
```

### Option 2: Build with Docker CLI

```bash
cd /path/to/CoffeePie
docker build -t coffeepie:latest .
```

## Running the Application

### Option 1: Run with Docker Compose (Linux/macOS)

```bash
# First, allow X11 connections from Docker
xhost +local:docker

# Start the application
docker-compose up

# To stop
docker-compose down
```

### Option 2: Run with Docker CLI

**For Linux:**
```bash
# Allow X11 connections
xhost +local:docker

# Run the container with X11 forwarding
docker run -it --rm \
  --env DISPLAY=$DISPLAY \
  --volume /tmp/.X11-unix:/tmp/.X11-unix:rw \
  --volume /etc/localtime:/etc/localtime:ro \
  --ipc=host \
  coffeepie:latest
```

**For macOS with XQuartz:**
```bash
docker run -it --rm \
  --env DISPLAY=host.docker.internal:0 \
  --volume /tmp/.X11-unix:/tmp/.X11-unix:rw \
  coffeepie:latest
```

### Option 3: Run Headless (No Display)

```bash
docker run -it --rm \
  --env QT_QPA_PLATFORM=offscreen \
  coffeepie:latest
```

## Connecting to External Services

The application connects to an external backend service at `http://127.0.0.1:8000`. 

### To use a different backend URL:

**Option A:** Modify `CoffeePieContent/python/main.py`
```python
BASE_URL = "http://your-backend-service:8000"
```
Then rebuild the image.

**Option B:** Mount a modified main.py when running:
```bash
docker run -it --rm \
  --env DISPLAY=$DISPLAY \
  --volume /tmp/.X11-unix:/tmp/.X11-unix:rw \
  --volume $(pwd)/CoffeePieContent/python/main.py:/app/python/main.py:ro \
  coffeepie:latest
```

**Option C:** Use docker-compose with environment variables (requires updating the code):
Edit `docker-compose.yml` and add environment variables, then modify main.py to use them.

## Docker Compose Advanced Configuration

### Adding a Backend Service

If you want to include the backend service in docker-compose (currently commented out):

```yaml
services:
  backend:
    image: your-backend-image:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/coffeepie
  
  coffeepie:
    # ... existing config
    depends_on:
      - backend
    links:
      - backend
```

### Enable Audio Support

Uncomment the devices section in `docker-compose.yml`:
```yaml
devices:
  - /dev/snd:/dev/snd
```

### Mount Configuration Directory

```yaml
volumes:
  - /tmp/.X11-unix:/tmp/.X11-unix:rw
  - ${HOME}/.config:/root/.config  # For persistent settings
```

## Troubleshooting

### Display connection failed
```
Error: Could not connect to display
```
**Solution:** Run `xhost +local:docker` before starting the container on Linux

### Qt plugin not found
```
Could not find the Qt platform plugin
```
**Solution:** The Dockerfile sets up the correct paths. Rebuild the image: `docker-compose build --no-cache`

### Permission denied on X11 socket
```
Permission denied while trying to connect to X Server
```
**Solution:** Add execute permission: `chmod 777 /tmp/.X11-unix`

### Network connection to backend fails
```
Connection refused: http://127.0.0.1:8000
```
**Solution:** Update the backend URL in code or use docker-compose to link services

### Application crashes
Check logs:
```bash
docker-compose logs -f coffeepie
# or
docker logs -f coffeepie-app
```

## Verifying the Build

To verify the Docker image was built correctly:

```bash
# List images
docker images | grep coffeepie

# Inspect image layers
docker history coffeepie:latest

# Test the image with a simple command
docker run --rm coffeepie:latest /bin/sh -c "echo 'Docker build successful!'"
```

## Performance Optimization

For better performance, use a smaller base image or multi-stage build:

- Current Dockerfile already uses multi-stage build (builder + runtime)
- Runtime image is ~800MB
- To reduce further, consider replacing Ubuntu with Alpine (requires Qt6 compilation)

## Security Considerations

- The Dockerfile builds from source, so all dependencies are verified
- For production, consider:
  - Using official Qt Docker base images
  - Signing the Docker image
  - Scanning for vulnerabilities with `docker scan coffeepie:latest`
  - Running as non-root user (update Dockerfile)
  - Using private registries for storing images

## Next Steps

1. Customize `docker-compose.yml` for your specific needs
2. Update the backend URL if using a different service
3. Test with `docker-compose up`
4. For CI/CD integration, consider adding `.github/workflows/docker.yml`

## Additional Resources

- [Qt6 Docker Documentation](https://doc.qt.io/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [X11 Forwarding with Docker](https://github.com/moby/moby/issues/8396)
