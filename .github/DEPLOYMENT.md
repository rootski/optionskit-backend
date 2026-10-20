# Deployment

**As of 2026-10-20 this project is no longer deployed.** The AWS App Runner
service, ECR repository, and VPC connector in `us-east-1` were torn down, and
the deploy job was removed from `.github/workflows/ci-cd.yml`.

CI still runs on every push to `master` and on pull requests:

1. **Test** — installs dependencies and runs the pytest suite with coverage.
2. **Build** — builds the Docker image and smoke-tests `/healthz` and
   `/version` against a local Redis.

## Leftover GitHub configuration

The `prod` environment in GitHub still holds these secrets. They are unused and
the AWS keys should be deactivated or deleted:

- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (IAM user `options`)
- `AWS_REGION`
- `APP_RUNNER_SERVICE_ARN` (service no longer exists)
- `TRADIER_API_TOKEN`, `MASSIVE_API_KEY` (still optional for tests)

## Redeploying later

The app is a plain Docker image listening on port 8000 that needs
`TRADIER_API_TOKEN`, `MASSIVE_API_KEY`, and `REDIS_URL`. See `compose.yaml`
for the local shape. The old App Runner configuration (1 vCPU / 2 GB, ECR image
source, auto-deploy on `latest`) can be recreated from the git history of this
file and `ci-cd.yml` if needed.
