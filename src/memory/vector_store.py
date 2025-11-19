"""Second Brain Vector Store using ChromaDB for long-term knowledge storage."""

import logging
import os
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("CHROMA_TELEMETRY", "0")
from pathlib import Path
from typing import Any, Dict, List, Optional

# 延迟导入，避免触发 transformers 锁问题
Document = None
VectorStoreIndex = None
resolve_embed_model = None
ChromaVectorStore = None
chromadb = None

logger = logging.getLogger(__name__)


class SecondBrainVectorStore:
    """管理用户的"第二大脑"向量数据库，使用ChromaDB存储历史知识。"""

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        embed_model_name: str = "BAAI/bge-small-en-v1.5",
    ):
        project_root = Path(__file__).resolve().parents[2]
        self.persist_dir = (
            persist_dir or project_root / "data" / "second_brain_chroma"
        ).resolve()
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.embed_model_name = embed_model_name
        self.client = None
        self.collection = None
        self.vector_store = None
        self.embed_model = None
        self.index = None
        self.query_engine = None
        self._initialized = False

        logger.info(
            f"✓ SecondBrainVectorStore 已创建（延迟初始化），数据路径: {self.persist_dir}"
        )
    
    def _ensure_initialized(self) -> bool:
        """延迟初始化向量库"""
        if self._initialized:
            return True
        
        # 先尝试导入必要的库
        global Document, VectorStoreIndex, resolve_embed_model, ChromaVectorStore, chromadb
        if Document is None:
            try:
                from llama_index.core import Document as _Doc, VectorStoreIndex as _VSI
                from llama_index.core.embeddings import resolve_embed_model as _REM
                from llama_index.vector_stores.chroma import ChromaVectorStore as _CVS
                import chromadb as _chromadb
                
                Document = _Doc
                VectorStoreIndex = _VSI
                resolve_embed_model = _REM
                ChromaVectorStore = _CVS
                chromadb = _chromadb
            except Exception as e:
                logger.warning(f"无法导入向量库依赖: {e}")
                return False
        
        try:
            logger.info("正在初始化向量库（首次使用需下载模型）...")
            self.client = chromadb.PersistentClient(path=str(self.persist_dir))
            self.collection = self.client.get_or_create_collection(
                "second_brain_collection"
            )
            self.vector_store = ChromaVectorStore(chroma_collection=self.collection)
            self.embed_model = resolve_embed_model(self.embed_model_name)
            self.index = VectorStoreIndex.from_vector_store(
                self.vector_store, embed_model=self.embed_model
            )
            self.query_engine = self.index.as_query_engine()
            self._initialized = True
            logger.info("✓ 向量库初始化完成")
            return True
        except Exception as e:
            logger.warning(f"向量库初始化失败: {e}")
            return False

    def add_document(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """添加单个文档到向量库"""
        if not self._ensure_initialized():
            logger.warning("向量库未初始化，跳过文档添加")
            return
        doc = Document(text=text, metadata=metadata or {})
        self.index.insert(doc)
        logger.debug(f"添加文档到第二大脑: {metadata.get('title', text[:50])}")

    def query(self, query_text: str, top_k: int = 20) -> List[str]:
        """查询向量库中的相关文档"""
        if not self._ensure_initialized():
            logger.warning("向量库未初始化，返回空结果")
            return []
        response = self.query_engine.query(query_text)
        return [node.text for node in response.source_nodes]

    def build_from_history(self, documents: List[Dict[str, str]]) -> None:
        """从历史文档列表构建向量库"""
        if not self._ensure_initialized():
            logger.warning("向量库未初始化，跳过历史文档构建")
            return
        logger.info(f"开始构建第二大脑向量库，共 {len(documents)} 个历史文档...")
        for doc_data in documents:
            self.add_document(
                doc_data["text"],
                {
                    "source": doc_data.get("source", "history"),
                    "title": doc_data.get("title", doc_data["text"][:50]),
                },
            )
        logger.info("✓ 第二大脑向量库构建完成。")

