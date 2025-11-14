#!/usr/bin/env python
"""
Test script to verify CUDA dependency resolution fix.

This script tests that the updated CUDA library versions in
requirements/base-linux.txt can be resolved by pip without conflicts.
"""

import subprocess
import sys
from pathlib import Path

def test_dependency_resolution():
    """Test that pip can resolve dependencies without conflicts."""
    print("=" * 70)
    print("Testing CUDA Dependency Resolution Fix")
    print("=" * 70)
    print()
    
    # Get project root
    project_root = Path(__file__).parent.parent.absolute()
    requirements_file = project_root / "requirements" / "base-linux.txt"
    
    if not requirements_file.exists():
        print(f"❌ Error: {requirements_file} not found")
        return False
    
    print(f"Testing: {requirements_file}")
    print()
    
    # Test dependency resolution (dry-run, no actual installation)
    print("Running: pip install --dry-run -r requirements/base-linux.txt")
    print("(This will check if all dependencies can be resolved)")
    print()
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run", "-r", str(requirements_file)],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Check for specific error patterns
        errors = []
        if "ERROR: Cannot install" in result.stderr:
            errors.append("Dependency conflict detected")
        if "nvidia-cuda" in result.stderr and "conflict" in result.stderr.lower():
            errors.append("CUDA library version conflict")
        if "triton" in result.stderr and "conflict" in result.stderr.lower():
            errors.append("Triton version conflict")
        
        if errors or result.returncode != 0:
            print("❌ FAILED - Dependency resolution failed")
            print()
            print("Errors found:")
            for error in errors:
                print(f"  - {error}")
            print()
            print("Full output:")
            print(result.stderr[-1000:])  # Last 1000 chars
            return False
        
        # Check for success indicators
        if "Would install" in result.stdout:
            print("✅ SUCCESS - All dependencies can be resolved!")
            print()
            print("Key packages verified:")
            for pkg in ["torch", "triton", "nvidia-cuda", "nvidia-cudnn"]:
                if pkg in result.stdout:
                    print(f"  ✓ {pkg}")
            return True
        else:
            print("⚠️  WARNING - Unexpected output format")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ FAILED - Command timeout (>120s)")
        return False
    except Exception as e:
        print(f"❌ FAILED - Exception: {e}")
        return False

def main():
    """Main test function."""
    print()
    success = test_dependency_resolution()
    print()
    print("=" * 70)
    
    if success:
        print("✅ CUDA dependency fix verified successfully!")
        print()
        print("You can now install dependencies with:")
        print("  python scripts/install_dependencies.py --minimal")
        return 0
    else:
        print("❌ CUDA dependency fix verification failed")
        print()
        print("Please review the error messages above and check:")
        print("  1. requirements/base-linux.txt has correct CUDA versions")
        print("  2. torch version matches CUDA library requirements")
        print("  3. triton version is compatible with torch")
        return 1

if __name__ == "__main__":
    sys.exit(main())
