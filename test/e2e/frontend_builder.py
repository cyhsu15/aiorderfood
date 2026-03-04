"""
前端構建管理模組

負責自動化前端構建流程，包括依賴安裝、執行構建命令、驗證構建結果等。
"""
import logging
import subprocess
import os
from pathlib import Path
from typing import Tuple

from .config import config

logger = logging.getLogger(__name__)


class FrontendBuildError(Exception):
    """前端構建失敗異常"""
    pass


class FrontendBuilder:
    """前端構建管理器

    負責執行前端構建流程，確保測試運行前前端資源已準備就緒。
    """

    def __init__(self, project_root: Path):
        """初始化前端構建器

        Args:
            project_root: 專案根目錄路徑
        """
        self.project_root = project_root
        self.frontend_dir = project_root / config.FRONTEND_DIR
        self.dist_dir = project_root / config.FRONTEND_DIST_DIR
        self.package_json = self.frontend_dir / "package.json"
        self.node_modules = self.frontend_dir / "node_modules"

    def build(self) -> None:
        """執行完整的前端構建流程

        Raises:
            FrontendBuildError: 構建過程中發生錯誤
        """
        if config.SKIP_FRONTEND_BUILD:
            logger.info("跳過前端構建（SKIP_FRONTEND_BUILD=True）")
            return

        logger.info("=" * 80)
        logger.info("開始前端構建流程")
        logger.info("=" * 80)

        # 檢查前端目錄
        self._verify_frontend_directory()

        # 安裝依賴（如果需要）
        if not self.node_modules.exists():
            logger.info("node_modules 不存在，執行 npm ci...")
            self._run_npm_ci()
        else:
            logger.info("node_modules 已存在，跳過依賴安裝")

        # 執行構建
        logger.info("執行 npm run build...")
        self._run_npm_build()

        # 驗證構建結果
        self._verify_build_output()

        logger.info("=" * 80)
        logger.info("前端構建完成！")
        logger.info(f"構建輸出目錄: {self.dist_dir}")
        logger.info("=" * 80)

    def _verify_frontend_directory(self) -> None:
        """驗證前端目錄結構"""
        if not self.frontend_dir.exists():
            raise FrontendBuildError(
                f"前端目錄不存在: {self.frontend_dir}"
            )

        if not self.package_json.exists():
            raise FrontendBuildError(
                f"package.json 不存在: {self.package_json}\n"
                f"請確認專案結構是否正確"
            )

        logger.info(f"✓ 前端目錄: {self.frontend_dir}")

    def _run_npm_ci(self) -> None:
        """執行 npm ci 安裝依賴"""
        success, output, error = self._run_command(
            ["npm", "ci"],
            cwd=self.frontend_dir,
            timeout=config.FRONTEND_BUILD_TIMEOUT
        )

        if not success:
            raise FrontendBuildError(
                f"npm ci 執行失敗:\n"
                f"錯誤輸出: {error}\n"
                f"標準輸出: {output}"
            )

        logger.info("✓ 依賴安裝完成")

    def _run_npm_build(self) -> None:
        """執行 npm run build 構建前端"""
        success, output, error = self._run_command(
            ["npm", "run", "build"],
            cwd=self.frontend_dir,
            timeout=config.FRONTEND_BUILD_TIMEOUT
        )

        if not success:
            raise FrontendBuildError(
                f"npm run build 執行失敗:\n"
                f"錯誤輸出: {error}\n"
                f"標準輸出: {output}"
            )

        logger.info("✓ 前端構建成功")

    def _verify_build_output(self) -> None:
        """驗證構建輸出"""
        index_html = self.dist_dir / "index.html"

        if not self.dist_dir.exists():
            raise FrontendBuildError(
                f"構建輸出目錄不存在: {self.dist_dir}"
            )

        if not index_html.exists():
            raise FrontendBuildError(
                f"index.html 不存在: {index_html}\n"
                f"構建可能不完整"
            )

        # 統計構建產物
        files = list(self.dist_dir.rglob("*"))
        file_count = len([f for f in files if f.is_file()])

        logger.info(f"✓ 構建輸出驗證通過")
        logger.info(f"  - 產物數量: {file_count} 個檔案")
        logger.info(f"  - 主檔案: {index_html}")

    def _run_command(
        self,
        cmd: list[str],
        cwd: Path,
        timeout: int
    ) -> Tuple[bool, str, str]:
        """執行命令並返回結果

        Args:
            cmd: 命令列表
            cwd: 工作目錄
            timeout: 超時時間（秒）

        Returns:
            (成功與否, 標準輸出, 錯誤輸出)
        """
        try:
            # Windows 平台需要使用 shell=True
            shell = os.name == 'nt'

            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=shell,
                encoding='utf-8',
                errors='replace'  # 處理編碼錯誤
            )

            success = result.returncode == 0
            return success, result.stdout, result.stderr

        except subprocess.TimeoutExpired:
            return False, "", f"命令執行超時（>{timeout}秒）"
        except Exception as e:
            return False, "", f"命令執行異常: {str(e)}"
