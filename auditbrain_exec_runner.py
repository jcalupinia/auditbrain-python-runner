import contextlib
import io
import json
import os
import sys
from pathlib import Path


PUBLISHABLE_EXTENSIONS = {
    ".csv", ".doc", ".docx", ".html", ".json", ".pdf", ".png", ".ppt", ".pptx",
    ".svg", ".txt", ".xls", ".xlsx", ".zip"
}
MAX_STREAM_CHARS = int(os.getenv("AUDITBRAIN_MAX_STREAM_CHARS", "200000"))


def _snapshot_publishable_files(base_dir: Path):
    snapshots = {}
    for entry in base_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix.lower() in PUBLISHABLE_EXTENSIONS:
            snapshots[str(entry.resolve())] = entry.stat().st_mtime
    return snapshots


def _namespace_file_candidates(exec_namespace):
    candidates = []
    for value in exec_namespace.values():
        if not isinstance(value, str):
            continue
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        if path.is_file() and path.suffix.lower() in PUBLISHABLE_EXTENSIONS:
            candidates.append(str(path))
    return candidates


def _truncate_stream(value: str) -> str:
    if len(value) <= MAX_STREAM_CHARS:
        return value
    return value[:MAX_STREAM_CHARS] + "\n...[truncated]"


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: auditbrain_exec_runner.py <payload_path> <output_path>")

    payload_path = Path(sys.argv[1]).resolve()
    output_path = Path(sys.argv[2]).resolve()
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    code = payload.get("code", "")
    inputs = payload.get("inputs", {})

    before_snapshot = _snapshot_publishable_files(Path.cwd())
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    exec_namespace = {
        "__builtins__": __builtins__,
        "__name__": "__main__",
        "inputs": inputs,
    }

    result_payload = {
        "stdout": "",
        "stderr": "",
        "result": None,
        "generated_paths": [],
    }

    try:
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            exec(code, exec_namespace, exec_namespace)

        after_snapshot = _snapshot_publishable_files(Path.cwd())
        generated_paths = []
        for path, mtime in after_snapshot.items():
            if path not in before_snapshot or before_snapshot[path] != mtime:
                generated_paths.append(path)
        for path in _namespace_file_candidates(exec_namespace):
            if path not in generated_paths:
                generated_paths.append(path)

        result_payload.update({
            "stdout": _truncate_stream(stdout_buffer.getvalue()),
            "stderr": _truncate_stream(stderr_buffer.getvalue()),
            "result": exec_namespace.get("result"),
            "generated_paths": generated_paths,
        })
    except Exception as exc:
        result_payload.update({
            "stdout": _truncate_stream(stdout_buffer.getvalue()),
            "stderr": _truncate_stream(stderr_buffer.getvalue()),
            "error": str(exc),
            "traceback": _truncate_stream(__import__("traceback").format_exc()),
        })

    output_path.write_text(json.dumps(result_payload, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
