# Deployment Instructions

This document explains how to use the CI/CD workflows with the "prod" environment.

## Environment Setup

The "prod" environment has been configured in GitHub with the following secrets:

- `TRADIER_API_TOKEN` - Tradier API token for testing
- `MASSIVE_API_KEY` - Massive/Polygon API key for testing
- `AWS_ACCESS_KEY_ID` - AWS access key for deployment
- `AWS_SECRET_ACCESS_KEY` - AWS secret key for deployment
- `AWS_REGION` - AWS region (optional, defaults to us-east-1)
- `APP_RUNNER_SERVICE_ARN` - Full ARN of your App Runner service

## How It Works

### Automatic Deployment Flow

1. **Push to `master` branch**
   - Triggers the `ci-cd.yml` workflow
   - Runs tests first
   - Builds Docker image
   - Deploys to App Runner (if tests pass)

2. **Pull Request**
   - Triggers the `test.yml` workflow
   - Only runs tests (no deployment)
   - Tests must pass before merging

### Workflow Steps

1. **Test Job** (`test`)
   - Installs dependencies
   - Runs pytest test suite
   - Generates coverage reports
   - **Must pass** for deployment to proceed

2. **Build Job** (`build`)
   - Builds Docker image
   - Tests Docker image health
   - **Only runs if tests pass**

3. **Deploy Job** (`deploy`)
   - Uses "prod" environment secrets
   - Configures AWS credentials
   - Triggers App Runner deployment
   - **Only runs on `master` branch**

## Using the Workflow

### Option 1: Automatic Deployment (Recommended)

Simply push to the `master` branch:

```bash
git add .
git commit -m "Your changes"
git push origin master
```

The workflow will:
1. ✅ Run tests automatically
2. ✅ Build Docker image
3. ✅ Deploy to App Runner (if tests pass)

### Option 2: Manual Trigger

You can also manually trigger the workflow:

1. Go to GitHub → Actions tab
2. Select "CI/CD Pipeline" workflow
3. Click "Run workflow"
4. Select branch (usually `master`)
5. Click "Run workflow"

### Option 3: Pull Request Workflow

1. Create a feature branch:
   ```bash
   git checkout -b feature/my-feature
   ```

2. Make changes and push:
   ```bash
   git push origin feature/my-feature
   ```

3. Create a Pull Request on GitHub

4. Tests will run automatically on the PR

5. Merge only after tests pass

## Monitoring Deployments

### GitHub Actions

1. Go to **Actions** tab in GitHub
2. Click on the workflow run
3. View logs for each job:
   - ✅ Green checkmark = Success
   - ❌ Red X = Failure

### AWS App Runner

1. Go to AWS App Runner console
2. Click on your service
3. View deployment history
4. Check service status

## Troubleshooting

### Tests Fail

- Check the test logs in GitHub Actions
- Run tests locally: `pytest tests/ -v`
- Fix issues and push again

### Deployment Fails

- Check AWS credentials in "prod" environment secrets
- Verify `APP_RUNNER_SERVICE_ARN` is correct (full ARN)
- Check AWS App Runner service status
- Review deployment logs in AWS console

### Environment Secrets Not Found

- Go to Settings → Environments → "prod"
- Verify all secrets are added
- Check secret names match exactly (case-sensitive)

## Environment Protection (Optional)

If you enabled protection rules for "prod":

1. **Required Reviewers**: Deployment will wait for approval
   - Go to Actions → Workflow run
   - Click "Review deployments"
   - Approve or reject

2. **Wait Timer**: Deployment will wait for the specified time
   - Automatic after the wait period

3. **Deployment Branches**: Only specified branches can deploy
   - Usually set to `master` only

## Quick Reference

| Action | What Happens |
|--------|-------------|
| Push to `master` | Tests → Build → Deploy |
| Push to feature branch | Tests only (if PR created) |
| Create PR | Tests run automatically |
| Merge PR to `master` | Tests → Build → Deploy |
| Manual trigger | Full pipeline runs |

## Secrets Reference

All secrets are stored in the "prod" environment:

- `TRADIER_API_TOKEN` - Used in tests (optional, can use dummy value)
- `MASSIVE_API_KEY` - Used in tests (optional, can use dummy value)
- `AWS_ACCESS_KEY_ID` - Required for deployment
- `AWS_SECRET_ACCESS_KEY` - Required for deployment
- `AWS_REGION` - Optional (defaults to us-east-1)
- `APP_RUNNER_SERVICE_ARN` - Required for deployment (full ARN)

## Next Steps

1. ✅ Environment "prod" is configured
2. ✅ Secrets are added
3. ✅ Workflow is updated to use "prod" environment
4. 🚀 Push to `master` to deploy!

