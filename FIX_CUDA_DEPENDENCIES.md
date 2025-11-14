# CUDA Dependencies Fix - November 14, 2025

## Problem
The repository had dependency conflicts preventing installation on Linux systems due to mismatched CUDA library versions between `torch==2.8.0` and the explicitly specified NVIDIA CUDA packages in `requirements/base-linux.txt`.

## Error Messages
```
ERROR: Cannot install -r requirements/base.txt (line 224) and nvidia-cuda-nvrtc-cu12==12.1.105 
because these package versions have conflicting dependencies.

The conflict is caused by:
    The user requested nvidia-cuda-nvrtc-cu12==12.1.105
    torch 2.8.0 depends on nvidia-cuda-nvrtc-cu12==12.8.93
```

```
ERROR: Cannot install -r requirements/base.txt (line 224) and triton==3.0.0 
because these package versions have conflicting dependencies.

The conflict is caused by:
    The user requested triton==3.0.0
    torch 2.8.0 depends on triton==3.4.0
```

## Root Cause
The `requirements/base-linux.txt` file contained NVIDIA CUDA 12.1.x libraries from an older version, but the updated `torch==2.8.0` package requires CUDA 12.8.x libraries. This created an unresolvable dependency conflict during pip installation.

## Solution
Updated all NVIDIA CUDA library versions in `requirements/base-linux.txt` to match the exact versions required by `torch==2.8.0`:

### Updated Libraries (12.1.x → 12.8.x)
- `nvidia-cublas-cu12`: 12.1.3.1 → 12.8.4.1
- `nvidia-cuda-cupti-cu12`: 12.1.105 → 12.8.90
- `nvidia-cuda-nvrtc-cu12`: 12.1.105 → 12.8.93
- `nvidia-cuda-runtime-cu12`: 12.1.105 → 12.8.90
- `nvidia-cudnn-cu12`: 9.1.0.70 → 9.10.2.21
- `nvidia-cufft-cu12`: 11.0.2.54 → 11.3.3.83
- `nvidia-curand-cu12`: 10.3.2.106 → 10.3.9.90
- `nvidia-cusolver-cu12`: 11.4.5.107 → 11.7.3.90
- `nvidia-cusparse-cu12`: 12.1.0.106 → 12.5.8.93
- `nvidia-nccl-cu12`: 2.20.5 → 2.27.3
- `nvidia-nvjitlink-cu12`: 12.9.86 → 12.8.93
- `nvidia-nvtx-cu12`: 12.1.105 → 12.8.90
- `triton`: 3.0.0 → 3.4.0

### New Dependencies
- `nvidia-cusparselt-cu12==0.7.1` (new dependency in torch 2.8.0)
- `nvidia-cufile-cu12==1.13.1.3` (new dependency in torch 2.8.0)

## Verification
Successfully tested dependency resolution with:
```bash
pip install --dry-run -r requirements/base-linux.txt
```

Output confirmed all packages can be installed without conflicts:
```
Would install [all packages listed successfully]
```

## System Requirements Update
Updated minimum CUDA version requirement from 12.1+ to 12.8+ in the requirements file header.

## Files Changed
- `requirements/base-linux.txt`

## Testing
To verify the fix works on your system:
```bash
# Create fresh virtual environment
python -m venv venv
source venv/bin/activate

# Test dependency resolution
python scripts/install_dependencies.py --minimal
```

## Impact
This fix enables:
- ✅ Successful installation on Linux systems with CUDA support
- ✅ Compatibility with torch 2.8.0 security updates
- ✅ Access to latest NVIDIA CUDA 12.8.x GPU acceleration features
- ✅ Proper dependency tracking for ML/AI workloads

## Related Issues
- torch 2.8.0 security update: CVE-2025-32434, CVE-2025-3730, CVE-2025-2953
- CUDA Toolkit upgrade: 12.1.x → 12.8.x
