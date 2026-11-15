"""Profile a local Python 3.15 PyChess server without manual PID lookup.

From the repository root, run `python3.15 scripts/profile_local_server.py`.
If no server is running, this starts a disposable *test-user-mode* local server.
The profiler attaches to the server, never the stress-test client process.
"""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server" / "server.py"


def find_local_server_pids(root: Path = ROOT, proc: Path = Path("/proc")) -> list[int]:
    """Select only processes executing this checkout's server/server.py."""
    expected = (root / "server" / "server.py").resolve()
    pids: list[int] = []
    for entry in proc.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            command = (entry / "cmdline").read_bytes().split(b"\0")
            cwd = (entry / "cwd").resolve(strict=True)
            if any(
                arg and (cwd / os.fsdecode(arg)).resolve() == expected
                for arg in command[1:]
                if arg.endswith(b"server.py")
            ):
                pids.append(int(entry.name))
        except (OSError, ValueError):  # fmt: skip
            continue  # Unrelated process, or process terminated while scanning.
    return sorted(pids)


def is_test_user_server(pid: int, proc: Path = Path("/proc")) -> bool:
    """Whether the target server was started with -a test-user mode."""
    arguments = (proc / str(pid) / "cmdline").read_bytes().split(b"\0")
    return b"-a" in arguments


def ensure_local_mode() -> str:
    uri = os.getenv("URI", "http://127.0.0.1:8080")
    parsed = urlsplit(uri)
    if os.getenv("PROD") == "true" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Refusing to profile/start a non-local or PROD server.")
    if sys.version_info[:2] != (3, 15):
        raise SystemExit(f"Run with Python 3.15, not {sys.version.split()[0]}.")
    return uri


def assert_python315_process(pid: int) -> None:
    version = subprocess.run(
        [f"/proc/{pid}/exe", "--version"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not version.startswith("Python 3.15."):
        raise RuntimeError(f"Server PID {pid} uses {version}, not Python 3.15")


def wait_until_ready(server: subprocess.Popen[bytes], uri: str, timeout: float = 60.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(f"Server exited during startup (code {server.returncode}).")
        try:
            with urlopen(uri, timeout=1) as response:
                response.read(64)
            return
        except (OSError, URLError):  # fmt: skip
            time.sleep(0.4)
    raise RuntimeError(f"Local server did not become ready at {uri} within {timeout:g}s")


def stop_server(server: subprocess.Popen[bytes] | None) -> None:
    if server is None or server.poll() is not None:
        return
    try:
        os.killpg(server.pid, signal.SIGINT)
    except ProcessLookupError:
        return
    try:
        server.wait(timeout=12)
    except subprocess.TimeoutExpired:
        os.killpg(server.pid, signal.SIGTERM)
        server.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=120, help="Sampling duration in seconds")
    parser.add_argument(
        "--output", type=Path, help="Output Gecko JSON (default: private /tmp directory)"
    )
    parser.add_argument(
        "--attach-only", action="store_true", help="Fail instead of starting a local server"
    )
    parser.add_argument(
        "--no-sudo", action="store_true", help="Attach without sudo if ptrace permissions allow"
    )
    args = parser.parse_args(argv)
    if args.duration < 1:
        parser.error("--duration must be positive")
    uri = ensure_local_mode()
    output = args.output or (Path(tempfile.mkdtemp(prefix="pychess-tachyon-")) / "timeline.json")
    output = output.expanduser().absolute()
    snapshot_output = output.with_name("event-loop-lag.json")
    launched: subprocess.Popen[bytes] | None = None
    started = False
    try:
        if output.exists():
            raise RuntimeError(f"Refusing to overwrite existing profile: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        # A snapshot from an older run must never be mistaken for this capture.
        if snapshot_output.exists():
            raise RuntimeError(f"Refusing to overwrite existing lag snapshot: {snapshot_output}")
        pids = find_local_server_pids()
        if len(pids) > 1:
            raise RuntimeError(
                f"Multiple PyChess servers in this checkout: {pids}; stop the extras."
            )
        if pids:
            pid = pids[0]
            print(f"Attaching to existing local server PID {pid}.", flush=True)
            if not is_test_user_server(pid):
                raise RuntimeError(
                    "This server was not started with -a test-user mode. "
                    "Restart locally with: PYCHESS_LOOP_LAG_ENABLED=1 "
                    "python3.15 server/server.py -a"
                )
            print("Make sure PYCHESS_LOOP_LAG_ENABLED=1 was set when it started.", flush=True)
            print(
                "Automatic final lag snapshots require a server started by this helper; "
                "an already-running server cannot inherit the output setting.",
                flush=True,
            )
        else:
            if args.attach_only:
                raise RuntimeError("No PyChess server is running in this checkout.")
            mongo_uri = os.getenv("MONGO_HOST", "mongodb://127.0.0.1:27017")
            mongo = urlsplit(mongo_uri)
            if (
                mongo.scheme != "mongodb"
                or mongo.hostname not in {"localhost", "127.0.0.1", "::1"}
                or "," in mongo.netloc
            ):
                raise RuntimeError(
                    "Auto-start is restricted to a local MongoDB. "
                    "Start your development server manually and rerun to attach."
                )
            parsed = urlsplit(uri)
            try:
                with socket.create_connection((parsed.hostname, parsed.port or 8080), timeout=1):
                    raise RuntimeError(f"Port for {uri} is already occupied by another process.")
            except OSError:
                pass  # Not listening yet.
            print(
                "Starting local server in test-user mode (-a), with loop-lag monitoring.",
                flush=True,
            )
            env = dict(
                os.environ,
                PYCHESS_LOOP_LAG_ENABLED="1",
                PYCHESS_LOOP_LAG_SNAPSHOT_PATH=str(snapshot_output),
            )
            launched = subprocess.Popen(
                [sys.executable, str(SERVER), "-a"],
                cwd=ROOT,
                env=env,
                start_new_session=True,
            )
            pid = launched.pid
            wait_until_ready(launched, uri)
            started = True
        assert_python315_process(pid)
        cmd = [
            sys.executable,
            "-m",
            "profiling.sampling",
            "attach",
            "--gecko",
            "-d",
            str(args.duration),
            "-o",
            str(output),
            str(pid),
        ]
        if not args.no_sudo:
            cmd.insert(0, "sudo")
        if not args.no_sudo:
            # Prompt for sudo before inviting the user to start the workload.
            subprocess.run(["sudo", "-v"], check=True)
        print(
            f"Sampling server PID {pid} for {args.duration}s; start the stress test now.\n"
            f"Timeline (written after sampling finishes): {output}",
            flush=True,
        )
        if launched is not None:
            print(
                f"Final event-loop lag snapshot (written on shutdown): {snapshot_output}",
                flush=True,
            )
        result = subprocess.run(cmd, check=False)
        if output.is_file() and not args.no_sudo:
            subprocess.run(
                ["sudo", "chown", f"{os.getuid()}:{os.getgid()}", str(output)], check=True
            )
        if result.returncode != 0:
            raise RuntimeError(f"Tachyon exited with status {result.returncode}")
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Tachyon reported success but did not write a profile: {output}")
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Profiling failed: {exc}", file=sys.stderr)
        return 1
    finally:
        stop_server(launched)
        if started:
            if snapshot_output.is_file() and snapshot_output.stat().st_size:
                print(f"Event-loop lag snapshot: {snapshot_output}", flush=True)
            else:
                print(
                    f"WARNING: no shutdown lag snapshot was saved at {snapshot_output}",
                    file=sys.stderr,
                )
    print(f"Profile: {output}\nLoad in https://profiler.firefox.com/", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
