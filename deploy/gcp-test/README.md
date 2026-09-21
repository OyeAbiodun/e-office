# OfficeFlow minimal GCP test deployment

This profile runs the complete OfficeFlow application on the existing `officeflow` e2-micro
VM. It is a temporary functional-test configuration, not a production deployment. It keeps all
business modules enabled and changes only process count, connection pools, cache/database tuning,
and network exposure.

The only host port is `127.0.0.1:8080`. PostgreSQL, Redis, and FastAPI are never bound to a
public interface. A tester reaches the gateway through an authenticated SSH tunnel, so credentials
and application data traverse SSH rather than public HTTP. Because the browser origin is HTTP on
the tester's own loopback interface, this profile deliberately uses `MEETINGHQ_ENVIRONMENT=test`
and non-`Secure` cookies. Do not expose port 8080 in a GCP firewall rule and do not change the
Compose binding to `0.0.0.0`.

## Capacity decision

The stack is feasible for one or two low-concurrency functional testers, provided the VM begins
with about 5.3 GB free and the preflight below passes. It is not suitable for load testing,
production traffic, large report batches, or substantial attachment retention.

Expected clean-install footprint (estimates until the images are built and measured):

| Item | Transfer/compressed | Unpacked or initial disk | Runtime memory target |
| --- | ---: | ---: | ---: |
| OfficeFlow API image | 140-250 MB | 400-700 MB | 120-320 MB |
| OfficeFlow web image | 15-35 MB | 40-80 MB | 8-32 MB |
| PostgreSQL 17 Alpine | 90-130 MB | 250-400 MB | 70-180 MB |
| Redis 8 Alpine | 15-25 MB | 40-70 MB | 15-64 MB |
| Nginx Alpine | 20-30 MB | 50-80 MB | 5-32 MB |
| Image extraction and metadata headroom | n/a | 0.8-1.2 GB temporary | n/a |
| New PostgreSQL cluster | n/a | 50-150 MB, then data growth | included above |
| Redis AOF | n/a | usually under 50 MB; workload-dependent | included above |
| Attachments/reports/outbox | n/a | starts near zero; workload-dependent | API/worker |

Allow approximately 2.5 GB for pulled/loaded images plus extraction headroom and keep at least
1.0 GB free after startup for PostgreSQL, uploads, generated reports, logs, and Docker metadata.
The service memory limits total 848 MB; Debian and Docker use the remaining physical memory, while
the existing 1 GB swap absorbs short peaks. Sustained swapping, OOM kills, less than 1 GB remaining
disk, or concurrent report/payroll-heavy use means the VM is not reliable. The smallest practical
adjustment is first to remove unused Docker data and test artifacts or shorten the test-data
retention window. Only if those measures fail should the test move to a VM with roughly 2 GB RAM
or a larger boot disk; no upgrade is required merely to try this bounded profile.

After building, replace estimates with measurements:

```powershell
docker image inspect "officeflow-api:$commit" "officeflow-web:$commit" `
  --format '{{.RepoTags}} {{.Size}}'
