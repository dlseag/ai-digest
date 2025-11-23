#!/usr/bin/env python3
"""
批量禁用出错的信源
根据运行日志中的错误，将出错的源设置为 enabled: false
"""

import yaml
from pathlib import Path

# 需要禁用的源列表（从日志分析得出）
SOURCES_TO_DISABLE = {
    # HTTP 404
    "Google DeepMind Blog",
    "Google Research",
    "AWS Generative AI Blog",
    "IBM Research AI",
    "Stability AI Blog",
    "Snowflake ML Blog",
    "LlamaIndex Blog",
    "vLLM Blog",
    "FastChat Blog",
    "Pinecone Learn",
    "Milvus Blog",
    "LanceDB Blog",
    "Haystack Blog",
    "Modal Blog",
    "Flyte Blog",
    "Supabase AI",
    "Stanford CRFM",
    "UW NLP",
    "ETH AI Center",
    "MILA Québec",
    "Naver AI Lab",
    "EPFL NLP Lab",
    "TUM AI Lab",
    "USC Viterbi AI",
    "LangSmith",
    "PromptLayer",
    "Ragas",
    "Braintrust Data",
    "Truera AI",
    "LightOn AI",
    "Scale Spellbook",
    "HoneyHive",
    "Evidently AI",
    "Semantic Scholar AI",
    "Open Source AI Radar",
    "Builder Bytes",
    "Daily Papers Digest",
    "Venture in AI",
    "Data Science at Home",
    "Applied LLMs",
    "AI with Vercel",
    "AI Notebooks by Hamel",
    "Jeremy Howard / fast.ai",
    "Eugene Yan",
    "Lilian Weng",
    "Jay Alammar",
    "Coactive AI",
    # HTTP 403
    "Arize AI",
    "Digamma AI",
    "Deepchecks",
    "Product Hunt AI",
    "Product Hunt Dev Tools",
    # HTTP 400
    "FAIR Publications",
    # 网络错误
    "Azure AI Blog",
    "Chroma Blog",
    "Oxford Applied AI",
    "Evals.art",
    "GitHub Trending AI",
    "Generative AI with Python",
    "PromptOps",
    # 500错误
    "Humanloop",
    "Helicone",
    "Aporia",
    "LessWrong AI",
}

def disable_sources():
    """禁用出错的源"""
    config_path = Path(__file__).parent.parent / "config" / "sources.yaml"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    disabled_count = 0
    not_found = []
    
    # 处理 rss_feeds
    if 'rss_feeds' in config:
        for source in config['rss_feeds']:
            if source.get('name') in SOURCES_TO_DISABLE:
                if source.get('enabled', True):
                    source['enabled'] = False
                    source['note'] = (source.get('note', '') + ' [已禁用：运行日志显示错误]').strip()
                    disabled_count += 1
                    print(f"✓ 已禁用: {source['name']}")
                else:
                    print(f"  (已禁用): {source['name']}")
                SOURCES_TO_DISABLE.discard(source['name'])
    
    # 处理 news_feeds
    if 'news_feeds' in config:
        for source in config['news_feeds']:
            if source.get('name') in SOURCES_TO_DISABLE:
                if source.get('enabled', True):
                    source['enabled'] = False
                    source['note'] = (source.get('note', '') + ' [已禁用：运行日志显示错误]').strip()
                    disabled_count += 1
                    print(f"✓ 已禁用: {source['name']}")
                else:
                    print(f"  (已禁用): {source['name']}")
                SOURCES_TO_DISABLE.discard(source['name'])
    
    # 检查未找到的源
    if SOURCES_TO_DISABLE:
        print(f"\n⚠️  以下源在配置中未找到:")
        for name in sorted(SOURCES_TO_DISABLE):
            print(f"  - {name}")
    
    # 保存配置
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    print(f"\n✅ 完成！共禁用 {disabled_count} 个源")
    print(f"📝 配置文件已更新: {config_path}")

if __name__ == '__main__':
    disable_sources()

