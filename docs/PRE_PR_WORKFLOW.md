# Pre-PR Testing Workflow

This document describes the automated testing workflow that runs before creating a Pull Request in the Kokoro TTS project.

## Overview

The pre-PR workflow uses a **multi-layer approach** to catch issues as early as possible:

1. **Layer 1: Pre-Commit Hook** - Quick checks before every commit (< 5 seconds)
2. **Layer 2: Pre-Push Hook** - Full test suite before push (< 30 seconds)
3. **Layer 3: GitHub Actions CI** - Cross-platform testing on PR (2-5 minutes)
4. **Layer 4: PR Checklist** - Manual verification checklist

## Visual Workflow

```
┌─────────────────────────────────────────────────┐
│ 1. Make changes to code                         │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 2. git add <files>                              │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 3. git commit -m "message"                      │
│    └─> PRE-COMMIT HOOK runs                    │
│        ✓ Syntax check                           │
│        ✓ Debugging artifacts check              │
│        ✓ TODO/FIXME detection                   │
│        ✓ File size check                        │
│        ⚡ < 5 seconds                            │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 4. git push origin <branch>                     │
│    └─> PRE-PUSH HOOK runs                      │
│        ✓ Run full test suite (37+ tests)        │
│        ✓ All tests must pass                    │
│        ⚡ < 30 seconds                           │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 5. Create PR on GitHub                          │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 6. GitHub Actions CI runs automatically         │
│    ✓ Python 3.10, 3.11, 3.12, 3.13             │
│    ✓ Linux, macOS, Windows                      │
│    ✓ Coverage report (Ubuntu 3.12)              │
│    ✓ Set PR status check                        │
│    ⚡ 2-5 minutes                                │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 7. Review & complete PR checklist               │
│    ☑ All tests pass                             │
│    ☑ Manual testing done                        │
│    ☑ Documentation updated                      │
│    ☑ CI status green                            │
└────────────┬────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│ 8. Merge PR ✅                                  │
└─────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Git Hooks (One-Time Setup)

After cloning the repository, install the git hooks:

```bash
./hooks/install-hooks.sh
```

This installs:
- **pre-commit** - Quick syntax and quality checks
- **pre-push** - Full test suite execution

### 2. Develop with Confidence

Once hooks are installed, they run automatically:

**When you commit:**
```bash
git commit -m "fix: improve EPUB parsing"
# → Pre-commit hook runs (< 5 seconds)
# ✓ Syntax check
# ✓ Quality checks
```

**When you push:**
```bash
git push origin feature-branch
# → Pre-push hook runs (< 30 seconds)
# ✓ Full test suite (37+ tests)
```

**When you create a PR:**
- GitHub Actions runs automatically
- Tests on Python 3.10, 3.11, 3.12, 3.13
- Tests on Linux, macOS, Windows
- Coverage report generated

## Layer 1: Pre-Commit Hook

### What It Checks

✅ **Python Syntax** - Ensures all Python files compile
✅ **Debugging Artifacts** - Warns about `pdb`, `breakpoint()`
✅ **TODO/FIXME Markers** - Warns about unfinished work
✅ **File Size** - Warns about files > 1000 lines

### When It Runs

Automatically before every `git commit`

### Performance

⚡ < 5 seconds (only checks staged files)

### Bypassing (Emergency Only)

```bash
git commit --no-verify -m "emergency fix"
```

### Example Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Pre-Commit Checks - Kokoro TTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Checking 3 Python file(s)...

[1/4] Checking Python syntax...
  ✓ All files have valid Python syntax

[2/4] Checking for debugging artifacts...
  ✓ No debugging artifacts found

[3/4] Checking for TODO/FIXME markers...
  ⚠ Found 2 TODO/FIXME marker(s) in kokoro_tts/core.py

[4/4] Checking file sizes...
  ✓ All files are reasonable size

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ⚠️  Pre-commit checks passed with 1 warning(s)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Layer 2: Pre-Push Hook

### What It Does

✅ Runs the full test suite using pytest
✅ All 37+ tests must pass
✅ Same tests that run in CI

### When It Runs

Automatically before every `git push`

### Performance

⚡ < 30 seconds (current test suite)

### Bypassing (Emergency Only)

```bash
git push --no-verify
```

### Example Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Pre-Push Tests - Kokoro TTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Running test suite...

======================== test session starts =========================
tests/test_cover_extraction.py ................           [ 43%]
tests/test_front_matter.py .............                  [ 78%]
tests/test_intro_generation.py ........                   [100%]

======================== 37 passed in 0.51s ==========================

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ All tests passed! Push proceeding...
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Layer 3: GitHub Actions CI

### What It Tests

The CI workflow (`.github/workflows/tests.yml`) runs automatically on:
- Pull request creation
- Pull request updates
- Push to `main` or `development` branches

**Test Matrix:**
- Python versions: 3.10, 3.11, 3.12, 3.13
- Operating systems: Ubuntu, macOS, Windows
- Total combinations: 12 test runs per PR

**Additional Features:**
- Coverage report (Ubuntu + Python 3.12)
- Codecov integration (optional)
- PR status check (blocks merge if tests fail)

### Viewing CI Results

1. Go to your PR on GitHub
2. Scroll to "Checks" section at the bottom
3. Click "Details" to see full test output
4. All checks must be green ✅ before merging

### What Happens if CI Fails

- PR is blocked from merging
- Red ❌ status appears on PR
- Click "Details" to see which tests failed
- Fix the issues and push again
- CI runs automatically on new commits

## Layer 4: PR Checklist

When creating a PR, fill out the checklist in the PR template:

### Code Quality
- [ ] Created feature branch
- [ ] Code follows project style
- [ ] Documentation updated
- [ ] Commit messages follow guidelines

### Testing
- [ ] Tested changes thoroughly
- [ ] All existing tests pass locally
- [ ] Added tests for new features/fixes
- [ ] GitHub Actions CI passes
- [ ] Test coverage maintained

### Manual Testing
- [ ] Tested on local environment
- [ ] Tested specific scenarios

## Running Tests Locally

### Quick Test Run

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_cover_extraction.py

# Run with verbose output
pytest tests/ -v
```

