"""
Tracking Server for Reading Behaviors
阅读行为追踪服务器
"""

import json
import logging
import os
import asyncio
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from typing import Optional, Tuple
import sys
from uuid import uuid4
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.storage.feedback_db import FeedbackDB
from src.agents.tool_executor import ToolExecutor
from src.learning.feedback_reinforcer import FeedbackReinforcer
from src.utils.llm_client import get_llm_client
from src.memory.hot_cache import HotMemoryCache
from src.memory.cache_sync import sync_hot_cache_to_warm_storage
from src.memory.metrics import get_memory_health_api

logger = logging.getLogger(__name__)
HISTORY_LOG_PATH = Path(__file__).parents[2] / "logs" / "deep_dive_history.jsonl"
HISTORY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
TRACKING_LOG_CANDIDATES = [
    Path.home() / "Library" / "Logs" / "ai-digest-tracking-server.log",
    Path.home() / "Library" / "Logs" / "ai-digest-tracking-server.error.log",
    Path(__file__).parents[2] / "logs" / "tracking-server.log",
    Path(__file__).parents[2] / "logs" / "tracking-server.error.log",
]


class TrackingHandler(BaseHTTPRequestHandler):
    """追踪请求处理器"""
    
    # 类级别共享的数据库连接和工具执行器
    db = None
    tool_executor = None
    feedback_reinforcer = None
    hot_cache = None
    hot_cache_flush_threshold = 400
    history_log_path = HISTORY_LOG_PATH
    log_candidates = TRACKING_LOG_CANDIDATES
    
    @classmethod
    def set_db(cls, db):
        cls.db = db
    
    @classmethod
    def set_tool_executor(cls, executor):
        cls.tool_executor = executor
    
    @classmethod
    def set_feedback_reinforcer(cls, reinforcer):
        cls.feedback_reinforcer = reinforcer
    
    @classmethod
    def set_hot_cache(cls, cache: HotMemoryCache, flush_threshold: int = 400):
        cls.hot_cache = cache
        cls.hot_cache_flush_threshold = flush_threshold
    
    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_POST(self):
        """处理POST请求（追踪数据或执行行动）"""
        # 解析URL路径
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        # 处理行动执行请求
        if path == '/api/execute_action':
            self._handle_execute_action()
            return
        
        # 处理追踪请求
        if path == '/api/track':
            self._handle_track()
            return
        
        # 未知路径
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {'status': 'error', 'message': 'Not found'}
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def _handle_track(self):
        """处理追踪请求"""
        
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # 保存行为数据
            self._store_reading_behavior(data)
            
            # 检查是否为"想看更多"请求
            action = data.get('action', 'unknown')
            feedback_type = data.get('feedback_type')
            
            if action == "feedback" and feedback_type == "more":
                # 同步处理深度研究请求
                deep_dive_result = self._handle_deep_dive_request(data)
                response = {
                    'status': 'success',
                    'message': 'Behavior tracked',
                    'deep_dive': deep_dive_result
                }
            elif action == "feedback" and feedback_type == "architect_analysis":
                # 同步处理架构师分析请求
                analysis_result = self._handle_architect_analysis_request(data)
                response = {
                    'status': 'success',
                    'message': 'Behavior tracked',
                    'deep_dive': analysis_result  # 复用 deep_dive 字段以保持前端兼容性
                }
            else:
                response = {'status': 'success', 'message': 'Behavior tracked'}
            
            # 返回成功响应
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
            item_id = data.get('item_id', 'N/A')
            logger.info(f"✓ 追踪行为: {action} - {item_id}")
            
        except Exception as e:
            logger.error(f"追踪失败: {e}", exc_info=True)
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {'status': 'error', 'message': str(e)}
            self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def _handle_execute_action(self):
        """处理行动执行请求"""
        try:
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # 获取工具调用信息
            tool_name = data.get('tool_name')
            arguments = data.get('arguments', {})
            action_id = data.get('action_id', 'unknown')
            
            if not tool_name:
                raise ValueError("缺少 tool_name")
            
            # 执行工具
            if not self.tool_executor:
                raise ValueError("工具执行器未初始化")
            
            result = self.tool_executor.execute(tool_name, arguments)
            
            # 记录执行结果到数据库
            self._store_reading_behavior({
                "report_id": data.get('report_id', 'unknown'),
                "item_id": action_id,
                "action": "execute_action",
                "feedback_type": "success" if result.success else "failed",
                "section": "action_items",
                "metadata": json.dumps({
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result.to_dict() if hasattr(result, 'to_dict') else str(result),
                }),
            })
            
            # Phase 2.3: 记录反馈并强化权重
            if self.feedback_reinforcer:
                action_type = self._get_action_type_from_tool(tool_name)
                self.feedback_reinforcer.record_action_feedback(
                    action_id=action_id,
                    action_type=action_type,
                    feedback_type="execute",
                    tool_name=tool_name,
                    success=result.success,
                )
            
            # 返回执行结果
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {
                'status': 'success' if result.success else 'error',
                'message': result.message,
                'data': result.to_dict() if hasattr(result, 'to_dict') else {'result': str(result)},
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
            logger.info(f"✓ 执行行动: {tool_name} - {action_id} ({'成功' if result.success else '失败'})")
            
        except Exception as e:
            logger.error(f"执行行动失败: {e}", exc_info=True)
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = {'status': 'error', 'message': str(e)}
            self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def do_GET(self):
        """处理GET请求"""
        parsed_path = urlparse(self.path)
        
        if parsed_path.path == '/api/deep_dive_history':
            self._handle_deep_dive_history(parsed_path)
            return
        
        if parsed_path.path == '/api/memory/metrics':
            self._handle_memory_metrics()
            return
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        response = {'status': 'ok', 'message': 'Tracking server is running'}
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def _handle_memory_metrics(self):
        """返回记忆系统健康状态和质量指标"""
        try:
            result = get_memory_health_api()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
        except Exception as e:
            logger.error(f"获取记忆指标失败: {e}")
            
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            response = {'status': 'error', 'message': str(e)}
            self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def _handle_deep_dive_history(self, parsed_path):
        """返回最近的深度研究记录"""
        params = parse_qs(parsed_path.query)
        try:
            limit = int(params.get('limit', ['20'])[0])
        except ValueError:
            limit = 20
        limit = max(1, min(limit, 100))
        
        history = self._read_deep_dive_history(limit)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response = {'status': 'success', 'history': history}
        self.wfile.write(json.dumps(response).encode('utf-8'))
    
    def _get_action_type_from_tool(self, tool_name: str) -> str:
        """从工具名称获取行动类型"""
        mapping = {
            "create_github_issue": "github_issue",
            "send_calendar_invite": "calendar",
            "add_to_reading_list": "reading_list",
        }
        return mapping.get(tool_name, "other")
    
    def _handle_deep_dive_request(self, data: dict) -> dict:
        """同步处理深度研究请求，返回研究结果"""
        # 1. 提取URL和标题
        metadata = data.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {"raw": metadata}
        
        item_url = data.get("url") or metadata.get("item_url")
        item_title = metadata.get("item_title", "Unknown")
        request_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        
        if not item_url:
            user_message = "缺少文章URL"
            self._append_deep_dive_history({
                "request_id": request_id,
                "status": "error",
                "title": item_title,
                "url": None,
                "error_message": "missing url in payload",
                "user_message": user_message,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
            return {
                "status": "error",
                "message": user_message,
                "request_id": request_id,
            }
        
        logger.info(f"🔬 开始深度研究: {item_title[:50]}...")
        
        # 2. 调用 research-assistant
        try:
            result = self._run_research_assistant(item_url, item_title)
            logger.info(f"✅ 研究完成: {item_title[:50]}...")
            duration = (datetime.now(timezone.utc) - started_at).total_seconds()
            self._append_deep_dive_history({
                "request_id": request_id,
                "status": "success",
                "title": item_title,
                "url": item_url,
                "report_path": result["report_path"],
                "duration": duration,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
            return {
                "status": "success",
                "markdown": result["markdown"],
                "report_path": result["report_path"],
                "request_id": request_id,
            }
        except Exception as primary_error:
            logger.error(f"深度研究失败: {primary_error}", exc_info=True)
            try:
                fallback = self._run_llm_fallback(item_url, item_title)
                duration = (datetime.now(timezone.utc) - started_at).total_seconds()
                self._append_deep_dive_history({
                    "request_id": request_id,
                    "status": "success",
                    "title": item_title,
                    "url": item_url,
                    "report_path": fallback["report_path"],
                    "duration": duration,
                    "mode": "fallback_llm",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                })
                return {
                    "status": "success",
                    "markdown": fallback["markdown"],
                    "report_path": fallback["report_path"],
                    "request_id": request_id,
                    "mode": "fallback_llm",
                    "message": "研究助手失败，已使用LLM备用方案生成报告",
                }
            except Exception as fallback_error:
                logger.error(f"LLM备用方案也失败: {fallback_error}", exc_info=True)
                error_info = self._format_deep_dive_error(str(fallback_error))
                duration = (datetime.now(timezone.utc) - started_at).total_seconds()
                log_excerpt, log_path = self._read_recent_log_excerpt()
                combined_error = f"{primary_error}; fallback={fallback_error}"
                self._append_deep_dive_history({
                    "request_id": request_id,
                    "status": "error",
                    "title": item_title,
                    "url": item_url,
                    "error_message": combined_error,
                    "user_message": error_info["message"],
                    "log_path": log_path,
                    "log_excerpt": log_excerpt,
                    "duration": duration,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                })
                error_payload = {
                    "status": "error",
                    "message": error_info["message"],
                    "hint": error_info["hint"] + "（LLM备用方案也失败）",
                    "request_id": request_id,
                }
                if log_path:
                    error_payload["log_path"] = log_path
                if log_excerpt:
                    error_payload["log_excerpt"] = log_excerpt
                return error_payload
    
    def _handle_architect_analysis_request(self, data: dict) -> dict:
        """
        处理架构师分析请求
        
        从AI系统架构师视角分析新闻/论文：
        1. 架构演进：解决了什么痛点
        2. 落地场景：能跑通什么新的Agent Workflow
        3. 设计模式：需要什么新的基础设施
        """
        # 1. 提取元数据
        metadata = data.get("metadata") or {}
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except json.JSONDecodeError:
                metadata = {"raw": metadata}
        
        item_url = data.get("url") or metadata.get("item_url")
        item_title = metadata.get("item_title", "Unknown")
        item_source = metadata.get("item_source", "Unknown")
        item_summary = metadata.get("summary", "")
        request_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        
        if not item_url:
            user_message = "缺少文章URL"
            self._append_deep_dive_history({
                "request_id": request_id,
                "status": "error",
                "title": item_title,
                "url": None,
                "error_message": "missing url in payload",
                "user_message": user_message,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "analysis_type": "architect",
            })
            return {
                "status": "error",
                "message": user_message,
                "request_id": request_id,
            }
        
        logger.info(f"🏗️ 开始架构师分析: {item_title[:50]}...")
        
        # 2. 使用LLM生成架构师分析
        try:
            markdown = self._generate_architect_analysis(item_title, item_url, item_source, item_summary)
            report_path = self._save_deep_dive_report(item_title, markdown, mode="architect")
            
            duration = (datetime.now(timezone.utc) - started_at).total_seconds()
            self._append_deep_dive_history({
                "request_id": request_id,
                "status": "success",
                "title": item_title,
                "url": item_url,
                "report_path": report_path,
                "duration": duration,
                "mode": "architect_analysis",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
            
            logger.info(f"✅ 架构师分析完成: {item_title[:50]}...")
            
            return {
                "status": "success",
                "markdown": markdown,
                "report_path": report_path,
                "request_id": request_id,
                "mode": "architect_analysis",
            }
        except Exception as e:
            logger.error(f"架构师分析失败: {e}", exc_info=True)
            error_info = self._format_deep_dive_error(str(e))
            duration = (datetime.now(timezone.utc) - started_at).total_seconds()
            log_excerpt, log_path = self._read_recent_log_excerpt()
            
            self._append_deep_dive_history({
                "request_id": request_id,
                "status": "error",
                "title": item_title,
                "url": item_url,
                "error_message": str(e),
                "user_message": error_info["message"],
                "log_path": log_path,
                "log_excerpt": log_excerpt,
                "duration": duration,
                "mode": "architect_analysis",
                "finished_at": datetime.now(timezone.utc).isoformat(),
            })
            
            error_payload = {
                "status": "error",
                "message": error_info["message"],
                "hint": error_info["hint"],
                "request_id": request_id,
            }
            if log_path:
                error_payload["log_path"] = log_path
            if log_excerpt:
                error_payload["log_excerpt"] = log_excerpt
            return error_payload
    
    def _generate_architect_analysis(self, title: str, url: str, source: str, summary: str) -> str:
        """
        使用LLM生成AI系统架构师视角的分析
        """
        llm_client = get_llm_client()
        
        # 构建架构师分析的专用prompt
        prompt = f"""你是一位资深的AI系统架构师。请从系统设计的角度分析以下AI新闻/论文：

**标题**: {title}
**来源**: {source}
**摘要**: {summary}
**原文链接**: {url}

请从以下三个维度进行深入分析：

## 1. 🏗️ 架构演进 (Architecture Evolution)

- 这个新模型/工具解决了以前AI开发中的哪个痛点？
- 是记忆丢失？是幻觉？是编排太难？还是成本/延迟问题？
- 在AI系统架构的哪一层（计算层/记忆层/工具层/监控层）产生了影响？
- 相比之前的方案，架构上有什么本质性的改进？

## 2. 🚀 落地场景 (Practical Applications)

- 基于这个新能力，以前做不到的哪些Agent Workflow现在可以跑通了？
- 具体可以应用在什么场景？（如：实时对话、长文档分析、多步推理等）
- 对现有AI应用的改进空间在哪里？
- 有哪些实际的使用案例或潜在应用？

## 3. ⚙️ 设计模式与基础设施 (Design Patterns & Infrastructure)

- 如果要把这个新技术集成到企业级应用，需要考虑哪些新的基础设施？
- 是否需要更大的向量数据库？新的监控工具？不同的编排框架？
- 有哪些架构上的权衡（Trade-offs）？（如：速度vs准确率、成本vs性能）
- 需要什么样的技术栈和工具链支持？

## 4. 💡 系统设计启示

- 对于构建AI系统的开发者和架构师，这个技术带来了什么启示？
- 在设计AI应用时，应该如何考虑这个新能力？
- 有哪些需要注意的坑或最佳实践？

请用清晰、结构化的Markdown格式输出分析结果，帮助读者建立"AI系统架构师"的思维模式。
分析要具体、深入，避免泛泛而谈。如果某个维度不适用，请说明原因。
"""
        
        logger.info(f"📋 使用 LLM 进行架构师分析")
        
        # 调用LLM生成分析
        analysis_text = asyncio.run(llm_client.chat_completion(prompt=prompt)).strip()
        
        # 构建最终的Markdown报告
        markdown = f"""# 🏗️ AI系统架构师分析

## {title}

**来源**: {source}  
**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

{analysis_text}

---

> **原文链接**: [{title}]({url})
> 
> **说明**: 本分析从AI系统架构师的视角出发，帮助理解新技术的系统设计价值和实践启示。
"""
        
        return markdown
    
    def _run_research_assistant(self, url: str, title: str) -> dict:
        """调用 research-assistant 生成报告"""
        import subprocess
        import re
        from datetime import datetime
        
        # 准备研究助手目录与统一输出目录
        # 使用绝对路径确保正确
        current_file = Path(__file__).resolve()
        research_root = current_file.parents[3] / "research-assistant"
        # 所有深度研究报告统一保存到 ai-digest/deep_dive_reports
        output_dir = current_file.parents[2] / "deep_dive_reports"
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"✓ 深度研究报告输出目录: {output_dir}")
        
        # 调用 research-assistant/main.py
        research_assistant_path = research_root / "main.py"
        
        cmd = [
            sys.executable,
            str(research_assistant_path),
            "--url", url,
            "--report-dir", str(output_dir),
            "--json-output"
        ]
        
        logger.info(f"执行命令: {' '.join(cmd[:4])}...")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(research_assistant_path.parent)
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("研究超时（120秒）")
        
        if result.returncode != 0:
            error_output = result.stderr or result.stdout
            logger.error(f"Research assistant 失败: {error_output[:500]}")
            raise RuntimeError(f"Research assistant failed: {error_output[:200]}")
        
        # 解析 JSON 输出
        try:
            output_lines = result.stdout.strip().split('\n')
            # 查找JSON输出（最后一行应该是JSON）
            json_line = None
            for line in reversed(output_lines):
                if line.strip().startswith('{'):
                    json_line = line
                    break
            
            if not json_line:
                raise ValueError("未找到JSON输出")
            
            output_data = json.loads(json_line)
            return {
                "markdown": output_data.get("markdown", ""),
                "report_path": output_data.get("report_path", "")
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"解析输出失败: {e}")
            logger.error(f"输出内容: {result.stdout[:500]}")
            raise RuntimeError(f"无法解析研究结果: {str(e)}")

    def _run_llm_fallback(self, url: str, title: str) -> dict:
        """当 research-assistant 失败时，使用 LLM 直接生成报告"""
        logger.info(f"🔁 使用LLM备用方案进行深度研究: {title[:50]}...")
        article_html = self._fetch_article_html(url)
        article_text = self._extract_article_text(article_html)
        if len(article_text) < 200:
            raise RuntimeError("备用方案: 无法提取文章正文或正文过短")
        markdown = self._summarize_with_llm(title, url, article_text)
        report_path = self._save_deep_dive_report(title, markdown, mode="llm")
        return {
            "markdown": markdown,
            "report_path": report_path,
        }

    def _fetch_article_html(self, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text

    def _extract_article_text(self, html: str) -> str:
        soup = BeautifulSoup(html, 'lxml')
        candidates = [soup.find('article'), soup.find('main'), soup.find('section')]
        candidate = next((c for c in candidates if c), soup.body)
        if not candidate:
            return ''
        paragraphs = []
        for tag in candidate.find_all(['p', 'li']):
            text = tag.get_text(' ', strip=True)
            if len(text) >= 40 and not text.startswith('var '):
                paragraphs.append(text)
        return '\n'.join(paragraphs)

    def _summarize_with_llm(self, title: str, url: str, article_text: str) -> str:
        llm_client = get_llm_client()
        excerpt = article_text.strip()
        if len(excerpt) > 6000:
            excerpt = excerpt[:6000]
        prompt = (
            "你是一名资深AI研究分析师，请根据提供的文章内容输出Markdown格式的深度报告，必须用中文撰写。\n"
            "结构：\n"
            "1. ### 关键信息 - 列出最重要的3-5条结论\n"
            "2. ### 背后逻辑 - 解释关键技术/观点的原理与限制\n"
            "3. ### 对我的价值 - David关注RAG、Agent、企业AI落地，说明启发\n"
            "4. ### 下一步建议 - 提供可执行行动或说明不建议的原因\n\n"
            f"文章标题: {title}\n"
            f"文章链接: {url}\n"
            f"文章正文:\n{excerpt}\n"
        )
        summary_text = asyncio.run(llm_client.chat_completion(prompt=prompt)).strip()
        markdown = (
            f"### {title}\n\n"
            f"{summary_text or '（LLM未返回内容）'}\n\n"
            f"> 原文链接：[点击查看]({url})"
        )
        return markdown


    def _save_deep_dive_report(self, title: str, markdown: str, mode: str = 'llm') -> str:
        safe_title = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-') or 'deep-dive'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{mode}_{safe_title[:40].lower()}" + '.md'
        # 所有深度研究报告统一保存到 ai-digest/deep_dive_reports
        # 使用绝对路径确保正确
        current_file = Path(__file__).resolve()
        # tracking_server.py 在 ai-digest/src/tracking/ 下，需要向上2级到 ai-digest
        output_dir = current_file.parents[2] / 'deep_dive_reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / filename
        report_path.write_text(markdown, encoding='utf-8')
        logger.info(f"✓ 深度研究报告已保存到: {report_path}")
        return str(report_path)


    
    @classmethod
    def _format_deep_dive_error(cls, raw: str) -> dict:
        """将底层异常转换为面向用户的友好提示和建议。"""
        lowered = raw.lower()
        if "timeout" in lowered or "timed out" in lowered:
            return {
                "message": "研究超时：来源服务器长时间无响应",
                "hint": "请稍后再试，或检查目标站点是否可访问",
            }
        if any(keyword in lowered for keyword in ("connection", "network", "dns")):
            return {
                "message": "无法连接到来源站点，可能是网络不稳定或站点临时不可用",
                "hint": "请检查网络环境，或复制链接在浏览器中尝试访问",
            }
        if "reddit" in lowered and ("blocked" in lowered or "需要登录" in lowered):
            return {
                "message": "Reddit 拒绝了自动访问，需登录或开发者令牌",
                "hint": "请改用公开可访问的讨论链接，或将原文复制到自建文档后再研究",
            }
        if "403" in raw or "404" in raw:
            paywalled_domains = ("ft.com", "wsj.com", "bloomberg.com", "economist.com")
            if any(domain in raw for domain in paywalled_domains):
                return {
                    "message": "来源页面位于付费墙之后，无法自动抓取",
                    "hint": "请提供公开可访问的链接，或将文章内容复制到自建文档后再发起深度研究",
                }
            return {
                "message": "来源页面无法访问（可能不存在或被限制访问）",
                "hint": "确认链接是否正确，或尝试替换为公开可访问的来源",
            }
        if "research assistant failed" in raw:
            return {
                "message": "研究助手执行失败，详细错误已记录在追踪服务器日志",
                "hint": "可在日志面板中查看详情，或稍后重试",
            }
        return {
            "message": "内容解析失败，请稍后再试（详细日志已记录）",
            "hint": "如果问题持续，请将日志截图反馈给开发者",
        }
    
    @classmethod
    def _append_deep_dive_history(cls, entry: dict) -> None:
        entry.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
        cls.history_log_path.parent.mkdir(parents=True, exist_ok=True)
        with cls.history_log_path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    @classmethod
    def _read_deep_dive_history(cls, limit: int) -> list:
        if not cls.history_log_path.exists():
            return []
        history = []
        with cls.history_log_path.open('r', encoding='utf-8') as fp:
            for line in reversed(fp.readlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    history.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(history) >= limit:
                    break
        return history
    
    @classmethod
    def _read_recent_log_excerpt(cls, max_lines: int = 40) -> Tuple[Optional[str], Optional[str]]:
        """读取最近的追踪日志内容，返回(内容, 路径)。"""
        for candidate in cls.log_candidates:
            if not candidate:
                continue
            try:
                if candidate.exists():
                    with candidate.open('r', encoding='utf-8', errors='ignore') as fp:
                        lines = fp.readlines()[-max_lines:]
                        excerpt = ''.join(lines).strip()
                        if excerpt:
                            return excerpt, str(candidate)
            except OSError:
                continue
        return None, None
    
    def log_message(self, format, *args):
        """禁用默认日志"""
        pass
    
    def _store_reading_behavior(self, data: dict) -> None:
        """优先写入热缓存，必要时刷新到持久层。"""
        if self.hot_cache:
            self.hot_cache.store("reading_behavior", data)
            self._maybe_flush_hot_cache()
        else:
            self.db.save_reading_behavior(data)
    
    def _maybe_flush_hot_cache(self, force: bool = False) -> None:
        if not self.hot_cache:
            return
        if not force and self.hot_cache.get_size("reading_behavior") < self.hot_cache_flush_threshold:
            return
        sync_hot_cache_to_warm_storage(
            self.hot_cache,
            self.db,
            behavior_batch_size=self.hot_cache_flush_threshold,
        )


def run_server(port: int = 8000, tool_config: Optional[dict] = None):
    """运行追踪服务器"""
    # 初始化数据库
    db = FeedbackDB()
    TrackingHandler.set_db(db)
    hot_cache = HotMemoryCache()
    flush_threshold = int(os.getenv("HOT_CACHE_FLUSH_THRESHOLD", "400"))
    TrackingHandler.set_hot_cache(hot_cache, flush_threshold)
    
    # 初始化工具执行器（如果提供配置）
    tool_executor = None
    if tool_config:
        from src.agents.tool_executor import ToolExecutor
        tool_executor = ToolExecutor(config=tool_config)
        TrackingHandler.set_tool_executor(tool_executor)
        logger.info("✓ 工具执行器已加载")
    
    # Phase 2.3: 初始化反馈强化器
    from src.learning.weight_adjuster import WeightAdjuster
    weight_adjuster = WeightAdjuster()
    feedback_reinforcer = FeedbackReinforcer(db=db, weight_adjuster=weight_adjuster)
    TrackingHandler.set_feedback_reinforcer(feedback_reinforcer)
    logger.info("✓ 反馈强化器已加载")
    
    server_address = ('', port)
    httpd = HTTPServer(server_address, TrackingHandler)
    
    logger.info(f"🚀 追踪服务器启动: http://localhost:{port}")
    logger.info(f"   API 端点: http://localhost:{port}/api/track")
    logger.info(f"   行动执行: http://localhost:{port}/api/execute_action")
    logger.info("   按 Ctrl+C 停止服务器")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\n✓ 追踪服务器已停止")
        httpd.shutdown()
    finally:
        if hot_cache.get_size():
            logger.info("↻ 正在刷新热缓存中的追踪数据…")
        sync_hot_cache_to_warm_storage(hot_cache, db)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Digest Tracking Server')
    parser.add_argument('--port', type=int, default=8000, help='服务器端口')
    args = parser.parse_args()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    run_server(port=args.port)