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

On startup the UI shows two buttons — **API Agent** and **SQL Agent**.
Pick which mode you want before chatting.

### API Agent only (no database needed)

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

### With SQL Agent (requires database mount)

```bash
docker run --rm -it \
  -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -e OLLAMA_MODEL=qwen3:14b \
  -e SMASH_API_BASE_URL=https://server.cetacean-tuna.ts.net \
  -e SMASH_DB_PATH=/data/smash.db \
  -v ~/code-repos/smashDA/.cache/startgg/smash.db:/data/smash.db:ro \
  --name rag-chainlit \
  rag-chainlit
```

- `-v ...smash.db:/data/smash.db:ro` mounts the SQLite database read-only into the container.
- `-e SMASH_DB_PATH=/data/smash.db` tells the SQL agent where to find it inside the container.
- Without the volume mount, choosing "SQL Agent" will fail.

### Common options

- Open `http://localhost:8000`.
- `--rm` auto-deletes the container when it exits.
- Change model with `-e OLLAMA_MODEL=qwen3:8b` (or any Ollama model tag).

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

## Troubleshooting `Connection refused`

If Chainlit UI opens but replies with `Agent error: [Errno 111] Connection refused`,
the container usually cannot reach Ollama.

### 1) Verify Ollama on host

```bash
curl -sS http://localhost:11434/api/tags
```

If this fails, Ollama is not running on host.

### 2) Verify container -> host Ollama path

```bash
docker run --rm --add-host=host.docker.internal:host-gateway \
  python:3.12-slim python - <<'PY'
import urllib.request
print(urllib.request.urlopen("http://host.docker.internal:11434/api/tags", timeout=3).read()[:200])
PY
```

If this fails, host Ollama is likely bound only to loopback and not reachable from Docker bridge.

### 3) Linux fallback (recommended if step 2 fails)

Run container with host networking and point Ollama to localhost:

```bash
docker run --rm -it \
  --network host \
  -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  -e OLLAMA_MODEL=qwen3:14b \
  -e SMASH_API_BASE_URL=https://server.cetacean-tuna.ts.net \
  -e SMASH_DB_PATH=/data/smash.db \
  -v ~/code-repos/smashDA/.cache/startgg/smash.db:/data/smash.db:ro \
  --name rag-chainlit \
  rag-chainlit
```

Then open `http://localhost:8000`.
