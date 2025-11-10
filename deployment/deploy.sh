#!/bin/bash

# AWS Lambda 部署脚本
# 使用方法: ./deploy.sh

set -e  # 遇到错误立即退出

echo "========================================="
echo "AI Weekly Report - AWS Lambda 部署"
echo "========================================="

# 配置变量
AWS_REGION="${AWS_REGION:-us-east-1}"
FUNCTION_NAME="${AWS_LAMBDA_FUNCTION_NAME:-ai-weekly-report-generator}"
IMAGE_NAME="ai-weekly-report"
ECR_REPO_NAME="ai-weekly-report"

# 检查必需的环境变量
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo "错误: 请设置 AWS_ACCOUNT_ID 环境变量"
    echo "例如: export AWS_ACCOUNT_ID=123456789012"
    exit 1
fi

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo ""
echo "配置信息:"
echo "  - AWS Region: $AWS_REGION"
echo "  - Function Name: $FUNCTION_NAME"
echo "  - ECR URI: $ECR_URI"
echo ""

# 步骤1: 构建Docker镜像
echo "步骤 1/5: 构建Docker镜像..."
cd ..
docker build -t $IMAGE_NAME:latest -f deployment/Dockerfile .

# 步骤2: 标记镜像
echo ""
echo "步骤 2/5: 标记Docker镜像..."
docker tag $IMAGE_NAME:latest $ECR_URI:latest

# 步骤3: 登录ECR
echo ""
echo "步骤 3/5: 登录AWS ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URI

# 步骤4: 创建ECR仓库（如果不存在）
echo ""
echo "步骤 4/5: 检查/创建ECR仓库..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION 2>/dev/null || \
    aws ecr create-repository --repository-name $ECR_REPO_NAME --region $AWS_REGION

# 步骤5: 推送镜像到ECR
echo ""
echo "步骤 5/5: 推送镜像到ECR..."
docker push $ECR_URI:latest

echo ""
echo "========================================="
echo "✓ Docker镜像已推送到ECR"
echo "========================================="
echo ""
echo "下一步: 创建或更新Lambda函数"
echo ""
echo "如果是首次部署，运行:"
echo "  aws lambda create-function \\"
echo "    --function-name $FUNCTION_NAME \\"
echo "    --package-type Image \\"
echo "    --code ImageUri=$ECR_URI:latest \\"
echo "    --role arn:aws:iam::$AWS_ACCOUNT_ID:role/lambda-execution-role \\"
echo "    --timeout 900 \\"
echo "    --memory-size 1024 \\"
echo "    --region $AWS_REGION"
echo ""
echo "如果是更新现有函数，运行:"
echo "  aws lambda update-function-code \\"
echo "    --function-name $FUNCTION_NAME \\"
echo "    --image-uri $ECR_URI:latest \\"
echo "    --region $AWS_REGION"
echo ""
echo "配置EventBridge定时触发（每周五下午2点）:"
echo "  aws events put-rule \\"
echo "    --name weekly-ai-report \\"
echo "    --schedule-expression 'cron(0 14 ? * FRI *)' \\"
echo "    --region $AWS_REGION"
echo ""

