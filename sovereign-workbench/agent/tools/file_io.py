"""
Workspace File I/O Tool for Karyalaya AI.
Strictly scoped to sovereign-workbench/workspace/ directory.
Prevents path traversal outside the workspace folder.
"""

import os
from typing import Dict, Any, List

WORKSPACE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "workspace")
)

def _resolve_safe_path(relative_or_abs_path: str) -> str:
    """Ensures target path stays strictly inside WORKSPACE_DIR."""
    if os.path.isabs(relative_or_abs_path):
        target = os.path.abspath(relative_or_abs_path)
    else:
        target = os.path.abspath(os.path.join(WORKSPACE_DIR, relative_or_abs_path))

    if not target.startswith(WORKSPACE_DIR):
        raise PermissionError(f"Access denied: Path '{relative_or_abs_path}' is outside designated workspace directory '{WORKSPACE_DIR}'.")
    return target


def read_workspace_file(file_path: str) -> Dict[str, Any]:
    """Reads content of a text file inside workspace."""
    try:
        safe_path = _resolve_safe_path(file_path)
        if not os.path.exists(safe_path):
            return {"status": "error", "error": f"File not found: {file_path}"}
        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"status": "success", "content": content, "path": safe_path}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def write_workspace_file(file_path: str, content: str) -> Dict[str, Any]:
    """Writes text content to a file inside workspace."""
    try:
        safe_path = _resolve_safe_path(file_path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"status": "success", "message": f"Successfully wrote {len(content)} characters to {file_path}", "path": safe_path}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def list_workspace_files(subfolder: str = "") -> Dict[str, Any]:
    """Lists files in the workspace or subfolder."""
    try:
        target_dir = _resolve_safe_path(subfolder) if subfolder else WORKSPACE_DIR
        if not os.path.exists(target_dir):
            return {"status": "error", "error": f"Folder not found: {subfolder}"}

        file_list: List[str] = []
        for root, _, files in os.walk(target_dir):
            for file in files:
                if file.startswith("."):
                    continue
                rel_path = os.path.relpath(os.path.join(root, file), WORKSPACE_DIR)
                file_list.append(rel_path)

        return {"status": "success", "files": file_list}
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    # Quick self-test
    print("Workspace dir:", WORKSPACE_DIR)
    w_res = write_workspace_file("sops/test.txt", "Sample SOP Content")
    print("Write res:", w_res)
    r_res = read_workspace_file("sops/test.txt")
    print("Read res:", r_res)
    l_res = list_workspace_files()
    print("List res:", l_res)
