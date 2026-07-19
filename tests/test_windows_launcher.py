import sys
from pathlib import Path

from scripts.windows_launcher import _ensure_output_streams


def test_missing_console_streams_are_replaced_by_log_file(tmp_path: Path) -> None:
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    stream = None
    try:
        sys.stdout = None
        sys.stderr = None

        stream = _ensure_output_streams(tmp_path)

        assert stream is not None
        assert sys.stdout is stream
        assert sys.stderr is stream
        assert stream.isatty() is False
        stream.write("launcher smoke test\n")
        stream.flush()
        assert (tmp_path / "logs" / "bridge.log").read_text(encoding="utf-8").endswith(
            "launcher smoke test\n"
        )
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        if stream is not None:
            stream.close()


def test_existing_console_streams_are_kept(tmp_path: Path) -> None:
    assert _ensure_output_streams(tmp_path) is None
    assert not (tmp_path / "logs").exists()
