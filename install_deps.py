#!/usr/bin/env python3
"""
Optimized Dependency Installer for Chirag Clone v2.8
=====================================================
Fast batch installation for backend (Python) and frontend (Node.js).

Optimizations:
- Batch pip install (parallel internally) instead of one-by-one
- Pre-filters problematic packages
- Uses --no-input --disable-pip-version-check for speed
- Parallel frontend install while backend runs

Usage:
    python install_deps.py [--backend-only] [--frontend-only] [--force-all]
"""

import subprocess
import sys
import os
import argparse
import time
import tempfile
import concurrent.futures
from pathlib import Path
from typing import List, Tuple, Set

# ============= Configuration =============

# Packages to SKIP on Windows (require C++ build tools or Linux-only)
PROBLEMATIC_PACKAGES = {
    'chromadb',
    'chroma-hnswlib', 
    'webrtcvad',
    'uvloop',           # Linux only
    'piper-tts',        # Complex native deps
    'faster-whisper',   # Complex native deps
}

# Essential packages - will retry if batch fails
ESSENTIAL_PACKAGES = [
    'fastapi',
    'uvicorn',
    'pydantic',
    'python-dotenv',
    'PyJWT',
    'PyMuPDF',
    'requests',
    'aiohttp',
    'python-multipart',
]

# ============= Cross-Platform Print =============

