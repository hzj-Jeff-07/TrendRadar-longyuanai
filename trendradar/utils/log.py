# coding=utf-8
"""日志工具模块

统一的 logging 配置，替代散落各处的 print：

- 默认输出格式与 print 完全一致（仅消息本身），对用户零可见变化
- LOG_LEVEL 环境变量控制级别（DEBUG/INFO/WARNING/ERROR，默认 INFO）
- LOG_FORMAT=full 输出时间戳 + 级别 + 模块名，便于 Docker/CI 排查问题

用法::

    from trendradar.utils.log import get_logger

    logger = get_logger(__name__)
    logger.info("获取 %s 成功", platform_id)
    logger.warning("请求 %s 失败: %s", platform_id, e)
"""

import logging
import os

_configured = False


def setup_logging(force: bool = False) -> None:
    """初始化根日志配置（幂等，可安全重复调用）

    Args:
        force: 强制重新配置（用于测试或运行时切换格式）
    """
    global _configured
    if _configured and not force:
        return

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if os.environ.get("LOG_FORMAT", "").lower() == "full":
        fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
    else:
        # 与原 print 输出保持一致
        fmt = "%(message)s"
        datefmt = None

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, force=force)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger（首次调用时自动完成根配置）"""
    setup_logging()
    return logging.getLogger(name)
