"""
測試伺服器管理模組

負責啟動、監控和關閉測試用的 FastAPI 伺服器。
使用 subprocess 方式啟動獨立進程，提供完整的生命週期管理。
"""
import logging
import subprocess
import sys
import time
import os
import socket
import tempfile
from pathlib import Path
from typing import Optional
import requests

from .config import config

logger = logging.getLogger(__name__)


class ServerStartupError(Exception):
    """伺服器啟動失敗異常"""
    pass


class ServerManager:
    """測試伺服器管理器

    負責啟動 uvicorn 伺服器進程、健康檢查、日誌捕獲和優雅關閉。
    """

    def __init__(self, project_root: Path):
        """初始化伺服器管理器

        Args:
            project_root: 專案根目錄路徑
        """
        self.project_root = project_root
        self.process: Optional[subprocess.Popen] = None
        self.log_file: Optional[Path] = None
        self._log_handle = None

    def start(self) -> str:
        """啟動測試伺服器

        Returns:
            伺服器的 base URL (e.g., "http://127.0.0.1:8088")

        Raises:
            ServerStartupError: 伺服器啟動失敗
        """
        logger.info("=" * 80)
        logger.info("啟動測試伺服器")
        logger.info("=" * 80)

        # 檢查 port 是否可用
        self._check_port_available()

        # 準備環境變數
        env = self._prepare_environment()

        # 準備日誌檔案
        if config.CAPTURE_SERVER_LOGS:
            self._prepare_log_file()

        # 啟動伺服器進程
        self._start_process(env)

        # 健康檢查
        self._wait_for_server()

        base_url = config.get_base_url()
        logger.info("=" * 80)
        logger.info(f"✓ 測試伺服器已啟動: {base_url}")
        logger.info(f"  - PID: {self.process.pid}")
        if self.log_file:
            logger.info(f"  - 日誌檔案: {self.log_file}")
        logger.info("=" * 80)

        return base_url

    def stop(self) -> None:
        """停止測試伺服器"""
        if not self.process:
            return

        logger.info("正在關閉測試伺服器...")

        try:
            # 嘗試優雅關閉
            self.process.terminate()
            logger.info(f"發送 SIGTERM 給進程 {self.process.pid}")

            # 等待進程結束
            try:
                self.process.wait(timeout=config.SERVER_SHUTDOWN_TIMEOUT)
                logger.info("✓ 伺服器已優雅關閉")
            except subprocess.TimeoutExpired:
                # 強制終止
                logger.warning(
                    f"進程未在 {config.SERVER_SHUTDOWN_TIMEOUT} 秒內結束，"
                    f"執行強制終止"
                )
                self.process.kill()
                self.process.wait()
                logger.info("✓ 伺服器已強制終止")

        except Exception as e:
            logger.error(f"關閉伺服器時發生錯誤: {e}")
        finally:
            self.process = None

        # 關閉日誌檔案
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

        logger.info("=" * 80)

    def _check_port_available(self) -> None:
        """檢查目標 port 是否可用

        Raises:
            ServerStartupError: Port 已被佔用
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((config.SERVER_HOST, config.SERVER_PORT))
            logger.info(f"✓ Port {config.SERVER_PORT} 可用")
        except OSError:
            raise ServerStartupError(
                f"Port {config.SERVER_PORT} 已被佔用\n"
                f"請確認是否有其他伺服器正在運行，或修改 config.SERVER_PORT"
            )
        finally:
            sock.close()

    def _prepare_environment(self) -> dict:
        """準備環境變數

        Returns:
            包含所有必要環境變數的字典
        """
        env = os.environ.copy()

        # 設定測試模式
        env["TEST_MODE"] = "1"

        # 設定測試資料庫（動態讀取環境變數）
        test_db_url = config.get_test_database_url()
        if test_db_url:
            env["TEST_DATABASE_URL"] = test_db_url
            env["DATABASE_URL"] = test_db_url
            logger.info(f"✓ 測試資料庫: {test_db_url}")
        else:
            logger.warning("警告: TEST_DATABASE_URL 未設定")

        return env

    def _prepare_log_file(self) -> None:
        """準備日誌檔案"""
        if config.SERVER_LOG_FILE:
            self.log_file = Path(config.SERVER_LOG_FILE)
        else:
            # 使用臨時檔案
            fd, path = tempfile.mkstemp(
                prefix="e2e_server_",
                suffix=".log",
                text=True
            )
            os.close(fd)  # 關閉 fd，讓 Popen 使用
            self.log_file = Path(path)

        logger.info(f"✓ 日誌檔案: {self.log_file}")

    def _start_process(self, env: dict) -> None:
        """啟動伺服器進程

        Args:
            env: 環境變數字典

        Raises:
            ServerStartupError: 進程啟動失敗
        """
        # 構建命令
        cmd = [
            sys.executable,  # 使用當前 Python 解釋器
            "-m",
            "uvicorn",
            "main:app",
            "--host", config.SERVER_HOST,
            "--port", str(config.SERVER_PORT),
        ]

        # 打開日誌檔案
        if self.log_file:
            self._log_handle = open(self.log_file, "w", encoding="utf-8")
            stdout = self._log_handle
            stderr = subprocess.STDOUT  # 合併 stderr 到 stdout
        else:
            stdout = subprocess.DEVNULL
            stderr = subprocess.DEVNULL

        # 啟動進程
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=self.project_root,
                env=env,
                stdout=stdout,
                stderr=stderr,
                text=True,
            )
            logger.info(f"✓ 進程已啟動 (PID: {self.process.pid})")
            logger.info(f"  命令: {' '.join(cmd)}")

        except Exception as e:
            raise ServerStartupError(f"啟動伺服器進程失敗: {e}")

    def _wait_for_server(self) -> None:
        """等待伺服器就緒（健康檢查）

        Raises:
            ServerStartupError: 伺服器未在預期時間內就緒
        """
        health_url = config.get_health_check_url()
        max_retries = config.HEALTH_CHECK_MAX_RETRIES
        interval = config.HEALTH_CHECK_INTERVAL

        logger.info(f"等待伺服器就緒...")
        logger.info(f"  - 健康檢查 URL: {health_url}")
        logger.info(f"  - 最大重試次數: {max_retries}")
        logger.info(f"  - 檢查間隔: {interval} 秒")

        for attempt in range(1, max_retries + 1):
            # 檢查進程是否還活著
            if self.process.poll() is not None:
                # 進程已結束，讀取日誌
                log_content = self._read_log_tail(lines=50)
                raise ServerStartupError(
                    f"伺服器進程意外終止 (退出碼: {self.process.returncode})\n"
                    f"最後 50 行日誌:\n{log_content}"
                )

            # 嘗試連接
            try:
                response = requests.get(health_url, timeout=2)
                if response.status_code == 200:
                    logger.info(f"✓ 伺服器就緒 (第 {attempt} 次嘗試)")
                    return
                else:
                    logger.debug(
                        f"健康檢查返回非 200 狀態碼: {response.status_code}"
                    )
            except requests.RequestException as e:
                logger.debug(f"第 {attempt}/{max_retries} 次嘗試: {e}")

            time.sleep(interval)

        # 超時，讀取日誌輔助診斷
        log_content = self._read_log_tail(lines=50)
        raise ServerStartupError(
            f"伺服器未在 {max_retries * interval} 秒內就緒\n"
            f"健康檢查 URL: {health_url}\n"
            f"最後 50 行日誌:\n{log_content}"
        )

    def _read_log_tail(self, lines: int = 50) -> str:
        """讀取日誌檔案的最後幾行

        Args:
            lines: 讀取的行數

        Returns:
            日誌內容
        """
        if not self.log_file or not self.log_file.exists():
            return "(日誌檔案不存在)"

        try:
            # 確保檔案寫入完成
            if self._log_handle:
                self._log_handle.flush()

            with open(self.log_file, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
                tail_lines = all_lines[-lines:]
                return "".join(tail_lines)
        except Exception as e:
            return f"(無法讀取日誌: {e})"
