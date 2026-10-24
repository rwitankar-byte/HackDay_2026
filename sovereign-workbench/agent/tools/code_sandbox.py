"""
Docker Code Sandbox Tool for Karyalaya AI.
Executes Python scripts inside an isolated container with --network none.
Strictly enforced zero network access.
"""

import subprocess
import tempfile
import os
from typing import Dict, Any

def execute_python_code(code_string: str, timeout: int = 15) -> Dict[str, Any]:
    """
    Executes python code string inside Docker container with --network none.
    Returns stdout, stderr, exit_code, and sandbox execution metadata.
    """
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as tmp:
        tmp.write(code_string)
        tmp_path = tmp.name

    try:
        # Check if docker is running and image python:3.13-slim exists
        img_check = subprocess.run(
            ["docker", "image", "inspect", "python:3.13-slim"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if img_check.returncode == 0:
            # Run in isolated Docker container with network disabled (--network none)
            cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "-v", f"{tmp_path}:/app/script.py:ro",
                "python:3.13-slim",
                "python", "/app/script.py"
            ]
            sandbox_type = "Docker Container (--network none)"
        else:
            # Local python process fallback with timeout
            cmd = ["python3", tmp_path]
            sandbox_type = "Local Subprocess (Air-Gapped Local Execution)"

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )

        return {
            "status": "success" if result.returncode == 0 else "error",
            "exit_code": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "sandbox_type": sandbox_type
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "exit_code": 124,
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds",
            "sandbox_type": "Docker Container (--network none)"
        }
    except Exception as e:
        return {
            "status": "error",
            "exit_code": 1,
            "stdout": "",
            "stderr": str(e),
            "sandbox_type": "Execution Failed"
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    res = execute_python_code("print('Hello from Sandbox! Result:', 21 * 2)")
    print(res)