### Using the Test Runner

```bash
# Run all tests
./run_tests.sh

# Run with coverage report
./run_tests.sh --coverage

# Run specific test file
./run_tests.sh --test test_cover_extraction.py

# Verbose output
./run_tests.sh --verbose
```

### Coverage Report

```bash
# Generate HTML coverage report
pytest tests/ --cov=kokoro_tts --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Troubleshooting

### Pre-Commit Hook Not Running

```bash
# Check if hook is executable
ls -la .git/hooks/pre-commit

# Reinstall hooks
./hooks/install-hooks.sh
```

### Tests Failing Locally

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Install project in editable mode
pip install -e .

# Run tests with verbose output
pytest tests/ -v --tb=short
```

### Tests Pass Locally But Fail in CI

Common causes:
- Different Python version
- Different OS behavior
- Missing dependencies in CI
- Hardcoded paths

Check the CI logs for specific error messages.

### Bypassing Hooks (Emergency Only)

If you absolutely must bypass hooks:

```bash
# Skip pre-commit hook
git commit --no-verify -m "message"

# Skip pre-push hook
git push --no-verify
```

⚠️ **Warning:** Only use `--no-verify` in emergencies. The hooks are there to protect code quality.

## Best Practices

### Before Creating a PR

1. ✅ Run tests locally: `./run_tests.sh`
2. ✅ Check coverage: `./run_tests.sh --coverage`
3. ✅ Fix any failing tests
4. ✅ Add tests for new features/fixes
5. ✅ Update documentation if needed
6. ✅ Commit with descriptive messages
7. ✅ Push to your branch
8. ✅ Create PR with complete checklist

### During PR Review

1. ✅ Wait for CI to complete
2. ✅ Fix any CI failures
3. ✅ Respond to reviewer feedback
4. ✅ Add tests for suggested changes
5. ✅ Keep PR focused and small

### After PR Merge

1. ✅ Delete your feature branch
2. ✅ Pull latest changes to `main`/`development`
3. ✅ Verify your changes work in the merged code

## FAQ

### Q: Do I need to install hooks for every clone?

**A:** Yes, git hooks are not committed to the repository. Run `./hooks/install-hooks.sh` after cloning.

### Q: Can I disable hooks temporarily?

**A:** Yes, use `--no-verify` flag, but this should be rare.

### Q: What if pre-push hook takes too long?

**A:** The hook only runs the test suite. If it's slow, consider:
- Optimizing slow tests
- Running specific tests during development
- Using `--no-verify` sparingly

### Q: How do I run only specific tests?

**A:** Use pytest directly:
```bash
pytest tests/test_cover_extraction.py::TestCoverExtraction::test_cover_html_reference -v
```

### Q: What if CI is failing on a specific OS?

**A:** Debug using the CI logs:
1. Click "Details" on failing check
2. Review error messages
3. Fix OS-specific issues (paths, line endings, etc.)
4. Push fix and re-run CI

### Q: Can I run the full CI matrix locally?

**A:** Not easily. CI runs 12 combinations (4 Python versions × 3 OS). Use:
- `tox` for multi-version testing (if configured)
- Docker for OS testing
- GitHub Actions workflow_dispatch for manual CI runs

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [Git Hooks Documentation](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)
- [Contributing Guidelines](../CONTRIBUTING.md)

## Summary

The pre-PR workflow ensures code quality through automated testing at multiple stages:

- 🔍 **Pre-Commit** - Catch syntax errors instantly
- 🧪 **Pre-Push** - Verify all tests pass locally
- 🤖 **CI** - Validate across platforms and versions
- ✅ **PR Checklist** - Human verification

This multi-layer approach catches issues early, maintains code quality, and gives developers confidence when creating PRs.

Happy coding! 🚀
