#!/usr/bin/env python3
"""
调试Poe API返回内容
查看Claude到底返回了什么
"""

import os
import asyncio
from fastapi_poe import get_bot_response
from fastapi_poe.types import ProtocolMessage


async def debug_response():
    """调试Claude的响应"""
    
    api_key = os.getenv('POE_API_KEY')
    model = "Claude-Haiku-4.5"
    
    # 使用周报实际的prompt
    prompt = """你是一个AI工程师的技术助理，负责分析技术更新信息。

用户背景：
- 角色：AI Engineer / Generative AI Engineer
- 当前阶段：第3个月
- 当前主题：LLM编排和LangChain
- 当前重点：OpenAI API编排, LangChain组件使用, Function Calling, Prompt Engineering

请分析以下技术更新：

来源：LangGraph
标题：1.0.2
内容：## What's Changed
* Fix UntrackedValue persistence issue
* Add Overwrite reducer bypass
* Upgrade Checkpointers to 3.0

请提供以下分析（JSON格式）：

1. **summary** (3句话总结):
   - 第1句：这是什么（What）
   - 第2句：为什么重要（Why）
   - 第3句：具体变化（How）

2. **relevance_score** (0-10评分):
   - 10分：直接影响用户当前项目，必须立即关注
   - 7-9分：相关性高，建议本周了解
   - 4-6分：有价值，可以收藏稍后阅读
   - 0-3分：不相关

3. **why_matters** (1-2句话):
   解释为什么这个更新对用户重要

4. **impact_analysis** (1-2句话，可执行建议):
   具体说明对用户的影响和建议行动
   例如："立即升级到1.0.30，否则你第3个月的项目会崩溃"

5. **category** (选一个):
   - headline: 头条新闻（重大发布）
   - framework: 框架更新（LangChain等）
   - model: 新模型/平台
   - article: 技术文章
   - project: 开源项目
   - other: 其他

6. **actionable** (true/false):
   是否需要用户采取行动（如升级、测试、学习）

请以JSON格式返回，不要包含```json标记：
"""
    
    print("=" * 70)
    print("🔍 调试Poe API响应")
    print("=" * 70)
    print("\n⏳ 发送请求...\n")
    
    message = ProtocolMessage(role="user", content=prompt)
    
    full_response = ""
    async for partial in get_bot_response(
        messages=[message],
        bot_name=model,
        api_key=api_key
    ):
        full_response += partial.text
    
    print("📄 完整响应：")
    print("=" * 70)
    print(full_response)
    print("=" * 70)
    print()
    
    # 显示响应的前后字符
    print(f"📊 响应分析：")
    print(f"  - 长度: {len(full_response)} 字符")
    print(f"  - 前10个字符: {repr(full_response[:10])}")
    print(f"  - 后10个字符: {repr(full_response[-10:])}")
    print()
    
    # 尝试解析JSON
    print("🧪 尝试JSON解析...")
    import json
    
    # 原始解析
    try:
        data = json.loads(full_response)
        print("✅ 原始解析成功！")
        return
    except json.JSONDecodeError as e:
        print(f"❌ 原始解析失败: {str(e)}")
    
    # 清理后解析
    try:
        cleaned = full_response.replace('```json', '').replace('```', '').strip()
        data = json.loads(cleaned)
        print("✅ 清理后解析成功！")
        print(f"   需要清理的字符数: {len(full_response) - len(cleaned)}")
        return
    except json.JSONDecodeError as e:
        print(f"❌ 清理后仍然失败: {str(e)}")
    
    # 尝试找到JSON部分
    print("\n🔍 尝试提取JSON部分...")
    if '{' in full_response and '}' in full_response:
        start = full_response.find('{')
        end = full_response.rfind('}') + 1
        json_part = full_response[start:end]
        
        print(f"  - 找到JSON开始位置: {start}")
        print(f"  - 找到JSON结束位置: {end}")
        print(f"\n提取的JSON:")
        print("-" * 70)
        print(json_part)
        print("-" * 70)
        
        try:
            data = json.loads(json_part)
            print("\n✅ 提取后解析成功！")
            print(f"   前面多余的文字: {repr(full_response[:start])}")
            print(f"   后面多余的文字: {repr(full_response[end:])}")
        except json.JSONDecodeError as e:
            print(f"\n❌ 提取后仍然失败: {str(e)}")


if __name__ == "__main__":
    asyncio.run(debug_response())

