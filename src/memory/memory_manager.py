"""Memory Manager for coordinating different memory components."""

import logging
from pathlib import Path
from typing import Any, Optional

try:
    from langchain_core.chat_history import BaseChatMessageHistory
    from langchain_community.chat_message_histories import SQLChatMessageHistory
    LANGCHAIN_AVAILABLE = True
except ImportError:
    BaseChatMessageHistory = None
    SQLChatMessageHistory = None
    LANGCHAIN_AVAILABLE = False

from src.memory.vector_store import SecondBrainVectorStore
from src.memory.user_profile_manager import UserProfileManager
from src.storage.feedback_db import FeedbackDB

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    管理AI简报系统的各种内存组件，包括：
    - LangGraph的checkpointer（对话历史/状态）
    - 用户画像存储
    - LlamaIndex的VectorMemoryBlock（第二大脑）
    """

    def __init__(
        self,
        user_id: str = "default_user",
        db_path: Optional[Path] = None,
        second_brain_persist_dir: Optional[Path] = None,
        embed_model_name: str = "BAAI/bge-small-en-v1.5",
    ):
        project_root = Path(__file__).resolve().parents[2]
        self.user_id = user_id
        self.db_path = (db_path or project_root / "data" / "memory.db").resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # LangGraph Checkpointer (用于对话历史/状态) - 可选功能
        self.checkpointer = None
        if LANGCHAIN_AVAILABLE:
            try:
                self.checkpointer = SQLChatMessageHistory(
                    session_id=self.user_id, connection_string=f"sqlite:///{self.db_path}"
                )
                logger.info(f"✓ LangGraph Checkpointer 初始化完成: {self.db_path}")
            except Exception as e:
                logger.warning(f"LangGraph Checkpointer 初始化失败（可选功能）: {e}")
        else:
            logger.info("LangGraph 未安装，跳过 Checkpointer 初始化（可选功能）")

        # 第二大脑向量存储（长期知识检索）- 延迟初始化
        self.second_brain_store = None
        self._second_brain_persist_dir = second_brain_persist_dir
        self._embed_model_name = embed_model_name
        logger.info("✓ 第二大脑向量存储已配置（延迟初始化）")

        # 用户画像管理器（结构化用户画像和向量嵌入）
        # 注意：UserProfileManager 使用不同的初始化参数
        profile_path = Path(__file__).resolve().parents[2] / "config" / "user_profile.yaml"
        self.user_profile_manager = UserProfileManager(
            profile_path=profile_path,
            embedding_model=embed_model_name,
        )
        logger.info("✓ 用户画像管理器初始化完成")

        # 反馈数据库（用于事实提取和显式反馈）
        self.feedback_db = FeedbackDB()
        logger.info("✓ 反馈数据库初始化完成")

    def get_checkpointer(self):
        """获取LangGraph checkpointer"""
        return self.checkpointer

    def get_second_brain(self):
        """获取第二大脑向量存储（延迟初始化）"""
        if self.second_brain_store is None:
            try:
                logger.info("首次使用向量库，正在初始化...")
                self.second_brain_store = SecondBrainVectorStore(
                    persist_dir=self._second_brain_persist_dir,
                    embed_model_name=self._embed_model_name
                )
            except Exception as e:
                logger.warning(f"向量库初始化失败: {e}")
        return self.second_brain_store

    def get_user_profile_manager(self) -> UserProfileManager:
        """获取用户画像管理器"""
        return self.user_profile_manager

    def get_explicit_feedback_db(self) -> FeedbackDB:
        """获取显式反馈数据库"""
        return self.feedback_db

