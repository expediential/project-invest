from __future__ import annotations

import os
from pathlib import Path

from project_invest import runtime


def test_build_launch_env_prepends_src(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PYTHONPATH", "existing_path")

    env = runtime._build_launch_env(tmp_path)

    assert env["PYTHONPATH"].split(os.pathsep)[0].endswith("src")
    assert "existing_path" in env["PYTHONPATH"]


def test_run_api_with_public_tunnel_starts_and_stops_tunnel(monkeypatch) -> None:
    calls: list[str] = []

    class DummyProcess:
        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    dummy_process = DummyProcess()

    monkeypatch.setattr(runtime, "_spawn_cloudflared_tunnel", lambda port: calls.append(f"spawn:{port}") or dummy_process)
    monkeypatch.setattr(runtime.uvicorn, "run", lambda *args, **kwargs: calls.append("uvicorn"))
    monkeypatch.setattr(runtime, "_stop_process", lambda process: calls.append("stop"))

    runtime.run_api(host="0.0.0.0", port=8000, reload=False, public=True)

    assert calls == ["spawn:8000", "uvicorn", "stop"]


def test_launch_stack_starts_separate_api_and_worker_processes(monkeypatch, tmp_path: Path) -> None:
    spawned: list[list[str]] = []
    spawned_envs: list[dict[str, str] | None] = []

    class DummyProcess:
        def __init__(self, command: list[str]) -> None:
            self.command = command
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def kill(self):
            self.returncode = -9

    def fake_popen(command, env=None, cwd=None):
        spawned.append(command)
        spawned_envs.append(env)
        return DummyProcess(command)

    monkeypatch.setattr(runtime.Path, "cwd", lambda: tmp_path)
    monkeypatch.setattr(runtime.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(runtime, "_wait_for_port", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime.time, "sleep", lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))

    runtime.launch_stack(host="0.0.0.0", port=8000, public=False)

    assert len(spawned) == 3
    assert spawned[0][2] == "project_invest"
    assert spawned[0][3] == "api"
    assert spawned[1][-2:] == ["--mode", "research"]
    assert spawned[2][-2:] == ["--mode", "trading"]
    assert spawned_envs[0]["PROJECT_INVEST_RESEARCH_LOOP_ENABLED"] == "false"
    assert spawned_envs[0]["PROJECT_INVEST_TRADING_LOOP_ENABLED"] == "false"
