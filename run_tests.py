#!/usr/bin/env python3
"""
Test runner for AgentDiff Coordination

Simple script to run the core tests.
"""

import sys
import subprocess
from pathlib import Path

def main():
    """Run the test suite"""
    print("🧪 Running AgentDiff Coordination Tests")
    print("=" * 50)
    
    # Change to project root
    project_root = Path(__file__).parent
    
    # Run pytest with common options
    cmd = [
        sys.executable, "-m", "pytest", 
        "tests/",
        "-v",                    # Verbose output
        "--tb=short",           # Shorter traceback format  
        "--strict-markers",     # Strict marker checking
        "--disable-warnings",   # Less noise
    ]
    
    try:
        result = subprocess.run(cmd, cwd=project_root, check=True)
        print("\n✅ All tests passed!")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code {e.returncode}")
        return e.returncode
    except FileNotFoundError:
        print("❌ pytest not found. Install with: pip install pytest")
        return 1

if __name__ == "__main__":
    sys.exit(main())