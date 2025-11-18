"""
Retry Handler and Health Check for Data Collectors
数据采集器的重试机制和健康检查
"""

import logging
import time
import json
from pathlib import Path
from typing import Dict, Optional, Callable, Any, Tuple, List
from datetime import datetime, timedelta
from functools import wraps
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class RetryHandler:
    """重试处理器，实现指数退避重试机制"""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        retry_on_status: tuple = (429, 500, 502, 503, 504),
    ):
        """
        初始化重试处理器
        
        Args:
            max_retries: 最大重试次数
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
            backoff_factor: 退避因子
            retry_on_status: 需要重试的 HTTP 状态码
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retry_on_status = retry_on_status
    
    def retry_with_backoff(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Tuple[Any, Optional[Exception]]:
        """
        执行函数，失败时使用指数退避重试（快速失败策略）
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            (结果, 错误) 元组，如果成功则错误为 None
        """
        last_exception = None
        
        # 减少重试次数，加快失败速度
        max_attempts = min(self.max_retries + 1, 2)  # 最多尝试2次（初始+1次重试）
        
        for attempt in range(max_attempts):
            try:
                result = func(*args, **kwargs)
                return result, None
            except requests.exceptions.HTTPError as e:
                # 检查是否需要重试
                if e.response and e.response.status_code in self.retry_on_status:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = min(
                            self.base_delay * (self.backoff_factor ** attempt),
                            2.0  # 最大延迟2秒
                        )
                        logger.debug(
                            f"HTTP {e.response.status_code} 错误，{delay:.1f}秒后重试 "
                            f"(尝试 {attempt + 1}/{max_attempts})"
                        )
                        time.sleep(delay)
                        continue
                else:
                    # 不需要重试的错误（如 404, 403）
                    return None, e
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_exception = e
                if attempt < max_attempts - 1:
                    delay = min(
                        self.base_delay * (self.backoff_factor ** attempt),
                        2.0  # 最大延迟2秒
                    )
                    logger.debug(
                        f"网络错误 ({type(e).__name__})，{delay:.1f}秒后重试 "
                        f"(尝试 {attempt + 1}/{max_attempts})"
                    )
                    time.sleep(delay)
                    continue
                else:
                    # 最后一次尝试也失败，直接返回
                    return None, e
            except Exception as e:
                # 其他错误不重试
                return None, e
        
        return None, last_exception
    
    def create_session(self, timeout: float = 10.0) -> requests.Session:
        """
        创建带重试机制的 requests Session
        
        Args:
            timeout: 默认超时时间（秒），默认10秒
        
        Returns:
            配置好的 Session 对象
        """
        session = requests.Session()
        
        # 配置重试策略（快速失败策略）
        retry_strategy = Retry(
            total=1,  # 最多重试1次（初始+1次重试）
            backoff_factor=1.0,  # 固定延迟1秒
            status_forcelist=list(self.retry_on_status),
            allowed_methods=["GET", "HEAD"],
            connect=1,  # 连接错误最多重试1次
            read=1,  # 读取错误最多重试1次
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置默认 headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # 存储timeout到session对象，供后续使用
        session._default_timeout = timeout
        
        return session


class SourceHealthTracker:
    """数据源健康状态追踪器"""
    
    def __init__(self, health_db_path: Optional[Path] = None):
        """
        初始化健康追踪器
        
        Args:
            health_db_path: 健康状态数据库路径（JSON 文件）
        """
        if health_db_path is None:
            health_db_path = Path(__file__).parent.parent.parent / 'data' / 'source_health.json'
        
        self.health_db_path = health_db_path
        self.health_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._health_data: Dict[str, Dict] = self._load_health_data()
    
    def _load_health_data(self) -> Dict[str, Dict]:
        """加载健康状态数据"""
        if not self.health_db_path.exists():
            return {}
        
        try:
            with open(self.health_db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载健康状态数据失败: {e}")
            return {}
    
    def _save_health_data(self):
        """保存健康状态数据"""
        try:
            with open(self.health_db_path, 'w', encoding='utf-8') as f:
                json.dump(self._health_data, f, indent=2, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error(f"保存健康状态数据失败: {e}")
    
    def record_success(self, source_name: str, source_url: str):
        """记录成功采集"""
        key = f"{source_name}|{source_url}"
        
        if key not in self._health_data:
            self._health_data[key] = {
                'success_count': 0,
                'failure_count': 0,
                'last_success': None,
                'last_failure': None,
                'consecutive_failures': 0,
                'status': 'healthy',
            }
        
        self._health_data[key]['success_count'] += 1
        self._health_data[key]['last_success'] = datetime.now().isoformat()
        self._health_data[key]['consecutive_failures'] = 0
        self._health_data[key]['status'] = 'healthy'
        
        self._save_health_data()
    
    def record_failure(
        self,
        source_name: str,
        source_url: str,
        error_type: str,
        error_message: str,
        status_code: Optional[int] = None
    ):
        """记录采集失败"""
        key = f"{source_name}|{source_url}"
        
        if key not in self._health_data:
            self._health_data[key] = {
                'success_count': 0,
                'failure_count': 0,
                'last_success': None,
                'last_failure': None,
                'consecutive_failures': 0,
                'status': 'healthy',
            }
        
        self._health_data[key]['failure_count'] += 1
        self._health_data[key]['last_failure'] = datetime.now().isoformat()
        self._health_data[key]['consecutive_failures'] += 1
        self._health_data[key]['last_error_type'] = error_type
        self._health_data[key]['last_error_message'] = error_message[:200]  # 限制长度
        if status_code:
            self._health_data[key]['last_status_code'] = status_code
        
        # 根据连续失败次数更新状态
        consecutive = self._health_data[key]['consecutive_failures']
        if consecutive >= 5:
            self._health_data[key]['status'] = 'unhealthy'
        elif consecutive >= 3:
            self._health_data[key]['status'] = 'degraded'
        else:
            self._health_data[key]['status'] = 'healthy'
        
        self._save_health_data()
    
    def is_healthy(self, source_name: str, source_url: str) -> bool:
        """
        检查数据源是否健康
        
        Args:
            source_name: 源名称
            source_url: 源 URL
            
        Returns:
            是否健康（True）或应该跳过（False）
        """
        key = f"{source_name}|{source_url}"
        
        if key not in self._health_data:
            return True  # 新源默认健康
        
        status = self._health_data[key].get('status', 'healthy')
        consecutive_failures = self._health_data[key].get('consecutive_failures', 0)
        
        # 如果连续失败超过 5 次，标记为不健康
        if consecutive_failures >= 5:
            logger.debug(f"跳过不健康的数据源: {source_name} (连续失败 {consecutive_failures} 次)")
            return False
        
        # 如果状态为 unhealthy，跳过
        if status == 'unhealthy':
            logger.debug(f"跳过不健康的数据源: {source_name} (状态: {status})")
            return False
        
        return True
    
    def get_health_summary(self) -> Dict[str, Any]:
        """获取健康状态摘要"""
        total = len(self._health_data)
        healthy = sum(1 for v in self._health_data.values() if v.get('status') == 'healthy')
        degraded = sum(1 for v in self._health_data.values() if v.get('status') == 'degraded')
        unhealthy = sum(1 for v in self._health_data.values() if v.get('status') == 'unhealthy')
        
        return {
            'total': total,
            'healthy': healthy,
            'degraded': degraded,
            'unhealthy': unhealthy,
        }
    
    def get_unhealthy_sources(self) -> List[Dict[str, Any]]:
        """获取不健康的数据源列表"""
        unhealthy = []
        
        for key, data in self._health_data.items():
            if data.get('status') == 'unhealthy':
                source_name, source_url = key.split('|', 1)
                unhealthy.append({
                    'name': source_name,
                    'url': source_url,
                    'consecutive_failures': data.get('consecutive_failures', 0),
                    'last_failure': data.get('last_failure'),
                    'last_error': data.get('last_error_message', ''),
                })
        
        return unhealthy


# 全局实例
_retry_handler = RetryHandler()
_health_tracker = SourceHealthTracker()


def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """
    装饰器：为函数添加重试机制
    
    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = RetryHandler(max_retries=max_retries, base_delay=base_delay)
            result, error = handler.retry_with_backoff(func, *args, **kwargs)
            if error:
                raise error
            return result
        return wrapper
    return decorator

