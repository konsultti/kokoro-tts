# Git Hooks for Kokoro TTS

This directory contains git hooks that help maintain code quality by running automated checks before commits and pushes.

## Quick Start

Install the hooks after cloning the repository:

```bash
./hooks/install-hooks.sh
```

That's it! The hooks will now run automatically.

## Available Hooks

### pre-commit

**When it runs:** Before every `git commit`

**What it checks:**
- ✅ Python syntax validation
- ✅ Debugging artifacts (`pdb`, `breakpoint()`)
- ✅ TODO/FIXME markers
- ✅ File size warnings (> 1000 lines)

**Performance:** ⚡ < 5 seconds

### pre-push

**When it runs:** Before every `git push`

**What it does:**
- ✅ Runs full test suite (pytest)
- ✅ All 37+ tests must pass
- ✅ Prevents pushing broken code

**Performance:** ⚡ < 30 seconds

## Bypassing Hooks (Emergency Only)

If absolutely necessary, you can bypass hooks:

```bash
# Skip pre-commit hook
git commit --no-verify -m "emergency fix"

# Skip pre-push hook
git push --no-verify
```

⚠️ **Warning:** Only use `--no-verify` in true emergencies. The hooks protect code quality.

## Uninstalling Hooks

To remove the hooks:

```bash
rm .git/hooks/pre-commit
rm .git/hooks/pre-push
```

To restore them later:

```bash
./hooks/install-hooks.sh
```

## Hook Behavior

### Pre-Commit Hook

**Example output:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Pre-Commit Checks - Kokoro TTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Checking 2 Python file(s)...

[1/4] Checking Python syntax...
  ✓ All files have valid Python syntax

[2/4] Checking for debugging artifacts...
  ✓ No debugging artifacts found

[3/4] Checking for TODO/FIXME markers...
  ✓ No TODO/FIXME markers found

[4/4] Checking file sizes...
  ✓ All files are reasonable size

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✅ All pre-commit checks passed!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Pre-Push Hook

**Example output:**
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

## Troubleshooting

### Hooks not running

Check if hooks are executable:
```bash
ls -la .git/hooks/pre-commit
ls -la .git/hooks/pre-push
```

Reinstall if needed:
```bash
./hooks/install-hooks.sh
```

### Tests failing in pre-push

Run tests manually to debug:
```bash
./run_tests.sh
# or
pytest tests/ -v
```

### Python not found

Ensure Python 3.10+ is installed and in your PATH:
```bash
python3 --version
```

## Why Use Git Hooks?

**Benefits:**
- 🔍 Catch errors before committing
- 🧪 Ensure tests pass before pushing
- ⚡ Fast feedback loop (< 30 seconds)
- 🎯 Prevent broken code in remote branches
- 👥 Consistent quality across team

**Philosophy:**
The earlier you catch issues, the easier and cheaper they are to fix. Hooks provide instant feedback during development.

## Integration with CI

The pre-push hook runs the same tests as GitHub Actions CI, ensuring:
- No surprises when creating PRs
- Faster CI runs (tests already passed locally)
- Higher confidence in your code

## Further Reading

- [Pre-PR Workflow Documentation](../docs/PRE_PR_WORKFLOW.md)
- [Testing Documentation](../tests/README.md)
- [Git Hooks Documentation](https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks)

## Support

If you encounter issues with git hooks:
1. Check this README
2. Review [docs/PRE_PR_WORKFLOW.md](../docs/PRE_PR_WORKFLOW.md)
3. Open an issue on GitHub

Happy coding! 🚀