docker save -o officeflow-images-$commit.tar "officeflow-api:$commit" "officeflow-web:$commit"
Get-Item "officeflow-images-$commit.tar" | Select-Object Name,Length
```

On the VM, measure the actual unpacked footprint and live memory:

```bash
docker system df -v
docker compose --env-file .env -f compose.yaml ps --format json
docker stats --no-stream
sudo du -sh /var/lib/docker
docker run --rm -v officeflow_test_postgres_data:/data alpine:3.22 du -sh /data
docker run --rm -v officeflow_test_app_storage:/data alpine:3.22 du -sh /data
```

## 1. Build outside the VM

Run this on the Windows development workstation from the repository root. The web bundle uses a
same-origin API path, which also makes WebSockets traverse the gateway.

```powershell
git switch --show-current
$commit = git rev-parse HEAD
git status --short
docker build --pull -f apps/api/Dockerfile -t "officeflow-api:$commit" .
docker build --pull --build-arg VITE_API_URL=/api/v1 -f apps/web/Dockerfile -t "officeflow-web:$commit" .
docker save -o "officeflow-images-$commit.tar" "officeflow-api:$commit" "officeflow-web:$commit"
```

The workstation needs Docker for these commands. This repository does not build application
images on the e2-micro. The commit tag is immutable by convention; record image IDs from
`docker image inspect` before transfer.

For this one-VM test, direct transfer avoids Artifact Registry cost and setup:

```powershell
scp "officeflow-images-$commit.tar" GCP_USER@34.45.126.228:/tmp/
scp -r deploy/gcp-test GCP_USER@34.45.126.228:/tmp/officeflow-deploy
```

An already-authorized private registry is also acceptable: tag both images with its repository
plus the same commit SHA, push them, set the two image variables accordingly, and run
`docker compose pull`. Never use `latest`.

## 2. Prepare Debian and deployment files

No extra cloud resource or inbound firewall rule is needed. Verify the existing installation and
disk before loading images:

```bash
ssh GCP_USER@34.45.126.228
docker version
docker compose version
free -h
df -h / /var/lib/docker
sudo install -d -m 0750 -o "$USER" -g "$USER" /opt/officeflow-test
sudo cp /tmp/officeflow-deploy/compose.yaml /opt/officeflow-test/
sudo cp /tmp/officeflow-deploy/nginx.conf /opt/officeflow-test/
sudo cp /tmp/officeflow-deploy/.env.example /opt/officeflow-test/
cd /opt/officeflow-test
cp .env.example .env
chmod 600 .env
```

Require at least 3 GB free before loading the application archive. If that check fails, inspect
`docker system df -v` and remove only identified, unused artifacts; do not delete named volumes.

Load the prebuilt application images, then remove only the transferred archive:

```bash
docker load -i /tmp/officeflow-images-COMMIT_SHA.tar
rm /tmp/officeflow-images-COMMIT_SHA.tar
docker image inspect officeflow-api:COMMIT_SHA officeflow-web:COMMIT_SHA \
  --format '{{.RepoTags}} id={{.Id}} bytes={{.Size}}'
```

Edit `.env` and replace every `CHANGE_ME` value. Generate independent secrets on the VM without
printing them into shell history:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(36))'
python3 -c 'import secrets; print(secrets.token_hex(32))'
nano .env
grep -n 'CHANGE_ME' .env && echo 'STOP: unresolved values remain' || true
```

Use the first output for the database password and the second for the JWT secret. Use a new,
synthetic administrator identity and a unique temporary password. Never copy real employee,
payroll, Finance, Leave, or attachment data to this server. The database name, credentials,
volumes, network, and Compose project are isolated from local development and Office Platform.

Validate interpolation before changing state. This command must not display unresolved variables:

```bash
docker compose --env-file .env -f compose.yaml config --quiet
```

## 3. Create storage, start dependencies, and migrate

Named volumes preserve the PostgreSQL cluster, Redis AOF, attachments, generated reports, and
local email outbox across container replacement. Audit, Finance, Payroll, Leave, and migration
history live in PostgreSQL.

```bash
docker volume create officeflow_test_postgres_data
docker volume create officeflow_test_redis_data
docker volume create officeflow_test_app_storage
docker compose --env-file .env -f compose.yaml up -d postgres redis
docker compose --env-file .env -f compose.yaml ps
docker compose --env-file .env -f compose.yaml --profile tools run --rm migrate
docker compose --env-file .env -f compose.yaml --profile tools run --rm migrate \
  alembic current
```

Migrations are a single explicit job. Neither the API nor worker applies migrations, preventing
concurrent schema changes. A failed migration must be investigated before the API starts; do not
automatically downgrade financial schemas.

## 4. Start API, create the administrator, worker, and web

The permanent first-install bootstrap runs during the first successful API startup. It uses the
`INITIAL_*` values only when no Organization exists, creates the initial tenant/workspace and Super
Admin, and synchronizes the permission catalog.

