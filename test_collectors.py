#!/usr/bin/env python3
"""
快速测试各个采集器
"""

import yaml
import time

def test_hackernews():
    """测试HackerNews采集器"""
    print("=" * 60)
    print("测试 Hacker News 采集器")
    print("=" * 60)
    
    from src.collectors.hackernews_collector import HackerNewsCollector
    
    start = time.time()
    collector = HackerNewsCollector(
        query_tags=["AI", "LLM"],  # 只测试2个关键词
        min_points=100  # 提高门槛，减少数量
    )
    items = collector.collect(days_back=3)  # 只采集3天
    elapsed = time.time() - start
    
    print(f"✓ 采集完成: {len(items)} 条目")
    print(f"⏱️  耗时: {elapsed:.2f}秒")
    
    if items:
        print(f"\n示例:")
        item = items[0]
        print(f"  标题: {item.title}")
        print(f"  点数: {item.points}")
    print()


def test_reddit():
    """测试Reddit采集器"""
    print("=" * 60)
    print("测试 Reddit 采集器")
    print("=" * 60)
    
    from src.collectors.reddit_collector import RedditCollector
    
    configs = [
        {
            'name': 'r/LocalLLaMA',
            'subreddit': 'LocalLLaMA',
            'category': 'community',
            'priority': 9,
            'limit': 5  # 只采集5个
        }
    ]
    
    start = time.time()
    collector = RedditCollector(configs)
    items = collector.collect_all(days_back=3)  # 只采集3天
    elapsed = time.time() - start
    
    print(f"✓ 采集完成: {len(items)} 条目")
    print(f"⏱️  耗时: {elapsed:.2f}秒")
    
    if items:
        print(f"\n示例:")
        item = items[0]
        print(f"  标题: {item.title}")
        print(f"  热度: {item.upvotes}分")
    print()


def test_rss():
    """测试RSS采集器（包含The Batch）"""
    print("=" * 60)
    print("测试 RSS 采集器（包含The Batch）")
    print("=" * 60)
    
    from src.collectors.rss_collector import RSSCollector
    
    # 只测试The Batch
    sources = [
        {
            'name': 'The Batch (DeepLearning.AI)',
            'url': 'https://www.deeplearning.ai/the-batch/feed/',
            'category': 'newsletter',
            'priority': 9
        }
    ]
    
    start = time.time()
    collector = RSSCollector(sources)
    items = collector.collect_all(days_back=7)
    elapsed = time.time() - start
    
    print(f"✓ 采集完成: {len(items)} 条目")
    print(f"⏱️  耗时: {elapsed:.2f}秒")
    
    if items:
        print(f"\n示例:")
        item = items[0]
        print(f"  标题: {item.title}")
        print(f"  来源: {item.source}")
    print()


if __name__ == "__main__":
    print("\n🧪 开始测试各个采集器\n")
    
    try:
        test_hackernews()
    except Exception as e:
        print(f"❌ HackerNews测试失败: {str(e)}\n")
    
    try:
        test_reddit()
    except Exception as e:
        print(f"❌ Reddit测试失败: {str(e)}\n")
    
    try:
        test_rss()
    except Exception as e:
        print(f"❌ RSS测试失败: {str(e)}\n")
    
    print("=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

