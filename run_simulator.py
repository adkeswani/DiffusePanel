"""
Launch script for the DiffusePanel LED Simulator.
Run from the project root: python run_simulator.py
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    root = os.path.dirname(os.path.abspath(__file__))
    sys.exit(subprocess.call(
        [sys.executable, os.path.join(root, "simulator", "main.py")],
        cwd=root
    ))
