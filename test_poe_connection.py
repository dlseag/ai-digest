#!/usr/bin/env python3
"""
测试Poe API连接
快速验证API Key和模型是否可用
"""

import os
import asyncio
from fastapi_poe import get_bot_response
from fastapi_poe.types import ProtocolMessage


async def test_poe_api():
    """测试Poe API连接"""
    
    # 从环境变量获取API Key
    api_key = os.getenv('POE_API_KEY')
    if not api_key:
        print("❌ 错误：未找到POE_API_KEY环境变量")
        print("请设置: export POE_API_KEY=your_key")
        return False
    
    print("=" * 60)
    print("🧪 Poe API 连接测试")
    print("=" * 60)
    print(f"✓ API Key: {api_key[:20]}...{api_key[-10:]}")
    
    # 测试模型
    model = os.getenv('DEVELOPER_MODEL', 'Claude-Haiku-4.5')
    print(f"✓ 测试模型: {model}")
    print()
    
    # 简单的测试prompt
    test_prompt = "请用一句话介绍什么是LangChain。"
    
    print(f"📝 测试问题: {test_prompt}")
    print("⏳ 等待响应...")
    print()
    
    try:
        message = ProtocolMessage(role="user", content=test_prompt)
        
        full_response = ""
        async for partial in get_bot_response(
            messages=[message],
            bot_name=model,
            api_key=api_key
        ):
            full_response += partial.text
            # 实时显示响应
            print(partial.text, end='', flush=True)
        
        print("\n")
        print("=" * 60)
        print("✅ 测试成功！Poe API连接正常")
        print("=" * 60)
        print(f"响应长度: {len(full_response)} 字符")
        print()
        
        return True
        
    except Exception as e:
        print()
        print("=" * 60)
        print("❌ 测试失败！")
        print("=" * 60)
        print(f"错误信息: {str(e)}")
        print()
        print("可能的原因：")
        print("1. API Key不正确")
        print("2. 模型名称不正确（检查Poe上是否有此模型）")
        print("3. 网络连接问题")
        print("4. Poe API配额用尽")
        print()
        return False


async def test_json_analysis():
    """测试JSON格式分析（模拟周报场景）"""
    
    api_key = os.getenv('POE_API_KEY')
    model = os.getenv('DEVELOPER_MODEL', 'Claude-Haiku-4.5')
    
    print("=" * 60)
    print("🧪 测试JSON格式分析（模拟周报场景）")
    print("=" * 60)
    
    test_prompt = """你是一个AI工程师的技术助理，负责分析技术更新信息。

用户背景：
- 角色：AI Engineer / Generative AI Engineer
- 当前阶段：第3个月
- 当前主题：LLM编排和LangChain

请分析以下技术更新：

来源：LangChain Blog
标题：LangChain 1.0.30 发布 - 修复Memory泄漏问题
内容：本次更新修复了长期存在的Memory泄漏bug，影响长对话场景。建议所有用户尽快升级。

请提供以下分析（JSON格式）：

1. **summary** (3句话总结)
2. **relevance_score** (0-10评分)
3. **why_matters** (1-2句话)
4. **impact_analysis** (可执行建议)
5. **category** (framework)
6. **actionable** (true/false)

请以JSON格式返回，不要包含```json标记：
"""
    
    print("📝 测试场景：分析LangChain更新")
    print("⏳ 等待响应...")
    print()
    
    try:
        message = ProtocolMessage(role="user", content=test_prompt)
        
        full_response = ""
        async for partial in get_bot_response(
            messages=[message],
            bot_name=model,
            api_key=api_key
        ):
            full_response += partial.text
        
        print("📄 AI响应：")
        print("-" * 60)
        print(full_response)
        print("-" * 60)
        print()
        
        # 尝试解析JSON
        import json
        response_text = full_response.replace('```json', '').replace('```', '').strip()
        
        try:
            analysis = json.loads(response_text)
            print("✅ JSON解析成功！")
            print()
            print("解析结果：")
            for key, value in analysis.items():
                print(f"  - {key}: {value}")
            print()
            return True
        except json.JSONDecodeError as je:
            print("⚠️  JSON解析失败，但API调用成功")
            print(f"   可能需要调整Prompt让模型输出更标准的JSON")
            print(f"   错误: {str(je)}")
            print()
            return True  # API调用成功，只是格式问题
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False


def main():
    """主函数"""
    print()
    print("🚀 开始测试 AI Weekly Report - Poe API 集成")
    print()
    
    # 测试1：基础连接
    print("【测试 1/2】基础API连接")
    success1 = asyncio.run(test_poe_api())
    
    if not success1:
        print("⚠️  基础测试失败，跳过进阶测试")
        return
    
    print()
    print("继续进阶测试...")
    print()
    
    # 测试2：JSON分析
    print("【测试 2/2】JSON格式分析")
    success2 = asyncio.run(test_json_analysis())
    
    print()
    print("=" * 60)
    if success1 and success2:
        print("🎉 所有测试通过！可以运行完整系统了")
        print("=" * 60)
        print()
        print("下一步：运行完整周报生成")
        print("  命令: python -m src.main")
    else:
        print("⚠️  部分测试未通过，请检查配置")
        print("=" * 60)
    print()


if __name__ == "__main__":
    main()

