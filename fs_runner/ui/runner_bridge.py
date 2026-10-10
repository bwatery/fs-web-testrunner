# -*- coding: utf-8 -*-
"""
fs_runner.ui.runner_bridge
==========================
负责与新引擎命令行执行器交互：
1. 真实起子进程（python -I fsrun.py run ...）
2. 捕获 stdout 实时广播日志与步骤
3. 真实停止进程（taskkill 杀进程树）
4. 统一维护当前执行状态与进度
"""
import asyncio
import os
import re
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent.parent


class RunnerBridge:
    """管理测试子进程生命周期与实时事件。"""

    def __init__(self):
        self.lock = threading.Lock()
        self.running: bool = False
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.current_case: Optional[str] = None
        self.current_index: int = 0
        self.total_cases: int = 0
        self.current_step: str = "空闲"
        self.logs: deque = deque(maxlen=3000)
        self.results_cache: Dict[str, Dict[str, Any]] = {}
        self.started_at: Optional[str] = None
        self.env: str = "real"
        self.show_browser: bool = False
        self.slowmo: int = 0
        self.listeners: List[asyncio.Queue] = []

    def get_status(self) -> Dict[str, Any]:
        """获取当前执行快照。"""
        with self.lock:
            percent = 0
            if self.total_cases > 0:
                percent = int((self.current_index / self.total_cases) * 100)
            return {
                "running": self.running,
                "pid": self.pid,
                "current_case": self.current_case,
                "current_index": self.current_index,
                "total_cases": self.total_cases,
                "percent": percent,
                "current_step": self.current_step,
                "started_at": self.started_at,
                "env": self.env,
                "show_browser": self.show_browser,
                "slowmo": self.slowmo,
                "results_count": len(self.results_cache),
            }

    def get_recent_logs(self, limit: int = 500) -> List[str]:
        """获取最近日志行。"""
        with self.lock:
            return list(self.logs)[-limit:]

    def register_listener(self) -> asyncio.Queue:
        """注册一个实时事件队列。"""
        q = asyncio.Queue()
        with self.lock:
            self.listeners.append(q)
        return q

    def unregister_listener(self, q: asyncio.Queue):
        """移除实时事件队列。"""
        with self.lock:
            if q in self.listeners:
                self.listeners.remove(q)

    def _broadcast(self, msg_type: str, data: Any):
        """线程安全广播事件给监听队列。"""
        payload = {"type": msg_type, "data": data, "ts": time.time()}
        with self.lock:
            for q in list(self.listeners):
                try:
                    q.put_nowait(payload)
                except Exception:
                    pass

    def start_run(
        self,
        cases: Optional[List[str]] = None,
        env: str = "real",
        show_browser: bool = False,
        slowmo: int = 0,
        is_ui_verify: bool = False,
    ) -> Tuple[bool, str]:
        """
        启动测试子进程。
        """
        with self.lock:
            if self.running:
                return False, f"已有测试任务正在运行中 (PID: {self.pid})"

            self.running = True
            self.current_case = None
            self.current_index = 0
            self.total_cases = len(cases) if cases else (66 if not is_ui_verify else 4)
            self.current_step = "正在启动测试进程..."
            self.logs.clear()
            self.results_cache.clear()
            self.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
            self.env = env
            self.show_browser = show_browser
            self.slowmo = slowmo

        # 构造执行命令
        cmd = [sys.executable, "-I", "fsrun.py"]
        # 若勾选了「显示浏览器」且针对 L6-039 或 UI 巡检，自动路由到 ui-verify 启动可见 Chrome
        if (show_browser and (cases and any("039" in c for c in cases))) or is_ui_verify:
            is_ui_verify = True
            cmd.extend(["ui-verify"])
            if show_browser:
                cmd.append("--standalone")
            else:
                cmd.append("--headless")
            cmd.append("--screenshot")
            if slowmo > 0:
                cmd.extend(["--slowmo", str(slowmo)])
            if env == "sandbox":
                cmd.extend(["--env", "sandbox"])
        else:
            cmd.extend(["run", "--suite", "closed-loop"])
            if cases:
                cmd.extend(["--cases", ",".join(cases)])
            if env == "sandbox":
                cmd.extend(["--env", "sandbox"])

        # 环境变量注入：若用户开启「显示浏览器」，注入 FS_STANDALONE_BROWSER=1
        env_vars = os.environ.copy()
        if show_browser:
            env_vars["FS_STANDALONE_BROWSER"] = "1"
        if slowmo > 0:
            env_vars["FS_SLOWMO"] = str(slowmo)

        try:
            p = subprocess.Popen(
                cmd,
                cwd=str(_ROOT),
                env=env_vars,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
            )
            with self.lock:
                self.process = p
                self.pid = p.pid

            threading.Thread(target=self._reader_thread, args=(p,), daemon=True).start()
            return True, f"测试进程已启动 (PID: {p.pid})"
        except Exception as e:
            with self.lock:
                self.running = False
                self.process = None
                self.pid = None
            return False, f"拉起测试进程失败: {e}"

    def _reader_thread(self, proc: subprocess.Popen):
        """后台线程：逐行读取子进程 stdout。"""
        re_progress = re.compile(r"\[(\d+)/(\d+)\]\s+(L\d+-\d+|UI-[\w-]+)\s+(.*?)\s+——\s+(通过|失败|阻塞|跳过|未执行)")
        re_ui_prog = re.compile(r"\[(UI-[\w-]+)\]\s+——\s+(通过|失败|阻塞|跳过|未执行)")
        re_step = re.compile(r"▶\s+正在执行\s+\[(.*?)\]\s+(.*)")
        re_substep = re.compile(r"\[步骤\]\s+(.*)")

        try:
            for line in proc.stdout:
                line_str = line.rstrip()
                with self.lock:
                    self.logs.append(line_str)

                # 解析进度与结果
                m_prog = re_progress.search(line_str)
                m_ui = re_ui_prog.search(line_str)
                m_sub = re_substep.search(line_str)
                m_st = re_step.search(line_str)

                if m_prog:
                    idx = int(m_prog.group(1))
                    tot = int(m_prog.group(2))
                    cid = m_prog.group(3)
                    title = m_prog.group(4).strip()
                    status = m_prog.group(5).strip()

                    with self.lock:
                        self.current_index = idx
                        self.total_cases = tot
                        self.current_case = cid
                        self.current_step = f"已完成 {cid} {title}（{status}）"
                        self.results_cache[cid] = {
                            "case_id": cid,
                            "title": title,
                            "status": status,
                        }

                    self._broadcast("case_result", {
                        "case_id": cid,
                        "title": title,
                        "status": status,
                        "current_index": idx,
                        "total_cases": tot,
                    })
                elif m_ui:
                    cid = m_ui.group(1)
                    status = m_ui.group(2)
                    with self.lock:
                        self.current_index += 1
                        self.current_case = cid
                        self.current_step = f"已完成 {cid}（{status}）"
                        self.results_cache[cid] = {
                            "case_id": cid,
                            "title": cid,
                            "status": status,
                        }
                    self._broadcast("case_result", {
                        "case_id": cid,
                        "title": cid,
                        "status": status,
                        "current_index": self.current_index,
                        "total_cases": self.total_cases,
                    })
                elif m_sub:
                    desc = m_sub.group(1).strip()
                    with self.lock:
                        self.current_step = desc
                    self._broadcast("step", {"case_id": self.current_case or "UI", "step": desc})
                elif m_st:
                    cid = m_st.group(1).strip()
                    desc = m_st.group(2).strip()
                    with self.lock:
                        self.current_case = cid
                        self.current_step = f"正在执行 {cid}: {desc}"
                    self._broadcast("step", {"case_id": cid, "step": desc})

                # 广播单行日志
                self._broadcast("log", line_str)

            proc.wait()
            ret = proc.returncode
            end_msg = f"测试执行结束，退出码: {ret}"
            with self.lock:
                self.logs.append(end_msg)
                self.current_step = "已执行完成"
            self._broadcast("log", end_msg)
            self._broadcast("finished", {"returncode": ret})
        finally:
            with self.lock:
                self.running = False
                self.process = None
                self.pid = None

    def stop_run(self) -> Tuple[bool, str]:
        """
        杀死正在运行的测试子进程树。
        """
        with self.lock:
            if not self.running or not self.process:
                return False, "当前无正在运行的测试进程"
            pid = self.pid
            p = self.process

        try:
            # 在 Windows 下使用 taskkill /F /T /PID 强制杀掉整个进程树
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                p.terminate()
                p.kill()
        except Exception as e:
            print(f"[runner_bridge] 终止进程异常: {e}")

        stop_msg = f"⏹️ [用户中断] 测试执行已被人工终止 (PID: {pid})"
        with self.lock:
            self.running = False
            self.process = None
            self.pid = None
            self.current_step = "已人工停止"
            self.logs.append(stop_msg)

        self._broadcast("log", stop_msg)
        self._broadcast("finished", {"returncode": -1, "stopped": True})
        return True, f"测试进程已成功终止 (PID: {pid})"


runner_bridge = RunnerBridge()
