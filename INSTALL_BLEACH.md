# Installing Bleach for XSS Security Fix

## Quick Installation

### Option 1: Using Python 3.11.9 Virtual Environment (Recommended)

```bash
# Navigate to project directory
cd /Users/amar/Desktop/MyCode/DJANGO5-master

# Activate your virtual environment
source venv/bin/activate

# Install bleach
pip install bleach==6.2.0

# Verify installation
python -c "import bleach; print(f'Bleach {bleach.__version__} installed successfully')"
```

### Option 2: If Virtual Environment Doesn't Exist

```bash
# Create new virtual environment with Python 3.11.9
pyenv install 3.11.9  # If not already installed
pyenv local 3.11.9
~/.pyenv/versions/3.11.9/bin/python -m venv venv
source venv/bin/activate

# Install all requirements including bleach
pip install -r requirements/base-macos.txt  # For macOS
# OR
pip install -r requirements/base-linux.txt  # For Linux

pip install -r requirements/observability.txt
pip install -r requirements/encryption.txt
```

### Option 3: Install Just Bleach in Existing Environment

```bash
# If you already have an active virtual environment
pip install bleach==6.2.0
```

## Verification

After installation, verify bleach is working:

```bash
python -c "
import bleach
print(f'✅ Bleach version: {bleach.__version__}')

# Test sanitization
dirty_html = '<b onclick=\"alert(1)\">Click me</b>'
clean_html = bleach.clean(dirty_html, tags=['b'], attributes={}, strip=True)
print(f'Original: {dirty_html}')
print(f'Sanitized: {clean_html}')
print('✅ XSS protection working correctly!' if 'onclick' not in clean_html else '❌ Error')
"
```

Expected output:
```
✅ Bleach version: 6.2.0
Original: <b onclick="alert(1)">Click me</b>
Sanitized: <b>Click me</b>
✅ XSS protection working correctly!
```

## Troubleshooting

### Error: "No such file or directory: venv/bin/activate"

**Solution**: Create virtual environment first:
```bash
python3 -m venv venv
source venv/bin/activate
pip install bleach==6.2.0
```

### Error: "externally-managed-environment"

**Solution**: You're trying to install in system Python. Use virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # This is important!
pip install bleach==6.2.0
```

### Error: "command not found: pyenv"

**Solution**: Use system Python 3.11:
```bash
python3.11 -m venv venv
source venv/bin/activate
pip install bleach==6.2.0
```

## Next Steps After Installation

1. ✅ Bleach is installed
2. Run syntax check:
   ```bash
   python -m py_compile apps/y_helpdesk/security/ticket_security_service.py
   ```
3. Test the fix:
   ```bash
   python manage.py test apps.y_helpdesk.tests.test_security_fixes
   ```
4. Deploy to staging

## What Changed

Bleach replaces weak regex-based HTML sanitization with a battle-tested library:

**Before (Vulnerable to XSS)**:
```python
sanitized = re.sub(r'<(?!/?[bi]>)[^>]*>', '', sanitized)  # Can be bypassed
```

**After (Secure)**:
```python
import bleach

sanitized = bleach.clean(
    value,
    tags=['b', 'i', 'br', 'p'],  # Only these tags allowed
    attributes={},                # No attributes (blocks onclick, etc.)
    strip=True
)
```

This prevents attacks like:
- `<b onclick="alert(1)">Click</b>` → `<b>Click</b>` ✅
- `<script>alert(document.cookie)</script>` → Removed ✅
- `<img onerror="fetch('evil.com')">` → Removed ✅

---

**Note**: Bleach 6.2.0 has been added to `requirements/base.txt`, so future installations will include it automatically.
