# VM Deployment

This project is set up for a single Ubuntu/Debian VM running Docker Compose with:

- PostgreSQL
- Redis
- Django + Gunicorn
- Celery worker
- Celery beat
- Nginx
- Certbot

## 1. DNS

Point the domain to the VM external IP:

- `A` record for `@` -> `VM_EXTERNAL_IP`
- Optional: `CNAME` record for `www` -> `yourdomain.com`

## 2. GCP Firewall

Allow inbound HTTP and HTTPS:

```bash
gcloud compute firewall-rules create allow-http-https \
  --allow tcp:80,tcp:443 \
  --target-tags lms-backend

gcloud compute instances add-tags YOUR_VM_NAME \
  --zone YOUR_ZONE \
  --tags lms-backend
```

## 3. VM Bootstrap

SSH into the VM, clone the repo, then run:

```bash
cp .env.docker.example .env.docker
nano .env.docker
```

Fill in at least:

- `DOMAIN`
- `LETSENCRYPT_EMAIL`
- `RESEND_API_KEY`
- `DEFAULT_FROM_EMAIL`
- `POSTGRES_PASSWORD`
- `RAZORPAY_*` if payments are enabled
- `GOOGLE_CLIENT_ID` if Google login is enabled

Then run:

```bash
chmod +x bin/bootstrap-vm.sh
./bin/bootstrap-vm.sh yourdomain.com you@example.com
```

The script:

- installs Docker if missing
- installs Docker Compose plugin if missing
- installs git if missing
- creates `.env.docker` if missing
- generates a Django secret if the template value is still present
- provisions a Let's Encrypt certificate
- starts the full stack

## 4. Verification

Check containers:

```bash
docker compose ps
```

Check logs:

```bash
docker compose logs --tail=100
docker compose logs -f nginx
docker compose logs -f web
```

Check HTTP to HTTPS redirect:

```bash
curl -I http://yourdomain.com
curl -I https://yourdomain.com
```

## 5. Updates

Deploy future code changes with:

```bash
git pull
docker compose up -d --build
```
