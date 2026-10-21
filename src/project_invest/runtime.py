from __future__ import annotations

import argparse
import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

import uvicorn

from project_invest.config import settings
from project_invest.container import build_container
from project_invest.services.universe import resolve_symbols
from project_invest.services.worker import (
    BackgroundResearchWorker,
    BackgroundTradingWorker,
)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Project Invest runtime entrypoints.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    api_parser = subparsers.add_parser("api", help="Run the FastAPI control center.")
    api_parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    api_parser.add_argument("--port", default=int(os.getenv("PORT", "8000")), type=int)
    api_parser.add_argument("--reload", action="store_true")
    api_parser.add_argument(
        "--public",
        action="store_true",
        help="Expose the local dashboard through cloudflared in the same command.",
    )

    run_once_parser = subparsers.add_parser("run-once", help="Execute one research cycle.")
    run_once_parser.add_argument("--symbols", nargs="*", default=None)

    trade_once_parser = subparsers.add_parser("trade-once", help="Execute one trading cycle.")
    trade_once_parser.add_argument("--symbols", nargs="*", default=None)

    launch_parser = subparsers.add_parser(
        "launch",
        help="Start the API, research worker, and trading worker together from one command.",
    )
    launch_parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    launch_parser.add_argument("--port", default=int(os.getenv("PORT", "8000")), type=int)
    launch_parser.add_argument(
        "--public",
        action="store_true",
        help="Also expose the local dashboard through cloudflared.",
    )

    worker_parser = subparsers.add_parser("worker", help="Run one continuous research-only or paper-trading loop.")
    worker_parser.add_argument("--symbols", nargs="*", default=None)
    worker_parser.add_argument("--interval-seconds", type=int, default=None)
    worker_parser.add_argument("--mode", choices=["research", "trading"], default="research")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "api":
        run_api(host=args.host, port=args.port, reload=args.reload, public=args.public)
        return

    if args.command == "run-once":
        asyncio.run(run_once(args.symbols))
        return

    if args.command == "trade-once":
        asyncio.run(run_trade_once(args.symbols))
        return

    if args.command == "launch":
        launch_stack(host=args.host, port=args.port, public=args.public)
        return

    if args.command == "worker":
        asyncio.run(run_worker(args.symbols, args.interval_seconds, args.mode))


def run_api(host: str, port: int, reload: bool = False, public: bool = False) -> None:
    tunnel_process: subprocess.Popen[str] | None = None
    try:
        if public:
            if reload:
                raise RuntimeError("The public tunnel launcher does not support --reload. Start without reload.")
            tunnel_process = _spawn_cloudflared_tunnel(port)

        uvicorn.run("project_invest.api.app:app", host=host, port=port, reload=reload)
    finally:
        _stop_process(tunnel_process)


def launch_stack(host: str, port: int, public: bool = False) -> None:
    python_executable = sys.executable
    project_root = Path.cwd()
    launch_env = _build_launch_env(project_root)
    runtime_env = {
        **launch_env,
        "PROJECT_INVEST_RESEARCH_LOOP_ENABLED": "false",
        "PROJECT_INVEST_TRADING_LOOP_ENABLED": "false",
        "PROJECT_INVEST_LIVE_LOOP_ENABLED": "false",
    }

    processes: list[subprocess.Popen[str]] = []
    try:
        api_process = subprocess.Popen(
            [python_executable, "-m", "project_invest", "api", "--host", host, "--port", str(port)],
            env=runtime_env,
            cwd=str(project_root),
        )
        processes.append(api_process)

        processes.append(
            subprocess.Popen(
                [python_executable, "-m", "project_invest", "worker", "--mode", "research"],
                env=runtime_env,
                cwd=str(project_root),
            )
        )
        processes.append(
            subprocess.Popen(
                [python_executable, "-m", "project_invest", "worker", "--mode", "trading"],
                env=runtime_env,
                cwd=str(project_root),
            )
        )

        _wait_for_port("127.0.0.1", port, timeout_seconds=25.0)

        if public:
            processes.append(_spawn_cloudflared_tunnel(port))

        print(f"Project Invest stack is live at http://127.0.0.1:{port}/")
        print("Standalone research and paper-trading workers are enabled in this launch mode.")
        if public:
            print("Cloudflared quick tunnel is starting in this same console output.")

        while True:
            for process in processes:
                if process.poll() is not None:
                    raise RuntimeError(f"One of the stack processes exited early with code {process.returncode}.")
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        for process in reversed(processes):
            _stop_process(process)


async def run_once(symbols: list[str] | None = None) -> None:
    container = build_container(settings)
    try:
        await container.research_lab.run_cycle(symbols or None, execute_trades=False)
    finally:
        container.close()


async def run_trade_once(symbols: list[str] | None = None) -> None:
    container = build_container(settings)
    try:
        await container.trading_lab.run_cycle(symbols or None)
    finally:
        container.close()


async def run_worker(
    symbols: list[str] | None = None,
    interval_seconds: int | None = None,
    mode: str = "research",
) -> None:
    container = build_container(settings)
    resolved_symbols = symbols or resolve_symbols(
        settings.research_symbols,
        settings.use_market_universes,
        settings.market_universes,
    )
    if mode == "trading":
        effective_interval = interval_seconds or settings.trading_loop_seconds
        worker = BackgroundTradingWorker(
            trading_lab=container.trading_lab,
            interval_seconds=effective_interval,
            symbols=resolved_symbols,
        )
    else:
        effective_interval = interval_seconds or settings.research_loop_seconds
        worker = BackgroundResearchWorker(
            research_lab=container.research_lab,
            interval_seconds=effective_interval,
            symbols=resolved_symbols,
            execute_trades=False,
        )
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    try:
        await worker.start()
        await stop_event.wait()
    finally:
        await worker.stop()
        container.close()


def _build_launch_env(project_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    src_path = str(project_root / "src")
    existing = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def _spawn_cloudflared_tunnel(port: int) -> subprocess.Popen[str]:
    try:
        return subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"],
            cwd=str(Path.cwd()),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "cloudflared is not installed or not on PATH. Install it first to use --public."
        ) from exc


def _wait_for_port(host: str, port: int, timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with suppress(OSError):
            with socket.create_connection((host, port), timeout=1.0):
                return
        time.sleep(0.2)
    raise TimeoutError(f"Timed out waiting for {host}:{port} to accept connections.")


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        process.kill()
        with suppress(subprocess.TimeoutExpired):
            process.wait(timeout=2)