```bash
docker compose --env-file .env -f compose.yaml up -d api
docker compose --env-file .env -f compose.yaml logs --tail=100 api
docker compose --env-file .env -f compose.yaml up -d worker web gateway
docker compose --env-file .env -f compose.yaml ps
curl --fail --silent http://127.0.0.1:8080/api/v1/health
curl --fail --silent http://127.0.0.1:8080/api/v1/ready
curl --fail --silent --output /dev/null http://127.0.0.1:8080/
docker stats --no-stream
df -h / /var/lib/docker
```

The API has exactly one Uvicorn worker. Its embedded scheduler is disabled. The dedicated worker
runs one bounded, idempotent database-claiming pass at a time, sleeps 30 seconds, and never overlaps
itself. Redis is private, AOF-backed, capped at 48 MB, and uses `noeviction` so rate-limit and job
state are not silently discarded. Containers retain outbound access for configured SMTP, calendar,
and notification providers, while unneeded host port publishing remains disabled. Docker uses its
bounded `local` log driver (three 10 MB files per service) to protect the small boot disk.

After the initial login succeeds, change the temporary administrator password in OfficeFlow. The
bootstrap value remains in the root-readable `.env` because container configuration validates it,
but it is never reapplied once an Organization exists and becomes invalid after that password
change. Do not reuse it anywhere else.

## 5. Secure access

Give the Product Owner an individual, key-only SSH account authorized for this VM. From their
computer, keep this terminal open:

```bash
ssh -N -L 8080:127.0.0.1:8080 GCP_USER@34.45.126.228
```

They then open `http://localhost:8080`. Despite the browser's loopback HTTP URL, traffic between
their computer and the VM is encrypted and authenticated by SSH. Never browse directly to
`http://34.45.126.228`, never open TCP 8080 in the GCP firewall, and never share a private key.
If multiple testers are required, give each a separate OS account and SSH key.

This SSH method is selected over an unauthenticated temporary public hostname. When a real domain
is available, terminate trusted HTTPS, change the environment to `staging`, enable secure cookies,
and use explicit HTTPS origins; that is outside this temporary profile.

## 6. Diagnose, back up, and stop

```bash
cd /opt/officeflow-test
docker compose --env-file .env -f compose.yaml ps
docker compose --env-file .env -f compose.yaml logs --tail=200 postgres redis api worker web gateway
docker inspect --format '{{.Name}} OOMKilled={{.State.OOMKilled}} Exit={{.State.ExitCode}}' \
  $(docker compose --env-file .env -f compose.yaml ps -q)
docker system df -v
docker stats --no-stream
docker compose --env-file .env -f compose.yaml exec postgres \
  sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose --env-file .env -f compose.yaml exec redis redis-cli ping
```

Because `.env` values are not automatically exported to the interactive shell, source them only
for a controlled backup command and immediately unset them:

```bash
set -a
. ./.env
set +a
umask 077
docker compose --env-file .env -f compose.yaml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "officeflow-test-$(date +%F).dump"
unset POSTGRES_PASSWORD MEETINGHQ_JWT_SECRET INITIAL_SUPER_ADMIN_PASSWORD
```

Store any backup in an approved encrypted location, then remove the VM copy. A database dump does
not include `officeflow_test_app_storage`; attachments and generated reports require a separate,
consistent volume backup.

Stop application processes while preserving all named volumes:

```bash
docker compose --env-file .env -f compose.yaml stop
```

`stop` preserves data but does not stop GCE billing. If the whole test VM may be stopped, an
authorized operator can run this from a configured Google Cloud workstation after confirming the
zone and project:

```bash
gcloud compute instances stop officeflow --zone=us-central1-c
```

Do not run `docker compose down -v`; `-v` deletes the persistent database, Redis, attachments, and
reports. Before each later test session, start the VM, then use `docker compose ... start` and repeat
the health checks.
