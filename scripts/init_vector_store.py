#!/usr/bin/env python3
"""
初始化第二大脑向量库
从历史周报、项目README和研究报告中构建向量存储
"""
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

import yaml

# 添加项目根目录到Python路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

# 直接使用 chromadb 和 llama_index，避免复杂依赖
try:
    from llama_index.core import Document, VectorStoreIndex
    from llama_index.core.embeddings import resolve_embed_model
    from llama_index.vector_stores.chroma import ChromaVectorStore
    import chromadb
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    logger.error(f"缺少必要的依赖: {e}")
    logger.error("请运行: pip install llama-index chromadb llama-index-vector-stores-chroma")
    DEPENDENCIES_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_yaml(file_path: Path) -> dict:
    """加载YAML配置文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"加载YAML文件失败 {file_path}: {e}")
        return {}


def extract_text_from_markdown(file_path: Path) -> str:
    """从Markdown文件中提取文本内容，忽略代码块"""
    content = file_path.read_text(encoding='utf-8')
    # 移除代码块
    content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    # 移除Markdown特定语法
    content = re.sub(r'\[.*?\]\(.*?\)', '', content)  # 链接
    content = re.sub(r'#+\s.*', '', content)  # 标题
    content = re.sub(r'[\*_`]', '', content)  # 粗体、斜体、代码
    return content.strip()


def get_project_readmes(user_profile: Dict, project_root: Path) -> List[Dict[str, str]]:
    """收集活跃项目的README文件"""
    readmes = []
    active_projects = user_profile.get("active_projects", [])
    
    for project in active_projects:
        name = project.get("name")
        if name:
            # 假设项目目录在ai-workflow的同级目录或父目录
            project_path = project_root.parent / name
            readme_path = project_path / "README.md"
            
            if readme_path.exists():
                try:
                    text_content = extract_text_from_markdown(readme_path)
                    readmes.append({
                        "title": f"Project README: {name}",
                        "source": f"project_readme_{name}",
                        "text": text_content,
                    })
                    logger.info(f"找到项目README: {name}")
                except Exception as e:
                    logger.warning(f"无法读取README {name}: {e}")
            else:
                logger.warning(f"未找到README: {name} at {readme_path}")
    
    return readmes


def get_historical_reports(reports_dir: Path) -> List[Dict[str, str]]:
    """收集历史周报"""
    reports = []
    
    if not reports_dir.exists():
        logger.warning(f"周报目录不存在: {reports_dir}")
        return reports
    
    for file_path in reports_dir.glob("weekly_report_*.md"):
        try:
            text_content = extract_text_from_markdown(file_path)
            reports.append({
                "title": f"Weekly Report: {file_path.stem}",
                "source": "weekly_report",
                "text": text_content,
            })
            logger.info(f"找到历史周报: {file_path.name}")
        except Exception as e:
            logger.warning(f"无法读取历史周报 {file_path.name}: {e}")
    
    return reports


def get_research_reports(research_reports_dir: Path) -> List[Dict[str, str]]:
    """收集研究助手报告"""
    reports = []
    
    if not research_reports_dir.exists():
        logger.warning(f"研究报告目录不存在: {research_reports_dir}")
        return reports
    
    for file_path in research_reports_dir.glob("*.md"):
        try:
            text_content = extract_text_from_markdown(file_path)
            reports.append({
                "title": f"Research Report: {file_path.stem}",
                "source": "research_assistant",
                "text": text_content,
            })
            logger.info(f"找到研究报告: {file_path.name}")
        except Exception as e:
            logger.warning(f"无法读取研究报告 {file_path.name}: {e}")
    
    return reports


def main():
    if not DEPENDENCIES_AVAILABLE:
        logger.error("无法初始化向量库，缺少必要的依赖")
        sys.exit(1)
    
    logger.info("\n" + "=" * 60)
    logger.info("初始化第二大脑向量库")
    logger.info("=" * 60)
    
    # 加载用户配置
    config_path = project_root / "config" / "user_profile.yaml"
    user_profile = load_yaml(config_path)
    
    # 直接初始化向量存储（不通过SecondBrainVectorStore类）
    persist_dir = project_root / "data" / "second_brain_chroma"
    persist_dir.mkdir(parents=True, exist_ok=True)
    
    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection("second_brain_collection")
    vector_store = ChromaVectorStore(chroma_collection=collection)
    embed_model = resolve_embed_model("BAAI/bge-small-en-v1.5")
    index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
    
    logger.info(f"✓ 向量存储初始化完成，数据路径: {persist_dir}")
    
    # 收集所有文档
    all_documents = []
    
    # 1. 历史周报
    logger.info("\n收集历史周报...")
    all_documents.extend(get_historical_reports(project_root / "output"))
    
    # 2. 项目README
    logger.info("\n收集项目README...")
    all_documents.extend(get_project_readmes(user_profile, project_root))
    
    # 3. 研究报告
    logger.info("\n收集研究报告...")
    research_assistant_root = project_root.parent / "research-assistant"
    if research_assistant_root.exists():
        research_reports_dir = research_assistant_root / "reports"
        all_documents.extend(get_research_reports(research_reports_dir))
    else:
        logger.warning(f"研究助手目录不存在: {research_assistant_root}")
    
    # 构建向量库
    if all_documents:
        logger.info(f"\n开始构建向量库，共 {len(all_documents)} 个文档...")
        for doc_data in all_documents:
            doc = Document(
                text=doc_data["text"],
                metadata={
                    "source": doc_data.get("source", "history"),
                    "title": doc_data.get("title", doc_data["text"][:50]),
                },
            )
            index.insert(doc)
            logger.debug(f"添加文档: {doc_data.get('title', doc_data['text'][:50])}")
        
        logger.info("\n✓ 第二大脑向量库初始化完成！")
        logger.info(f"✓ 数据存储位置: {persist_dir}")
        logger.info(f"✓ 共添加 {len(all_documents)} 个文档")
    else:
        logger.warning("\n未找到任何文档，向量库为空。")
    
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

