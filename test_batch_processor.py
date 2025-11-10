"""
快速测试批量处理器
验证1次API调用能否正常筛选和分析新闻
"""

import sys
import os
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.processors.ai_processor_batch import AIProcessorBatch
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def test_batch_processor():
    """测试批量处理器"""
    
    print("=" * 70)
    print("批量处理器测试")
    print("=" * 70)
    
    # 准备测试数据（模拟采集到的新闻）
    test_items = [
        {
            'source': 'VentureBeat AI',
            'title': 'Databricks research reveals AI judges problem',
            'summary': 'Building better AI judges is not just technical...',
            'url': 'https://example.com/1',
            'published_date': '2025-11-04'
        },
        {
            'source': 'The Verge AI',
            'title': 'Google Maps taps Gemini AI copilot',
            'summary': 'Google announces Gemini integration...',
            'url': 'https://example.com/2',
            'published_date': '2025-11-05'
        },
        {
            'source': 'Hacker News',
            'title': 'Show HN: LLM-based code generator',
            'summary': 'New tool for automatic code generation...',
            'url': 'https://example.com/3',
            'published_date': '2025-11-04'
        },
        {
            'source': 'LangChain',
            'title': 'LangChain v1.0.3 Release',
            'summary': 'Bug fixes and performance improvements...',
            'url': 'https://github.com/langchain-ai/langchain/releases/v1.0.3',
            'published_date': '2025-11-03'
        },
        {
            'source': 'MIT Tech Review AI',
            'title': 'AGI conspiracy theory discussion',
            'summary': 'Analysis of AGI development claims...',
            'url': 'https://example.com/5',
            'published_date': '2025-10-30'
        }
    ]
    
    print(f"\n📋 测试数据: {len(test_items)} 条新闻")
    for i, item in enumerate(test_items, 1):
        print(f"  {i}. [{item['source']}] {item['title']}")
    
    # 检查API key
    api_key = os.getenv('POE_API_KEY')
    if not api_key:
        print("\n❌ 错误: 未设置POE_API_KEY环境变量")
        print("   请在.env文件中设置: POE_API_KEY=your_key")
        return False
    
    print(f"\n✓ API Key已设置: {api_key[:10]}...")
    
    # 创建批量处理器
    try:
        processor = AIProcessorBatch(api_key=api_key)
        print("✓ 批量处理器创建成功")
    except Exception as e:
        print(f"❌ 创建处理器失败: {str(e)}")
        return False
    
    # 执行批量处理
    print("\n" + "=" * 70)
    print("开始批量处理（1次API调用）")
    print("=" * 70)
    
    try:
        processed = processor.batch_select_and_analyze(
            all_items=test_items,
            top_n=5  # 从5条中选出最重要的3条
        )
        
        print("\n" + "=" * 70)
        print("✓ 批量处理成功！")
        print("=" * 70)
        
        print(f"\n📊 处理结果: {len(processed)} 条")
        
        for i, item in enumerate(processed, 1):
            print(f"\n{i}. [{item.source}] {item.title}")
            print(f"   分类: {item.category}")
            print(f"   相关性: {item.relevance_score}/10")
            print(f"   头条优先级: {item.headline_priority}/10")
            print(f"   摘要: {item.summary[:100]}...")
            print(f"   为何重要: {item.why_matters[:80]}...")
        
        # 统计
        categories = {}
        for item in processed:
            categories[item.category] = categories.get(item.category, 0) + 1
        
        print(f"\n📂 分类分布: {categories}")
        
        # 验证媒体新闻是否被正确分类为headline
        media_headlines = [
            item for item in processed 
            if item.category == 'headline' 
            and any(src in item.source for src in ['VentureBeat', 'The Verge', 'MIT Tech Review'])
        ]
        
        print(f"\n✓ 媒体新闻被分类为headline: {len(media_headlines)} 条")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 批量处理失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_batch_processor()
    
    if success:
        print("\n" + "=" * 70)
        print("✅ 测试通过！批量处理器工作正常")
        print("=" * 70)
        print("\n下一步: 运行完整周报生成")
        print("  cd /Users/david/Documents/ai-weekly-report")
        print("  python -m src.main")
    else:
        print("\n" + "=" * 70)
        print("❌ 测试失败，请检查错误信息")
        print("=" * 70)
        sys.exit(1)

