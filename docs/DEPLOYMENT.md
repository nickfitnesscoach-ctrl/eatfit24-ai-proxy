# Deployment Guide

## Automatic Deployment via GitHub Actions

This project uses GitHub Actions to automatically deploy changes to the NL server whenever code is pushed to the `master` branch.

### Setup GitHub Secrets

Before the workflow can run, you need to configure the following secrets in your GitHub repository:

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add each of the following:

#### Required Secrets:

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `SSH_PRIVATE_KEY` | Private SSH key for authentication | Contents of `~/.ssh/id_ed25519` |
| `SSH_HOST` | Server IP address or hostname | `185.171.80.128` |
| `SSH_USER` | SSH username | `root` |
| `SSH_PORT` | SSH port (optional, defaults to 22) | `22` |

### Getting Your SSH Private Key

To get your SSH private key content:

```bash
# On Windows (Git Bash or WSL)
cat ~/.ssh/id_ed25519

# Copy the entire output, including:
# -----BEGIN OPENSSH PRIVATE KEY-----
# ... (key content) ...
# -----END OPENSSH PRIVATE KEY-----
```

**Important**: Never commit your private key to the repository!

### Workflow Triggers

The deployment workflow runs automatically when:

1. **Push to master**: Any commit pushed to the `master` branch triggers deployment
2. **Manual trigger**: You can manually trigger deployment from the Actions tab in GitHub

### Manual Deployment

To manually trigger a deployment:

1. Go to **Actions** tab in your GitHub repository
2. Select **Deploy EatFit24 AI Proxy to NL server** workflow
3. Click **Run workflow** button
4. Select the `master` branch
5. Click **Run workflow**

### Deployment Steps

The workflow performs the following steps:

1. Checkout the repository code
2. Setup SSH authentication using the private key
3. Connect to the NL server
4. Navigate to `/opt/eatfit24-ai-proxy`
5. Pull latest changes from GitHub
6. Rebuild and restart Docker containers
7. Display container status

### Monitoring Deployment

You can monitor deployment progress:

1. Go to **Actions** tab in GitHub
2. Click on the running workflow
3. View real-time logs of each step

### Troubleshooting

#### Deployment fails with SSH error

- Verify that `SSH_PRIVATE_KEY` is correctly set and includes the full key
- Ensure the public key is in `/root/.ssh/authorized_keys` on the server
- Check that `SSH_HOST` and `SSH_USER` are correct

#### Docker build fails

- Check the workflow logs for specific error messages
- Verify that Docker is running on the server
- Ensure there's enough disk space: `ssh root@185.171.80.128 "df -h"`

#### Container won't start

- Check container logs: `ssh root@185.171.80.128 "docker logs eatfit24-ai-proxy"`
- Verify environment variables in `.env` file on server
- Check Docker Compose configuration

### Manual Deployment (Fallback)

If GitHub Actions is not available, you can deploy manually:

```bash
# SSH into the server
ssh root@185.171.80.128

# Navigate to project directory
cd /opt/eatfit24-ai-proxy

# Pull latest changes
git pull origin master

# Rebuild and restart containers
docker compose up -d --build

# Check status
docker compose ps
docker logs eatfit24-ai-proxy
```

### Security Notes

- The workflow only runs on the `master` branch to prevent accidental deployments
- SSH private key is stored securely in GitHub Secrets (encrypted at rest)
- Only repository administrators can view or modify secrets
- Deployment requires both valid SSH key AND correct server credentials

### Post-Deployment Verification

After deployment, verify the service is running:

```bash
# Check health endpoint
curl http://100.84.210.65:8001/health

# Expected response:
# {"status":"ok"}
```
