# PR: Bump actions/upload-artifact to v4

## Summary
This PR updates all GitHub Actions workflow files to use `actions/upload-artifact@v4` instead of the deprecated `@v3`.

## Changes Made
Updated 11 occurrences across 7 workflow files:
- `.github/workflows/circular-dependency-check.yml` (1 occurrence)
- `.github/workflows/performance_regression.yml` (2 occurrences)
- `.github/workflows/api-contract-validation.yml` (1 occurrence)
- `.github/workflows/stream_health_check.yml` (1 occurrence)
- `.github/workflows/nightly_soak.yml` (1 occurrence)
- `.github/workflows/code-quality.yml` (4 occurrences)
- `.github/workflows/exception-quality-check.yml` (1 occurrence)

## References
- Job ID: 55366228653
- Workflow file: `.github/workflows/circular-dependency-check.yml`

## Target Branch
- main (repository default branch)

## Testing
All workflow files have been validated for correct YAML syntax.
