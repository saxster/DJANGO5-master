"""
GeoDjango Configuration for macOS Apple Silicon

Specifies GDAL and GEOS library paths for PostGIS support.
This configuration is required for Django's GIS (Geographic Information System) features.

Platform: macOS with Apple Silicon (M1/M2/M3)
Libraries: Installed via Homebrew

Installation Requirements:
    brew install gdal
    brew install geos
    brew install postgis

Author: Claude Code
Date: 2025-10-10
"""

import os
from pathlib import Path

# ============================================================================
# GDAL (Geospatial Data Abstraction Library)
# ============================================================================
# GDAL is required for reading and writing raster and vector geospatial data
# formats. Django uses it for coordinate transformations, spatial operations,
# and data format conversions.
#
# Default path is Homebrew's Apple Silicon location: /opt/homebrew/lib/
# Override with GDAL_LIBRARY_PATH environment variable if needed.
# ============================================================================

GDAL_LIBRARY_PATH = os.environ.get(
    'GDAL_LIBRARY_PATH',
    '/opt/homebrew/lib/libgdal.dylib'  # Homebrew Apple Silicon default
)

# ============================================================================
# GEOS (Geometry Engine - Open Source)
# ============================================================================
# GEOS is required for geometric operations such as buffer, intersection,
# union, and spatial predicates (contains, intersects, etc.).
#
# Default path is Homebrew's Apple Silicon location: /opt/homebrew/lib/
# Override with GEOS_LIBRARY_PATH environment variable if needed.
# ============================================================================

GEOS_LIBRARY_PATH = os.environ.get(
    'GEOS_LIBRARY_PATH',
    '/opt/homebrew/lib/libgeos_c.dylib'  # Homebrew Apple Silicon default
)

# ============================================================================
# TROUBLESHOOTING
# ============================================================================
# If Django still cannot find GDAL/GEOS after installation:
#
# 1. Verify Homebrew installation:
#    $ brew list gdal
#    $ brew list geos
#
# 2. Check library locations:
#    $ ls -l /opt/homebrew/lib/libgdal.dylib
#    $ ls -l /opt/homebrew/lib/libgeos_c.dylib
#
# 3. Verify architecture (should be arm64):
#    $ file /opt/homebrew/lib/libgdal.dylib
#
# 4. Alternative: Create symlinks (one-time setup, works across all projects):
#    $ sudo mkdir -p /usr/local/lib
#    $ sudo ln -s /opt/homebrew/lib/libgdal.dylib /usr/local/lib/libgdal.dylib
#    $ sudo ln -s /opt/homebrew/lib/libgeos_c.dylib /usr/local/lib/libgeos_c.dylib
#
# 5. If using Intel Mac (x86_64), use /usr/local/lib instead:
#    GDAL_LIBRARY_PATH = '/usr/local/lib/libgdal.dylib'
#    GEOS_LIBRARY_PATH = '/usr/local/lib/libgeos_c.dylib'
#
# 6. Set explicit paths via environment variables:
#    $ export GDAL_LIBRARY_PATH=/opt/homebrew/lib/libgdal.dylib
#    $ export GEOS_LIBRARY_PATH=/opt/homebrew/lib/libgeos_c.dylib
# ============================================================================

# Export settings for import in other modules
__all__ = [
    'GDAL_LIBRARY_PATH',
    'GEOS_LIBRARY_PATH',
]

# Validation: Ensure paths are set (even if libraries not yet installed)
assert GDAL_LIBRARY_PATH, "GDAL_LIBRARY_PATH must be set"
assert GEOS_LIBRARY_PATH, "GEOS_LIBRARY_PATH must be set"

# Note: Actual library existence is checked by Django at runtime
# This allows settings to load even if libraries aren't installed yet
