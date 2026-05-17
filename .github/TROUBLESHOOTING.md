# Troubleshooting GitHub Actions Workflows

## How to Check if Something Failed

### 1. Repository Main Page

Look at the commit status badge next to your latest commit:
- ✅ **Green checkmark** = All workflows passed
- ❌ **Red X** = At least one workflow failed
- 🟡 **Yellow dot** = Workflow is running
- ⚪ **Gray circle** = Workflow is pending

### 2. Actions Tab

1. Go to your GitHub repository
2. Click the **"Actions"** tab at the top
3. You'll see a list of workflow runs

**Status Indicators:**
- 🟢 **Green checkmark** = Success
- 🔴 **Red X** = Failed
- 🟡 **Yellow dot** = In progress
- ⚪ **Gray circle** = Queued/Pending

### 3. Click on a Workflow Run

When you click on a workflow run, you'll see:

**Job Status:**
- ✅ `test` - Green = Tests passed
- ✅ `build` - Green = Docker build succeeded
- ✅ `deploy` - Green = Deployment succeeded
- ❌ Any red X = That job failed

### 4. Click on a Failed Job

Click on the failed job (red X) to see:
- **Error messages** in red
- **Step-by-step logs**
- **Which step failed**

### 5. Common Failure Points

#### Test Job Fails
- **Look for:** `pytest` errors, import errors, test failures
- **Common causes:**
  - Syntax errors in code
  - Missing dependencies
  - Test assertions failing
  - Import errors

#### Build Job Fails
- **Look for:** Docker build errors
- **Common causes:**
  - Dockerfile syntax errors
  - Missing files in Docker context
  - Build timeout
  - Health check failures

#### Deploy Job Fails
- **Look for:** AWS credential errors, ARN errors
- **Common causes:**
  - Invalid AWS credentials
  - Wrong App Runner ARN
  - Missing environment secrets
  - AWS permissions issues

## Reading the Logs

### Step-by-Step Logs

Each job shows steps:
```
✓ Checkout code
✓ Set up Python
✓ Install dependencies
✓ Run tests
✗ Some step failed  ← This is where it failed
```

### Error Messages

Look for:
- **Red text** = Error messages
- **Exit code 1** = Failure
- **Traceback** = Python errors
- **ERROR** or **FAILED** keywords

### Example Error Output

```
Run pytest tests/ -v
============================= test session starts ==============================
tests/test_health.py::test_healthz FAILED
...
FAILED tests/test_health.py::test_healthz - AssertionError: ...
============================= 1 failed in 0.5s ==============================
Error: Process completed with exit code 1.
```

## Notification Settings

### Email Notifications

GitHub can email you when workflows fail:

1. Go to **Settings** → **Notifications**
2. Under "Actions", enable:
   - ✅ Workflow runs that fail
   - ✅ Workflow run approvals

### GitHub Mobile App

The GitHub mobile app will show notifications for failed workflows.

## Quick Diagnostic Commands

### Check Workflow Status via API

```bash
# Get latest workflow run status
gh run list --limit 1

# View logs for latest run
gh run view --log
```

### Check Specific Job

```bash
# View a specific workflow run
gh run view <run-id>

# Watch a running workflow
gh run watch <run-id>
```

## What to Do When Something Fails

### 1. Identify the Failed Job
- Look for the red X
- Note which job failed (test, build, or deploy)

### 2. Read the Error Message
- Click on the failed job
- Scroll to find the error
- Look for red text or "Error:" messages

### 3. Common Fixes

**Tests Fail:**
```bash
# Run tests locally to reproduce
pytest tests/ -v

# Fix the issue
# Commit and push again
```

**Build Fails:**
```bash
# Test Docker build locally
docker build -t test .

# Fix Dockerfile or missing files
# Commit and push again
```

**Deploy Fails:**
- Check AWS credentials in "prod" environment
- Verify App Runner ARN is correct
- Check AWS permissions
- Review AWS App Runner console for errors

### 4. Re-run Failed Workflow

1. Go to Actions tab
2. Click on the failed workflow run
3. Click **"Re-run all jobs"** or **"Re-run failed jobs"**

## Status Badge

You can add a status badge to your README:

```markdown
![CI/CD](https://github.com/your-username/optionskit-backend/workflows/CI/CD%20Pipeline/badge.svg)
```

This shows the latest workflow status on your README.

## Summary

**To know if something failed:**
1. ✅ Check repository main page for red X
2. ✅ Go to Actions tab
3. ✅ Look for red X on any job
4. ✅ Click failed job to see error details
5. ✅ Read the error message
6. ✅ Fix and push again

**Quick visual guide:**
- 🟢 Green = Good
- 🔴 Red = Bad (needs attention)
- 🟡 Yellow = In progress
- ⚪ Gray = Waiting








