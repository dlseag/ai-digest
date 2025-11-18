#!/usr/bin/env python3
"""
简报质量测试脚本

测试内容：
1. 数据一致性：title、link、summary 是否匹配
2. 链接有效性：URL 格式是否正确
3. 版面完整性：必要的板块是否存在
4. 内容质量：summary 是否为空或过短
5. 分类正确性：论文是否在论文板块，新闻是否在头条板块
"""

import sys
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class ReportQualityTester:
    """简报质量测试器"""
    
    def __init__(self, html_path: str, json_path: str = None):
        """
        初始化测试器
        
        Args:
            html_path: HTML报告路径
            json_path: 原始JSON数据路径（可选）
        """
        self.html_path = Path(html_path)
        self.json_path = Path(json_path) if json_path else None
        self.soup = None
        self.original_data = None
        self.errors = []
        self.warnings = []
        self.stats = {
            'total_items': 0,
            'headlines': 0,
            'papers': 0,
            'empty_summaries': 0,
            'invalid_urls': 0,
            'data_mismatches': 0
        }
        
    def load_files(self):
        """加载文件"""
        # 加载HTML
        with open(self.html_path, 'r', encoding='utf-8') as f:
            self.soup = BeautifulSoup(f.read(), 'html.parser')
        
        # 加载原始JSON（如果提供）
        if self.json_path and self.json_path.exists():
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.original_data = json.load(f)
    
    def test_layout_completeness(self) -> bool:
        """测试版面完整性"""
        print("\n" + "=" * 80)
        print("📐 测试1: 版面完整性")
        print("=" * 80)
        
        passed = True
        
        # 检查必要的板块
        required_sections = {
            '今日头条': '🔥 今日头条',
            '深度': '📄 深度'
        }
        
        for name, pattern in required_sections.items():
            section = self.soup.find('h2', string=lambda x: x and pattern in x)
            if section:
                print(f"  ✅ {name}板块存在")
            else:
                print(f"  ❌ {name}板块缺失")
                self.errors.append(f"缺少{name}板块")
                passed = False
        
        # 检查必要的元素
        required_elements = {
            'title': ('title', '页面标题'),
            'container': ('div', '主容器', {'class': 'container'}),
            'item-card': ('div', '内容卡片', {'class': 'item-card'})
        }
        
        for key, (tag, desc, *attrs) in required_elements.items():
            kwargs = attrs[0] if attrs else {}
            element = self.soup.find(tag, **kwargs)
            if element:
                print(f"  ✅ {desc}存在")
            else:
                print(f"  ❌ {desc}缺失")
                self.errors.append(f"缺少{desc}")
                passed = False
        
        return passed
    
    def test_data_consistency(self) -> bool:
        """测试数据一致性"""
        print("\n" + "=" * 80)
        print("🔍 测试2: 数据一致性（Title vs Summary）")
        print("=" * 80)
        
        passed = True
        items = self.soup.find_all('div', class_='item-card')
        self.stats['total_items'] = len(items)
        
        print(f"\n总计检查: {len(items)} 条内容\n")
        
        for i, item in enumerate(items, 1):
            title_div = item.find('div', class_='item-title')
            if not title_div:
                continue
            
            title = title_div.text.strip()
            # 移除优先级标签
            title = re.sub(r'📊\s*\d+/10', '', title).strip()
            
            content_div = item.find('div', class_='item-content')
            if not content_div:
                self.warnings.append(f"条目 {i} 缺少内容区域")
                continue
            
            # 获取摘要
            paras = content_div.find_all('p')
            summary = ""
            for p in paras:
                text = p.text
                if '摘要' in text or '📝' in text:
                    summary = text.replace('📝 摘要：', '').replace('摘要：', '').strip()
                    break
            
            if not summary:
                self.warnings.append(f"条目 {i} 没有摘要")
                continue
            
            # 数据一致性检查
            is_consistent = self._check_consistency(title, summary)
            
            if is_consistent:
                print(f"  ✅ 条目 {i}: {title[:50]}...")
            else:
                print(f"  ⚠️  条目 {i}: {title[:50]}...")
                print(f"      摘要: {summary[:80]}...")
                self.warnings.append(f"条目 {i} 数据一致性可疑: {title[:30]}")
                self.stats['data_mismatches'] += 1
        
        if self.stats['data_mismatches'] > 0:
            print(f"\n⚠️  发现 {self.stats['data_mismatches']} 条潜在不一致")
            passed = False
        
        return passed
    
    def _check_consistency(self, title: str, summary: str) -> bool:
        """
        检查title和summary的一致性
        
        Args:
            title: 标题
            summary: 摘要
            
        Returns:
            是否一致
        """
        # 清理文本
        title_clean = re.sub(r'[^\w\s]', ' ', title.lower())
        summary_clean = re.sub(r'[^\w\s]', ' ', summary.lower())
        
        # 提取关键词（长度>3，排除常见词）
        stop_words = {'the', 'and', 'for', 'with', 'from', 'that', 'this', 'what', 
                     'when', 'where', 'like', 'have', 'been', 'will', 'can', 'are'}
        title_words = [w for w in title_clean.split() if len(w) > 3 and w not in stop_words]
        
        if not title_words:
            return True  # 无法判断
        
        # 检查关键词匹配率
        match_count = sum(1 for word in title_words if word in summary_clean)
        match_rate = match_count / len(title_words)
        
        # 匹配率低于20%认为不一致
        return match_rate >= 0.2
    
    def test_url_validity(self) -> bool:
        """测试URL有效性"""
        print("\n" + "=" * 80)
        print("🔗 测试3: URL有效性")
        print("=" * 80)
        
        passed = True
        items = self.soup.find_all('div', class_='item-card')
        
        print(f"\n总计检查: {len(items)} 条链接\n")
        
        for i, item in enumerate(items, 1):
            link = item.find('a', class_='item-link')
            if not link:
                print(f"  ❌ 条目 {i} 缺少链接")
                self.errors.append(f"条目 {i} 缺少链接")
                self.stats['invalid_urls'] += 1
                passed = False
                continue
            
            url = link.get('href', '')
            if not url:
                print(f"  ❌ 条目 {i} 链接为空")
                self.errors.append(f"条目 {i} 链接为空")
                self.stats['invalid_urls'] += 1
                passed = False
                continue
            
            # 验证URL格式
            try:
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    print(f"  ❌ 条目 {i} URL格式无效: {url}")
                    self.errors.append(f"条目 {i} URL格式无效")
                    self.stats['invalid_urls'] += 1
                    passed = False
                else:
                    # 检查是否是常见的有效域名
                    valid_domains = [
                        'arxiv.org', 'huggingface.co', 'paperswithcode.com',
                        'github.com', 'techcrunch.com', 'venturebeat.com',
                        'theverge.com', 'news.ycombinator.com', 'blog.google',
                        'openai.com', 'anthropic.com', 'simonwillison.net'
                    ]
                    
                    is_known_domain = any(domain in parsed.netloc for domain in valid_domains)
                    
                    if is_known_domain or len(parsed.netloc.split('.')) >= 2:
                        print(f"  ✅ 条目 {i}: {parsed.netloc}")
                    else:
                        print(f"  ⚠️  条目 {i}: 未知域名 {parsed.netloc}")
                        self.warnings.append(f"条目 {i} 使用未知域名: {parsed.netloc}")
            except Exception as e:
                print(f"  ❌ 条目 {i} URL解析失败: {str(e)}")
                self.errors.append(f"条目 {i} URL解析失败")
                self.stats['invalid_urls'] += 1
                passed = False
        
        return passed
    
    def test_content_quality(self) -> bool:
        """测试内容质量"""
        print("\n" + "=" * 80)
        print("📝 测试4: 内容质量")
        print("=" * 80)
        
        passed = True
        items = self.soup.find_all('div', class_='item-card')
        
        print(f"\n总计检查: {len(items)} 条内容\n")
        
        english_summaries = 0
        
        for i, item in enumerate(items, 1):
            title_div = item.find('div', class_='item-title')
            if not title_div:
                continue
            
            title = title_div.text.strip()
            title = re.sub(r'📊\s*\d+/10', '', title).strip()
            
            content_div = item.find('div', class_='item-content')
            if not content_div:
                print(f"  ❌ 条目 {i} 缺少内容: {title[:40]}...")
                self.errors.append(f"条目 {i} 缺少内容")
                passed = False
                continue
            
            # 检查摘要
            paras = content_div.find_all('p')
            summary = ""
            for p in paras:
                text = p.text
                if '摘要' in text or '📝' in text:
                    summary = text.replace('📝 摘要：', '').replace('摘要：', '').strip()
                    break
            
            # 检查摘要质量
            if not summary:
                print(f"  ❌ 条目 {i} 摘要为空: {title[:40]}...")
                self.errors.append(f"条目 {i} 摘要为空")
                self.stats['empty_summaries'] += 1
                passed = False
            elif len(summary) < 20:
                print(f"  ⚠️  条目 {i} 摘要过短 ({len(summary)}字): {title[:40]}...")
                self.warnings.append(f"条目 {i} 摘要过短")
                self.stats['empty_summaries'] += 1
            elif summary == '...':
                print(f"  ❌ 条目 {i} 摘要为占位符: {title[:40]}...")
                self.errors.append(f"条目 {i} 摘要为占位符")
                self.stats['empty_summaries'] += 1
                passed = False
            else:
                # 检查是否为中文摘要
                is_chinese = self._is_chinese_text(summary)
                if not is_chinese:
                    print(f"  ⚠️  条目 {i} 摘要非中文: {title[:40]}...")
                    print(f"      摘要: {summary[:60]}...")
                    self.warnings.append(f"条目 {i} 摘要非中文")
                    english_summaries += 1
                else:
                    print(f"  ✅ 条目 {i}: 摘要长度 {len(summary)} 字 (中文)")
        
        if english_summaries > 0:
            print(f"\n⚠️  发现 {english_summaries} 条非中文摘要")
        
        return passed
    
    def _is_chinese_text(self, text: str) -> bool:
        """
        检查文本是否主要为中文
        
        Args:
            text: 待检查文本
            
        Returns:
            是否为中文文本
        """
        if not text:
            return False
        
        # 统计中文字符数量
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        # 统计英文字母数量
        english_chars = sum(1 for char in text if char.isalpha() and ord(char) < 128)
        
        total_chars = len(text.replace(' ', '').replace('\n', ''))
        
        if total_chars == 0:
            return False
        
        # 如果中文字符占比超过30%，认为是中文文本
        chinese_ratio = chinese_chars / total_chars
        
        # 或者英文字符很少（允许一些专业术语如RAG、LLM）
        if chinese_ratio > 0.3 or (english_chars < 50 and chinese_chars > 10):
            return True
        
        return False
    
    def test_categorization(self) -> bool:
        """测试分类正确性"""
        print("\n" + "=" * 80)
        print("🏷️  测试5: 分类正确性")
        print("=" * 80)
        
        passed = True
        
        # 检查今日头条
        headlines_section = self.soup.find('h2', string=lambda x: x and '今日头条' in x)
        if headlines_section:
            items = []
            next_elem = headlines_section.find_next_sibling()
            while next_elem and next_elem.name == 'div' and 'item-card' in next_elem.get('class', []):
                items.append(next_elem)
                next_elem = next_elem.find_next_sibling()
            
            self.stats['headlines'] = len(items)
            print(f"\n📰 今日头条: {len(items)} 条")
            
            # 检查是否有论文混入
            for i, item in enumerate(items, 1):
                category = item.get('data-item-category', '')
                source = item.get('data-item-source', '')
                title = item.find('div', class_='item-title')
                title_text = title.text.strip() if title else ''
                
                # 检查是否是论文
                is_paper = (category == 'paper' or 
                           'arxiv' in source.lower() or
                           'hugging face papers' in source.lower() or
                           'papers with code' in source.lower())
                
                if is_paper:
                    print(f"  ❌ 条目 {i} 是论文但在头条板块: {title_text[:40]}...")
                    self.errors.append(f"论文混入头条板块: {title_text[:30]}")
                    passed = False
        
        # 检查深度/论文板块
        papers_section = self.soup.find('h2', string=lambda x: x and '深度' in x)
        if papers_section:
            items = []
            next_elem = papers_section.find_next_sibling()
            while next_elem and next_elem.name == 'div' and 'item-card' in next_elem.get('class', []):
                items.append(next_elem)
                next_elem = next_elem.find_next_sibling()
            
            self.stats['papers'] = len(items)
            print(f"\n📄 深度（论文）: {len(items)} 篇")
            
            # 检查是否有非论文混入
            for i, item in enumerate(items, 1):
                category = item.get('data-item-category', '')
                source = item.get('data-item-source', '')
                title = item.find('div', class_='item-title')
                title_text = title.text.strip() if title else ''
                
                # 检查是否不是论文
                is_not_paper = (category not in ['paper', 'Paper'] and
                               'arxiv' not in source.lower() and
                               'hugging face papers' not in source.lower() and
                               'papers with code' not in source.lower())
                
                if is_not_paper:
                    print(f"  ⚠️  条目 {i} 不是论文但在论文板块: {title_text[:40]}...")
                    self.warnings.append(f"非论文混入论文板块: {title_text[:30]}")
        
        return passed
    
    def test_metadata_completeness(self) -> bool:
        """测试元数据完整性"""
        print("\n" + "=" * 80)
        print("📋 测试6: 元数据完整性")
        print("=" * 80)
        
        passed = True
        items = self.soup.find_all('div', class_='item-card')
        
        print(f"\n总计检查: {len(items)} 条内容\n")
        
        required_metadata = ['data-item-id', 'data-item-title', 'data-item-url', 
                            'data-item-source', 'data-item-category']
        
        for i, item in enumerate(items, 1):
            missing = []
            for attr in required_metadata:
                if not item.get(attr):
                    missing.append(attr.replace('data-item-', ''))
            
            if missing:
                title = item.find('div', class_='item-title')
                title_text = title.text.strip()[:40] if title else 'Unknown'
                print(f"  ⚠️  条目 {i} 缺少元数据: {', '.join(missing)}")
                print(f"      标题: {title_text}...")
                self.warnings.append(f"条目 {i} 缺少元数据: {', '.join(missing)}")
            else:
                print(f"  ✅ 条目 {i} 元数据完整")
        
        return passed
    
    def test_model_configuration(self) -> bool:
        """测试模型配置"""
        print("\n" + "=" * 80)
        print("🤖 测试7: 模型配置")
        print("=" * 80)
        
        passed = True
        
        # 检查环境变量
        import os
        model = os.getenv('DEVELOPER_MODEL', 'Claude-Sonnet-4.5')
        print(f"  ℹ️  环境变量 DEVELOPER_MODEL: {model}")
        
        # 检查是否为推荐模型
        if 'Sonnet' in model or 'sonnet' in model:
            print(f"  ✅ 使用推荐模型: {model}")
        elif 'Haiku' in model or 'haiku' in model:
            print(f"  ⚠️  当前使用 Haiku 模型，建议使用 Sonnet 以获得更好的中文摘要质量")
            self.warnings.append(f"当前使用 {model}，建议使用 Sonnet")
        else:
            print(f"  ℹ️  当前模型: {model}")
        
        return passed
    
    def run_all_tests(self) -> bool:
        """运行所有测试"""
        print("\n" + "=" * 80)
        print("🧪 简报质量测试")
        print("=" * 80)
        print(f"文件: {self.html_path}")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 加载文件
        try:
            self.load_files()
        except Exception as e:
            print(f"\n❌ 文件加载失败: {str(e)}")
            return False
        
        # 运行测试
        results = {
            '版面完整性': self.test_layout_completeness(),
            '数据一致性': self.test_data_consistency(),
            'URL有效性': self.test_url_validity(),
            '内容质量': self.test_content_quality(),
            '分类正确性': self.test_categorization(),
            '元数据完整性': self.test_metadata_completeness(),
            '模型配置': self.test_model_configuration()
        }
        
        # 打印总结
        self.print_summary(results)
        
        # 返回总体结果
        return all(results.values()) and len(self.errors) == 0
    
    def print_summary(self, results: Dict[str, bool]):
        """打印测试总结"""
        print("\n" + "=" * 80)
        print("📊 测试总结")
        print("=" * 80)
        
        # 测试结果
        print("\n测试结果:")
        for test_name, passed in results.items():
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"  {test_name}: {status}")
        
        # 统计信息
        print("\n统计信息:")
        print(f"  总条目数: {self.stats['total_items']}")
        print(f"  今日头条: {self.stats['headlines']} 条")
        print(f"  论文: {self.stats['papers']} 篇")
        print(f"  空摘要: {self.stats['empty_summaries']} 条")
        print(f"  无效URL: {self.stats['invalid_urls']} 条")
        print(f"  数据不一致: {self.stats['data_mismatches']} 条")
        
        # 错误列表
        if self.errors:
            print(f"\n❌ 错误 ({len(self.errors)} 个):")
            for error in self.errors[:10]:  # 只显示前10个
                print(f"  - {error}")
            if len(self.errors) > 10:
                print(f"  ... 还有 {len(self.errors) - 10} 个错误")
        
        # 警告列表
        if self.warnings:
            print(f"\n⚠️  警告 ({len(self.warnings)} 个):")
            for warning in self.warnings[:10]:  # 只显示前10个
                print(f"  - {warning}")
            if len(self.warnings) > 10:
                print(f"  ... 还有 {len(self.warnings) - 10} 个警告")
        
        # 总体评价
        print("\n" + "=" * 80)
        if len(self.errors) == 0:
            if len(self.warnings) == 0:
                print("✅ 测试全部通过！简报质量优秀！")
            else:
                print(f"⚠️  测试通过，但有 {len(self.warnings)} 个警告需要关注")
        else:
            print(f"❌ 测试失败！发现 {len(self.errors)} 个错误")
        print("=" * 80 + "\n")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='简报质量测试')
    parser.add_argument('--html', type=str, 
                       default='output/weekly_report_2025-11-17.html',
                       help='HTML报告路径')
    parser.add_argument('--json', type=str,
                       default='output/collected_items_2025-11-17_163447.json',
                       help='原始JSON数据路径')
    args = parser.parse_args()
    
    # 创建测试器
    tester = ReportQualityTester(args.html, args.json)
    
    # 运行测试
    success = tester.run_all_tests()
    
    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

