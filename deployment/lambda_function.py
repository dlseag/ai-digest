"""
AWS Lambda Handler
Lambda函数入口点
"""

import json
import logging
import os
import sys
import boto3
from datetime import datetime
from pathlib import Path

# 添加路径
sys.path.insert(0, os.path.dirname(__file__))

from src.main import WeeklyReportGenerator

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS客户端
s3_client = boto3.client('s3')
ses_client = boto3.client('ses')


def handler(event, context):
    """
    Lambda函数入口
    
    Args:
        event: Lambda事件（EventBridge触发）
        context: Lambda上下文
        
    Returns:
        响应字典
    """
    logger.info("=== AI Weekly Report Lambda 开始执行 ===")
    logger.info(f"Event: {json.dumps(event)}")
    
    try:
        # 1. 生成周报
        logger.info("步骤 1: 生成周报")
        generator = WeeklyReportGenerator()
        
        # 使用临时目录（Lambda只有/tmp可写）
        output_dir = "/tmp/reports"
        os.makedirs(output_dir, exist_ok=True)
        
        generator.run(days_back=7, output_dir=output_dir)
        
        # 2. 上传到S3
        logger.info("步骤 2: 上传到S3")
        report_path = _find_latest_report(output_dir)
        s3_key = _upload_to_s3(report_path)
        
        # 3. 发送邮件通知（可选）
        if os.getenv('SEND_EMAIL', 'false').lower() == 'true':
            logger.info("步骤 3: 发送邮件")
            _send_email_notification(report_path, s3_key)
        
        logger.info("=== 周报生成成功 ===")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': '周报生成成功',
                's3_key': s3_key,
                'timestamp': datetime.now().isoformat()
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda执行失败: {str(e)}", exc_info=True)
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }


def _find_latest_report(output_dir: str) -> str:
    """查找最新的报告文件"""
    reports = list(Path(output_dir).glob("weekly_report_*.md"))
    if not reports:
        raise FileNotFoundError("未找到生成的报告")
    
    latest = max(reports, key=lambda p: p.stat().st_mtime)
    return str(latest)


def _upload_to_s3(file_path: str) -> str:
    """
    上传报告到S3
    
    Args:
        file_path: 本地文件路径
        
    Returns:
        S3 key
    """
    bucket = os.getenv('AWS_S3_BUCKET')
    if not bucket:
        logger.warning("未配置S3_BUCKET，跳过上传")
        return ""
    
    file_name = Path(file_path).name
    s3_key = f"reports/{datetime.now().year}/{file_name}"
    
    try:
        s3_client.upload_file(
            file_path,
            bucket,
            s3_key,
            ExtraArgs={'ContentType': 'text/markdown'}
        )
        logger.info(f"✓ 上传到S3: s3://{bucket}/{s3_key}")
        return s3_key
    except Exception as e:
        logger.error(f"S3上传失败: {str(e)}")
        raise


def _send_email_notification(report_path: str, s3_key: str):
    """
    通过SES发送邮件通知
    
    Args:
        report_path: 报告文件路径
        s3_key: S3对象键
    """
    sender = os.getenv('SENDER_EMAIL')
    recipient = os.getenv('RECIPIENT_EMAIL')
    
    if not sender or not recipient:
        logger.warning("未配置邮件地址，跳过发送")
        return
    
    # 读取报告内容（前500字符作为预览）
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    preview = content[:500] + "..."
    
    # 构建邮件
    subject = f"AI周报 - {datetime.now().strftime('%Y年%m月%d日')}"
    body_text = f"""
本周AI工程师周报已生成！

预览：
{preview}

完整报告：
S3: {s3_key}

---
AI Weekly Report Generator
    """
    
    try:
        response = ses_client.send_email(
            Source=sender,
            Destination={'ToAddresses': [recipient]},
            Message={
                'Subject': {'Data': subject},
                'Body': {'Text': {'Data': body_text}}
            }
        )
        logger.info(f"✓ 邮件已发送: {response['MessageId']}")
    except Exception as e:
        logger.error(f"邮件发送失败: {str(e)}")

