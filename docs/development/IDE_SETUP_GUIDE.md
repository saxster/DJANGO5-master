# IDE Setup Guide

> **Last Updated**: November 5, 2025
> **Phase**: 7 - IDE Integration & Quality Enforcement
> **Scope**: Complete setup for VSCode and PyCharm

---

## Table of Contents

- [VSCode Setup (Recommended for Teams)](#vscode-setup-recommended-for-teams)
- [PyCharm Setup (Enterprise Standard)](#pycharm-setup-enterprise-standard)
- [Verification Checklist](#verification-checklist)
- [Troubleshooting IDE Issues](#troubleshooting-ide-issues)
- [IDE-Specific Features](#ide-specific-features)

---

## VSCode Setup (Recommended for Teams)

### Step 1: Install VSCode

Download from https://code.visualstudio.com/

**macOS:**
```bash
brew install --cask visual-studio-code
```

**Linux:**
```bash
sudo snap install code --classic
```

### Step 2: Install Python Extension Pack

1. Open VSCode
2. Go to **Extensions** (Cmd+Shift+X or Ctrl+Shift+X)
3. Search: `"Extension Pack for Python"` by Microsoft
4. Click **Install** (or press Enter when focused)

This automatically installs:
- Python (ms-python.python) - Core support
- Pylance (ms-python.vscode-pylance) - Code intelligence
- Jupyter (ms-vscode.jupyter) - Notebook support
- Black Formatter (ms-python.black-formatter)
- Pylint (ms-python.pylint)

### Step 3: Configure Project Settings

**Option A: Auto-detect (Recommended)**

1. Open project folder: File → Open Folder → `/path/to/DJANGO5-master`
2. VSCode auto-loads `.vscode/settings.json` (already configured)
3. VSCode auto-recommends extensions from `.vscode/extensions.json`

**Option B: Manual Configuration**

If auto-detection doesn't work:

```bash
# Copy settings to project
cp .vscode/settings.json .vscode/settings.json

# Create workspace file
cat > DJANGO5.code-workspace <<EOF
{
    "folders": [
        {
            "path": "."
        }
    ],
    "settings": {
        "python.defaultInterpreterPath": "\${workspaceFolder}/venv/bin/python",
        "python.linting.enabled": true,
        "python.linting.pylintEnabled": true,
        "python.testing.pytestEnabled": true
    }
}
EOF

# Open workspace
code DJANGO5.code-workspace
```

### Step 4: Select Python Interpreter

1. **Bottom right corner** of VSCode, click Python version
2. Select **"Enter interpreter path"**
3. Enter: `/Users/amar/Desktop/MyCode/DJANGO5-master/venv/bin/python`
   - Replace `/Users/amar/Desktop/MyCode/DJANGO5-master/` with your project path
4. Verify: Bottom right should show `Python 3.11.9 ('venv')`

### Step 5: Verify Extensions

1. Go to **Extensions** (Cmd+Shift+X)
2. Check "Installed" tab - you should see:
   - ✅ Python (ms-python.python)
   - ✅ Pylance (ms-python.vscode-pylance)
   - ✅ Black Formatter (ms-python.black-formatter)
   - ✅ Pylint (ms-python.pylint)
   - ✅ Django (batisteo.vscode-django)
   - ✅ Pytest (ms-python.pytest)

3. Install additional recommended extensions:
   - GitLens (eamodio.gitlens)
   - Flake8 (ms-python.flake8)
   - MyPy Type Checker (ms-python.mypy-type-checker)
   - Gitleaks (gitleaks.gitleaks-ext)

### Step 6: Configure Django Support

1. **Command Palette**: Ctrl+Shift+P (or Cmd+Shift+P)
2. Search: `"Django: Configure"`
3. Select: `"intelliwiz_config.settings"`
4. Verify: You should now see Django context menu

### Step 7: Test Configuration

Create a test file:

```python
# test_setup.py
from django.conf import settings
from apps.peoples.models import People

print("Django configured:", settings.configured)
print("Database URL:", settings.DATABASES['default']['NAME'])
```

Run in VSCode terminal:
```bash
python test_setup.py
```

Expected output:
```
Django configured: True
Database URL: intelliwiz
```

### VSCode Keyboard Shortcuts (Key Commands)

| Task | Shortcut |
|------|----------|
| **Format code** | Shift+Alt+F (or Cmd+Shift+P → Format Document) |
| **Organize imports** | Cmd+Shift+P → Sort imports |
| **Run tests** | Ctrl+Shift+; (or Testing sidebar) |
| **Go to definition** | F12 (or Ctrl+Click) |
| **Find usages** | Shift+Ctrl+F |
| **Rename symbol** | F2 |
| **Quick fix** | Ctrl+. |
| **Show errors/warnings** | Ctrl+Shift+M |
| **Open terminal** | Ctrl+` |
| **Open command palette** | Ctrl+Shift+P |
| **Django: Create app** | Cmd+Shift+P → Django |
| **Pytest: Run test** | Ctrl+Shift+; (testing sidebar) |

### VSCode Testing Integration

1. **Open Test Explorer**: Left sidebar → Testing icon (flask icon)
2. Click **"Configure tests"** if not detected
3. Select: **pytest**
4. Select test directory: **apps** (or specific path)

Now you can:
- Run all tests: Click play icon
- Run single test: Hover over test name → play icon
- Debug test: Click play with debug icon
- See coverage: Run with coverage option

### VSCode Debugging

**Set breakpoint:**
1. Click line number gutter (red dot appears)

**Debug test:**
1. Click test name in Testing sidebar
2. Select "Debug Test"

**Debug running code:**
1. Go to **Run and Debug** (Ctrl+Shift+D)
2. Select **"Python: Current File"**
3. Click **"Run"**

**Debugging commands:**
- F5: Continue
- F10: Step over
- F11: Step into
- Shift+F11: Step out
- Ctrl+K Ctrl+I: Show hover

---

## PyCharm Setup (Enterprise Standard)

### Step 1: Install PyCharm

Download from https://www.jetbrains.com/pycharm/

Choose:
- **Professional** (recommended for enterprise)
- **Community** (free, feature-limited)

**macOS:**
```bash
brew install --cask pycharm
```

### Step 2: Open Project

1. Launch PyCharm
2. **Open** → Select `/path/to/DJANGO5-master`
3. Click **"Trust Project"** when prompted

### Step 3: Configure Python Interpreter

1. **Settings** → **Project** → **Python Interpreter**
2. Click gear icon (⚙️) → **Add**
3. Select **"Existing environment"**
4. Click **...** → Navigate to `/path/to/venv/bin/python`
5. Click **OK**

Verify:
- Interpreter path shows: `/path/to/venv/bin/python`
- Python version shows: **3.11.9**
- Packages list shows Django, pytest, etc.

### Step 4: Enable Django Support

1. **Settings** → **Languages & Frameworks** → **Django**
2. Check: **"Enable Django support"**
3. Set **Django project root**: `/path/to/DJANGO5-master`
4. Set **Settings module**: `intelliwiz_config.settings`
5. Click **OK**

### Step 5: Import Inspection Profile

**Option A: Auto-detect**
1. PyCharm auto-loads `.idea/inspectionProfiles/ProjectDefault.xml`
2. Settings → **Editor** → **Inspections** → Verify profile

**Option B: Manual Import**
1. **Settings** → **Editor** → **Inspections**
2. Click gear icon → **Import Profile**
3. Select `.idea/inspectionProfiles/ProjectDefault.xml`
4. Click **Import**

### Step 6: Configure Code Style

**Option A: Auto-detect**
1. PyCharm auto-loads `.idea/codeStyles/Project.xml`

**Option B: Manual Setup**
1. **Settings** → **Editor** → **Code Style** → **Python**
2. Set **Line length**: 120
3. Set **Indent**: 4 spaces
4. Check **"Optimize imports"**
5. Select **"Sort by type"**

### Step 7: Run Configurations

Create run configurations for common tasks:

**1. Django Server**
1. **Run** → **Edit Configurations**
2. Click **+** → **Django Server**
3. Set:
   - **Django project root**: `/path/to/DJANGO5-master`
   - **Settings**: `intelliwiz_config.settings`
4. Click **OK**
5. Run: Shift+F10 (or Run menu)

**2. Pytest**
1. **Run** → **Edit Configurations**
2. Click **+** → **Python** → **pytest**
3. Set **Target**: `apps` (or specific test)
4. Click **OK**
5. Run: Shift+F10

**3. Celery Worker**
1. **Run** → **Edit Configurations**
2. Click **+** → **Python**
3. Set:
   - **Module name**: `celery`
   - **Parameters**: `-A intelliwiz_config worker -Q celery -c 8 -l info`
4. Click **OK**

### Step 8: Verify Setup

Open any Python file and verify:

- ✅ **Code completion** works (Ctrl+Space)
- ✅ **Go to definition** works (Ctrl+B)
- ✅ **Inspections** show (light bulb icon with suggestions)
- ✅ **Terminal** works (Alt+F12)
- ✅ **Django context** available (Django context menu)

### PyCharm Keyboard Shortcuts (Key Commands)

| Task | Shortcut |
|------|----------|
| **Format code** | Ctrl+Alt+L (Linux/Windows) or Cmd+Alt+L (macOS) |
| **Optimize imports** | Ctrl+Alt+O (Linux/Windows) or Cmd+Alt+O (macOS) |
| **Run tests** | Shift+F10 (or Ctrl+Shift+F10) |
| **Debug test** | Shift+F9 |
| **Go to definition** | Ctrl+B or Cmd+B |
| **Find usages** | Ctrl+Alt+F7 or Cmd+Alt+F7 |
| **Rename symbol** | Shift+F6 |
| **Show intentions/fixes** | Alt+Enter |
| **Terminal** | Alt+F12 |
| **Run configuration** | Shift+F10 |
| **Debug configuration** | Shift+F9 |
| **Comment/uncomment** | Ctrl+/ or Cmd+/ |
| **Duplicate line** | Ctrl+D or Cmd+D |
| **Find in files** | Ctrl+Shift+F |
| **Replace in files** | Ctrl+Shift+H |

### PyCharm Inspections (Quality Checks)

1. **Settings** → **Editor** → **Inspections**
2. View all active inspections
3. Key enabled inspections:
   - **Cyclomatic complexity** (max 10)
   - **Broad exception handling** (error level)
   - **Unused imports** (warning)
   - **SQL injection** (error)
   - **Security issues** (error)

Run inspection:
- **Code** → **Run Inspection by Name**
- Or: **Ctrl+Alt+Shift+I**

### PyCharm Live Templates

Pre-configured templates for common patterns:

1. **Code** → **Live Templates**
2. Available templates:
   - `tmodel` → Test model pattern
   - `apiview` → API view pattern
   - `service` → Service class pattern
   - `test` → Test function pattern

Use:
- Type prefix (e.g., `tmodel`)
- Press Tab to expand
- Edit placeholders

---

## Verification Checklist

### Before Starting Development

- [ ] **Python Version**: `python --version` shows 3.11.9
- [ ] **Virtual Environment**: `which python` shows `venv/bin/python`
- [ ] **Dependencies**: `pip list | grep Django` shows latest version
- [ ] **IDE Selected**: VSCode or PyCharm open with project
- [ ] **Python Interpreter**: IDE shows correct interpreter path
- [ ] **Django Support**: IDE has Django plugin/support enabled
- [ ] **Extensions Installed**: All recommended extensions installed
- [ ] **Database Connection**: `python manage.py dbshell` works
- [ ] **Pre-commit Hooks**: `pre-commit install` completed
- [ ] **Tests Pass**: `pytest apps/ -q` returns 0 errors

### Quick Verification Commands

```bash
# 1. Python version
python --version
# Expected: Python 3.11.9

# 2. Virtual environment
which python
# Expected: /Users/amar/Desktop/MyCode/DJANGO5-master/venv/bin/python

# 3. Django check
python manage.py check
# Expected: System check identified no issues

# 4. Database connection
python manage.py dbshell
# Expected: psql prompt or similar

# 5. Run tests
pytest apps/ -q
# Expected: no errors, X passed

# 6. Pre-commit hooks
pre-commit run --all-files
# Expected: all hooks passed

# 7. Code quality
python scripts/validate_code_quality.py
# Expected: validation passed
```

### IDE Health Check

**VSCode:**
```
1. Open a Python file
2. Ctrl+Shift+P → "Python: Lint Workspace"
3. Should show any issues
4. Ctrl+Shift+P → "Python: Run Tests"
5. Tests should run successfully
```

**PyCharm:**
```
1. Open a Python file
2. Code → Run Inspection by Name → "Python"
3. Should show inspection results
4. Right-click test file → "Run pytest"
5. Tests should run successfully
```

---

## Troubleshooting IDE Issues

### VSCode Issues

#### Issue: "Module 'django' not found"

**Solution:**
1. Verify Python interpreter: Click bottom right, select `venv/bin/python`
2. Reload VSCode: Ctrl+Shift+P → "Reload Window"
3. Verify settings: `.vscode/settings.json` exists and valid

#### Issue: "Pylint: command not found"

**Solution:**
```bash
# Reinstall in venv
source venv/bin/activate
pip install pylint pylint-django

# Restart VSCode
Ctrl+Shift+P → "Reload Window"
```

#### Issue: "Black formatter not available"

**Solution:**
```bash
# Install Black
pip install black

# Verify installation
which black

# Restart VSCode
Ctrl+Shift+P → "Reload Window"
```

#### Issue: "pytest not found"

**Solution:**
```bash
# Install pytest
pip install pytest pytest-django pytest-cov

# Verify Python path in settings.json
"python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python"

# Restart VSCode
```

#### Issue: "Django context not detected"

**Solution:**
1. Install Django extension: `batisteo.vscode-django`
2. Set `DJANGO_SETTINGS_MODULE` in `.env`:
   ```
   DJANGO_SETTINGS_MODULE=intelliwiz_config.settings
   ```
3. Create `.djangorc` in project root:
   ```
   [django]
   django_settings_module = intelliwiz_config.settings
   ```

### PyCharm Issues

#### Issue: "Unresolved reference" for apps

**Solution:**
1. **Settings** → **Project** → **Project Structure**
2. Mark `apps/` as **Sources Root** (right-click → Mark as Sources Root)
3. File → Invalidate Caches → Invalidate and Restart

#### Issue: "Django not configured"

**Solution:**
1. **Settings** → **Languages & Frameworks** → **Django**
2. Enable: ✅ "Enable Django support"
3. Django project root: `/full/path/to/project`
4. Settings module: `intelliwiz_config.settings`

#### Issue: "Python interpreter not found"

**Solution:**
1. **Settings** → **Project** → **Python Interpreter**
2. Click gear → **Add Interpreter** → **Add Local Interpreter**
3. Select: **Existing environment**
4. Path: `/full/path/to/venv/bin/python`
5. Click **OK**

#### Issue: "Inspection profile not loaded"

**Solution:**
1. **Settings** → **Editor** → **Inspections**
2. Click gear icon → **Import Profile**
3. Select: `.idea/inspectionProfiles/ProjectDefault.xml`
4. Click **Import**

#### Issue: "Code style not applied on save"

**Solution:**
1. **Settings** → **Editor** → **Code Style**
2. Scheme: Select **"Project"**
3. **Settings** → **Tools** → **Python Integrated Tools**
4. Default test runner: **pytest**
5. Reformat code: Cmd+Alt+L (macOS) or Ctrl+Alt+L (Linux/Windows)

---

## IDE-Specific Features

### VSCode-Specific Features

**Advantages:**
- ✅ Lightweight (3-4 MB)
- ✅ Fast startup
- ✅ Excellent extension ecosystem
- ✅ Great for remote development (SSH)
- ✅ VS Code Server (browser-based)

**Recommended for:**
- Teams with resource constraints
- Remote development
- Quick editing
- Cross-platform consistency

**Extensions to add:**
```json
// Productivity
- GitHub Copilot (github.copilot)
- Thunder Client (rangav.vscode-thunder-client)
- Database Client (cweijan.vscode-database-client2)
- Docker (ms-vscode.docker)
```

### PyCharm-Specific Features

**Advantages:**
- ✅ Extremely smart IDE (JetBrains)
- ✅ Excellent Django support
- ✅ Advanced refactoring
- ✅ Professional debugging
- ✅ Database tools built-in
- ✅ Version control integration

**Recommended for:**
- Professional teams
- Large codebases
- Complex debugging
- Advanced refactoring

**Key features:**
- **Project Structure View**: Shows file relationships
- **Database Tools**: Query builder, schema viewer
- **Version Control Integration**: Git, GitHub, GitLab
- **Terminal**: Built-in terminal with project environment
- **HTTP Client**: Test APIs within IDE
- **Profiler**: Performance analysis
- **Coverage**: Visual coverage indicators

---

## CI/CD Integration

### GitHub Actions (Automated Checks)

Configuration: `.github/workflows/code-quality.yml`

**Runs on every push/PR:**
1. Security scanning (Bandit, Safety, Semgrep)
2. File size validation
3. Complexity checks
4. Test coverage (75% minimum)
5. Pattern enforcement (forbidden patterns)

**View results:**
1. Push code to GitHub
2. Go to **Actions** tab
3. See workflow results
4. Click workflow → details

### Pre-commit Hooks (Local Validation)

Configuration: `.pre-commit-config.yaml`

**Install:**
```bash
pre-commit install
```

**Run manually:**
```bash
# All files
pre-commit run --all-files

# Specific hook
pre-commit run file-size-validation --all-files
```

**Hooks run automatically before commit:**
- File size validation
- Complexity checks
- Network timeout validation
- Import sorting
- Security scanning

---

## Recommended Workflow

### Daily Development

```bash
# 1. Start of day: pull latest
git pull origin develop

# 2. Create feature branch
git checkout -b feature/my-feature

# 3. Write code in IDE
# IDE shows linting errors in real-time
# IDE enforces quality standards
# IDE suggests quick fixes (Alt+Enter in PyCharm, Ctrl+. in VSCode)

# 4. Run tests before commit
pytest apps/ -v

# 5. Format and optimize
# VSCode: Shift+Alt+F
# PyCharm: Cmd+Alt+L

# 6. Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat(scope): description"

# 7. Push and create PR
git push origin feature/my-feature
# Create PR on GitHub
```

### Code Review Process

1. Push code → GitHub Actions runs automated checks
2. If checks pass → code is reviewed
3. Reviewer tests locally in IDE:
   - Opens branch in IDE
   - Runs tests
   - Checks coverage
   - Verifies quality
4. If approved → merge to develop

---

## Performance Tuning

### VSCode Performance

```json
// .vscode/settings.json - Add these for better performance
{
  "python.analysis.workers": 4,           // Number of analysis workers
  "python.analysis.indexing": true,       // Enable indexing
  "[python]": {
    "editor.defaultFormatter": "ms-python.python",
    "editor.formatOnSaveTimeout": 5000    // Timeout for format on save
  },
  "files.exclude": {
    "**/__pycache__": true,               // Don't index cache
    "**/venv": true,
    "**/.mypy_cache": true
  }
}
```

### PyCharm Performance

1. **Settings** → **Editor** → **General**
   - Uncheck: "Show whitespaces" (if slow)
   - Uncheck: "Show intention lightbulb" (shows suggestion light bulbs)

2. **Settings** → **Editor** → **Inspections**
   - Disable non-critical inspections if slow
   - Reduce scope (not all files)

3. **Increase memory** (settings.ini):
   ```
   -Xmx2048m   # Increase to available RAM
   ```

---

## Summary

| Feature | VSCode | PyCharm |
|---------|--------|---------|
| **Cost** | Free | Paid (free community edition) |
| **Performance** | Faster | Slower (more features) |
| **Learning Curve** | Easier | Steeper |
| **Django Support** | Good | Excellent |
| **Refactoring** | Basic | Advanced |
| **Database Tools** | Extension required | Built-in |
| **Best For** | Teams, remote | Enterprise, complex |

**Choose:**
- **VSCode** if: Using remote development, small team, prefer lightweight
- **PyCharm** if: Working on large project, need advanced features, professional team

Both are excellent choices. Pick what works for your team!

---

**Document Version**: 1.0
**Last Updated**: November 5, 2025
**Status**: Phase 7 Complete
**Maintainer**: Development Team