def safe_print(text: str):
    """Print text safely on all platforms."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))

def print_header(text: str):
    safe_print(f"\n{'=' * 60}")
    safe_print(f"  {text}")
    safe_print(f"{'=' * 60}\n")

def print_ok(text: str):
    safe_print(f"  [OK] {text}")

def print_warn(text: str):
    safe_print(f"  [WARN] {text}")

def print_fail(text: str):
    safe_print(f"  [FAIL] {text}")

def print_info(text: str):
    safe_print(f"  -> {text}")

# ============= Utility Functions =============

def get_project_root() -> Path:
    return Path(__file__).parent.resolve()

def run_command(cmd: List[str], cwd: Path = None, timeout: int = 600) -> Tuple[bool, str]:
    """Run command and return (success, output)."""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

def check_environment() -> Tuple[bool, bool]:
    """Check Python and Node.js availability. Returns (has_python, has_node)."""
    print_header("Environment Check")
    
    # Python
    success, out = run_command([sys.executable, '--version'])
    if success:
        print_ok(f"Python: {out.strip()}")
    else:
        print_fail("Python not found!")
        return False, False
    
    # Node.js
    npm_cmd = 'npm.cmd' if sys.platform == 'win32' else 'npm'
    success, out = run_command([npm_cmd, '--version'])
    has_node = success
    if success:
        print_ok(f"npm: v{out.strip()}")
    else:
        print_warn("npm not found - frontend install will be skipped")
    
    return True, has_node

# ============= Backend Installation (Optimized) =============

def read_requirements(file_path: Path) -> List[str]:
    """Read requirements.txt, handling BOM and comments."""
    packages = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '#' in line:
                    line = line.split('#')[0].strip()
                if line:
                    packages.append(line)
    except FileNotFoundError:
        print_fail(f"File not found: {file_path}")
    return packages

def get_package_name(spec: str) -> str:
    """Extract package name from requirement spec."""
    for sep in ['==', '>=', '<=', '>', '<', '[', ';']:
        if sep in spec:
            return spec.split(sep)[0].strip()
    return spec.strip()

def filter_requirements(packages: List[str], skip_packages: Set[str]) -> Tuple[List[str], List[str]]:
    """Filter out problematic packages. Returns (filtered, skipped)."""
    filtered = []
    skipped = []
    for pkg in packages:
        name = get_package_name(pkg).lower()
        if name in {p.lower() for p in skip_packages}:
            skipped.append(name)
        else:
            filtered.append(pkg)
    return filtered, skipped

def install_backend_batch(root: Path, skip_problematic: bool = True) -> bool:
    """Install backend deps using optimized batch approach."""
    print_header("Installing Backend Dependencies")
    
    req_file = root / 'requirements.txt'
    if not req_file.exists():
        print_fail("requirements.txt not found!")
        return False
    
    packages = read_requirements(req_file)
    print_info(f"Found {len(packages)} packages")
    
    # Filter problematic packages
    if skip_problematic:
        packages, skipped = filter_requirements(packages, PROBLEMATIC_PACKAGES)
        if skipped:
            print_warn(f"Skipping {len(skipped)} problematic packages: {', '.join(skipped)}")
    
    # Create temporary filtered requirements file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp:
        tmp.write('\n'.join(packages))
        tmp_path = tmp.name
    
    try:
        # Batch install with optimizations
        print_info("Running batch pip install (this may take a few minutes)...")
        
        cmd = [
            sys.executable, '-m', 'pip', 'install',
            '-r', tmp_path,
            '--no-input',
            '--disable-pip-version-check',
            '-q'  # Quiet mode for speed
        ]
        
        start = time.time()
        success, output = run_command(cmd, timeout=600)
        elapsed = time.time() - start
        
        if success:
            print_ok(f"Batch install completed in {elapsed:.1f}s")
        else:
            print_warn(f"Batch install had issues after {elapsed:.1f}s")
            # Show last few lines of error
            lines = output.strip().split('\n')
            for line in lines[-5:]:
                if line.strip():
                    safe_print(f"    {line}")
        
        # Always try essential packages individually
        print_info("Verifying essential packages...")
        for pkg in ESSENTIAL_PACKAGES:
            try:
                # Quick check if installable
                subprocess.run(
                    [sys.executable, '-m', 'pip', 'install', pkg, '-q', '--no-input'],
                    capture_output=True, timeout=60
                )
            except:
                pass
        
        # Install Playwright browsers
        print_info("Installing Playwright browsers...")
        try:
            subprocess.run(
                [sys.executable, '-m', 'playwright', 'install', 'chromium'],
                capture_output=True, timeout=120
            )
        except Exception as e:
            print_warn(f"Playwright browser install failed: {e}")

        return True
        
    finally:
        # Cleanup temp file
        try:
            os.unlink(tmp_path)
        except:
            pass

# ============= Frontend Installation =============

def install_frontend(root: Path) -> bool:
    """Install frontend dependencies."""
    print_header("Installing Frontend Dependencies")
    
    frontend = root / 'frontend-react'
    if not frontend.exists():
        print_fail("frontend-react directory not found!")
        return False
    
    npm_cmd = 'npm.cmd' if sys.platform == 'win32' else 'npm'
    
    print_info("Running npm install...")
    start = time.time()
    
    try:
        result = subprocess.run(
            [npm_cmd, 'install', '--silent'],
            cwd=frontend,
            capture_output=True,
            text=True,
            timeout=300
        )
        elapsed = time.time() - start
        
        if result.returncode == 0:
            print_ok(f"Frontend installed in {elapsed:.1f}s")
            return True
        else:
            print_warn(f"npm install had issues")
            # Show errors
            if result.stderr:
                for line in result.stderr.split('\n')[-5:]:
                    if line.strip():
                        safe_print(f"    {line}")
            return False
            
    except subprocess.TimeoutExpired:
        print_fail("npm install timed out")
        return False
    except FileNotFoundError:
        print_fail("npm not found")
        return False

# ============= Parallel Installation =============

def install_all_parallel(root: Path, skip_problematic: bool = True, has_node: bool = True) -> Tuple[bool, bool]:
    """Install backend and frontend in parallel."""
    backend_ok = False
    frontend_ok = not has_node  # Mark OK if skipping
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Start both installations
        backend_future = executor.submit(install_backend_batch, root, skip_problematic)
        
        if has_node:
            frontend_future = executor.submit(install_frontend, root)
            frontend_ok = frontend_future.result()
        
        backend_ok = backend_future.result()
    
    return backend_ok, frontend_ok

# ============= Verification =============

def verify_installation() -> bool:
    """Verify critical packages are importable."""
    print_header("Verification")
    
    critical = ['fastapi', 'uvicorn', 'pydantic']
    all_ok = True
    
    for pkg in critical:
        try:
            __import__(pkg)
            print_ok(f"{pkg}")
        except ImportError:
            print_fail(f"{pkg} - NOT FOUND")
            all_ok = False
    
    # Optional packages
    optional = [('jwt', 'PyJWT'), ('fitz', 'PyMuPDF'), ('chromadb', 'ChromaDB')]
    for mod, name in optional:
        try:
            __import__(mod)
            print_ok(f"{name} (optional)")
        except ImportError:
            print_warn(f"{name} not installed (optional)")
    
    return all_ok

# ============= Main =============

def main():
    parser = argparse.ArgumentParser(description='Install Chirag Clone dependencies')
    parser.add_argument('--backend-only', action='store_true')
    parser.add_argument('--frontend-only', action='store_true')
    parser.add_argument('--force-all', action='store_true', help='Try all packages including problematic ones')
    args = parser.parse_args()
    
    safe_print("""
    ============================================================
    |     Chirag Clone - Optimized Dependency Installer        |
    ============================================================
    """)
    
    root = get_project_root()
    print_info(f"Project: {root}")
    
    start_time = time.time()
    
    # Environment check
    has_python, has_node = check_environment()
    if not has_python:
        return 1
    
    skip_problematic = not args.force_all
    backend_ok = True
    frontend_ok = True
    
    # Installation
    if args.frontend_only:
        frontend_ok = install_frontend(root)
    elif args.backend_only:
        backend_ok = install_backend_batch(root, skip_problematic)
    else:
        # Parallel installation (fastest)
        backend_ok, frontend_ok = install_all_parallel(root, skip_problematic, has_node)
    
    # Verify
    verified = verify_installation()
    
    # Summary
    elapsed = time.time() - start_time
    print_header("Complete")
    print_info(f"Time: {elapsed:.1f} seconds")
    
    if backend_ok and frontend_ok and verified:
        print_ok("All dependencies installed!")
        safe_print("""
    Next steps:
      1. Backend:  cd backend && python -m uvicorn main:app --reload
      2. Frontend: cd frontend-react && npm run dev
      3. Open:     http://localhost:5173
        """)
        return 0
    else:
        print_warn("Some issues occurred - app may still work with mock services")
        return 1

if __name__ == '__main__':
    sys.exit(main())
