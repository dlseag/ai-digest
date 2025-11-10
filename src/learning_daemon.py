"""Daily learning helper script for AI Digest."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def configure_logger(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
    else:
        root_logger.setLevel(level)


def run_learning(days_back: int, verbose: bool = False) -> None:
    from src.main import WeeklyReportGenerator

    configure_logger(verbose)
    logger = logging.getLogger(__name__)

    logger.info("启动 AI Digest 每日学习循环 (days_back=%s)", days_back)
    generator = WeeklyReportGenerator()
    generator.run(days_back=days_back, learning_only=True)
    logger.info("每日学习循环完成")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Digest 每日学习任务")
    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="学习时回溯的天数（默认：7天）",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出更详细的日志",
    )
    args = parser.parse_args()

    run_learning(days_back=args.days_back, verbose=args.verbose)


if __name__ == "__main__":
    main()
