# Docker Quick Notes (This Project)

This project uses a custom image named `rag-chainlit` built from `python:3.12-slim`.

## Mental model

- `python:3.12-slim` is the base image.
- `rag-chainlit:latest` is your project image layered on top of that base.
- A **container** is a running (or stopped) instance of an image.

## Build

```bash
docker build -f Dockerfile.chainlit -t rag-chainlit .
```

## Inspect what you have

```bash
# Images
docker images

# Running containers
docker ps

# All containers (running + stopped)
docker ps -a
```

## Run Chainlit

```bash
docker run --rm -it \
  -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=qwen3:14b \
  -e SMASH_API_BASE_URL=https://server.cetacean-tuna.ts.net \
  --name rag-chainlit \
  rag-chainlit
```

- Open `http://localhost:8000`.
- `--rm` auto-deletes the container when it exits.

## Useful container commands

```bash
# Logs
docker logs rag-chainlit

# Follow logs live
docker logs -f rag-chainlit

# Enter shell in running container
docker exec -it rag-chainlit sh

# Stop container
docker stop rag-chainlit
```

## Cleanup

```bash
# Remove stopped containers
docker container prune

# Remove dangling/unused images
docker image prune -a
```

## Common issue

If build/run says it cannot connect to `/var/run/docker.sock`, start Docker daemon:

```bash
sudo systemctl start docker
sudo systemctl enable docker
```
