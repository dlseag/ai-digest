# AWS 部署指南

本文档说明如何将AI Weekly Report Generator部署到AWS。

## 🎯 部署架构

```
EventBridge (每周五触发)
    ↓
Lambda Function (Container)
    ↓
├─ Secrets Manager (API Keys)
├─ S3 (存储报告)
└─ SES (发送邮件)
```

## 📋 前置要求

1. **AWS账号**
2. **AWS CLI** 安装并配置
   ```bash
   aws configure
   ```
3. **Docker** 已安装
4. **SAM CLI** (可选，用于SAM部署)
   ```bash
   pip install aws-sam-cli
   ```

## 🚀 部署方式

### 方式1：使用部署脚本（推荐）

#### 步骤1：设置环境变量

```bash
# 必需
export AWS_ACCOUNT_ID=your-aws-account-id
export AWS_REGION=us-east-1

# Lambda函数名（可选）
export AWS_LAMBDA_FUNCTION_NAME=ai-weekly-report-generator
```

#### 步骤2：运行部署脚本

```bash
cd deployment
./deploy.sh
```

这会自动完成：
- 构建Docker镜像
- 创建ECR仓库（如果不存在）
- 推送镜像到ECR

#### 步骤3：创建Lambda函数

**首次部署**：

```bash
# 1. 首先创建执行角色
aws iam create-role \
  --role-name lambda-ai-weekly-report-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# 2. 附加基本执行策略
aws iam attach-role-policy \
  --role-name lambda-ai-weekly-report-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# 3. 创建S3访问策略
aws iam put-role-policy \
  --role-name lambda-ai-weekly-report-role \
  --policy-name S3Access \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject"],
      "Resource": "arn:aws:s3:::ai-weekly-report-bucket/*"
    }]
  }'

# 4. 创建Lambda函数
aws lambda create-function \
  --function-name ai-weekly-report-generator \
  --package-type Image \
  --code ImageUri=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/ai-weekly-report:latest \
  --role arn:aws:iam::${AWS_ACCOUNT_ID}:role/lambda-ai-weekly-report-role \
  --timeout 900 \
  --memory-size 1024 \
  --region ${AWS_REGION}
```

**更新现有函数**：

```bash
aws lambda update-function-code \
  --function-name ai-weekly-report-generator \
  --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/ai-weekly-report:latest \
  --region ${AWS_REGION}
```

#### 步骤4：配置环境变量

```bash
aws lambda update-function-configuration \
  --function-name ai-weekly-report-generator \
  --environment Variables="{
    ANTHROPIC_API_KEY=your-anthropic-api-key,
    GITHUB_TOKEN=your-github-token,
    AWS_S3_BUCKET=ai-weekly-report-bucket,
    SENDER_EMAIL=your-email@example.com,
    RECIPIENT_EMAIL=your-email@example.com,
    SEND_EMAIL=true
  }"
```

⚠️ **安全提示**：生产环境应使用AWS Secrets Manager存储敏感信息。

#### 步骤5：创建S3存储桶

```bash
aws s3 mb s3://ai-weekly-report-bucket --region ${AWS_REGION}
```

#### 步骤6：配置EventBridge定时触发

```bash
# 创建规则（每周五下午2点UTC）
aws events put-rule \
  --name weekly-ai-report \
  --schedule-expression 'cron(0 14 ? * FRI *)' \
  --state ENABLED \
  --region ${AWS_REGION}

# 添加Lambda权限
aws lambda add-permission \
  --function-name ai-weekly-report-generator \
  --statement-id weekly-ai-report \
  --action 'lambda:InvokeFunction' \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:${AWS_REGION}:${AWS_ACCOUNT_ID}:rule/weekly-ai-report

# 添加目标
aws events put-targets \
  --rule weekly-ai-report \
  --targets "Id"="1","Arn"="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:ai-weekly-report-generator"
```

### 方式2：使用AWS SAM（推荐生产环境）

#### 步骤1：部署镜像到ECR

```bash
cd deployment
./deploy.sh
```

#### 步骤2：部署SAM应用

```bash
sam deploy \
  --template-file template.yaml \
  --stack-name ai-weekly-report \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    AnthropicApiKey=your-api-key \
    GitHubToken=your-github-token \
    SenderEmail=your-email@example.com \
    RecipientEmail=your-email@example.com \
    S3BucketName=ai-weekly-report-bucket
```

这会自动创建：
- Lambda函数
- S3存储桶
- IAM角色和策略
- EventBridge规则
- Secrets Manager密钥
- CloudWatch日志组

## 🔧 配置SES邮件（可选）

如果要发送邮件通知：

1. 验证发件人邮箱：
```bash
aws ses verify-email-identity --email-address your-email@example.com
```

2. 检查验证状态：
```bash
aws ses get-identity-verification-attributes --identities your-email@example.com
```

3. 点击验证邮件中的链接

## 📊 监控和日志

### 查看CloudWatch日志

```bash
aws logs tail /aws/lambda/ai-weekly-report-generator --follow
```

### 查看Lambda指标

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=ai-weekly-report-generator \
  --start-time 2024-01-01T00:00:00Z \
  --end-time 2024-12-31T23:59:59Z \
  --period 3600 \
  --statistics Average
```

### 查看S3中的报告

```bash
aws s3 ls s3://ai-weekly-report-bucket/reports/ --recursive
```

## 🧪 测试Lambda函数

### 手动触发

```bash
aws lambda invoke \
  --function-name ai-weekly-report-generator \
  --payload '{}' \
  response.json

cat response.json
```

### 查看执行结果

```bash
aws s3 ls s3://ai-weekly-report-bucket/reports/ --recursive | tail -1
```

## 💰 成本估算

- **Lambda执行**: ~$0.01/周（15分钟 × 1024MB）
- **S3存储**: ~$0.02/月（52个周报，约50KB每个）
- **SES邮件**: 免费（前62,000封）
- **Secrets Manager**: $0.40/月
- **CloudWatch日志**: ~$0.01/月
- **总计**: **~$0.50/月**

## 🔒 安全最佳实践

1. **使用Secrets Manager** 存储API密钥
2. **最小权限原则** 配置IAM角色
3. **启用S3加密** 保护报告内容
4. **设置CloudWatch告警** 监控异常
5. **定期轮换密钥** 提高安全性

## 🔄 更新部署

```bash
# 1. 重新构建镜像
cd deployment
./deploy.sh

# 2. 更新Lambda函数
aws lambda update-function-code \
  --function-name ai-weekly-report-generator \
  --image-uri ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/ai-weekly-report:latest
```

## 🗑️ 清理资源

```bash
# 删除Lambda函数
aws lambda delete-function --function-name ai-weekly-report-generator

# 删除EventBridge规则
aws events remove-targets --rule weekly-ai-report --ids 1
aws events delete-rule --name weekly-ai-report

# 删除S3存储桶（先清空）
aws s3 rm s3://ai-weekly-report-bucket --recursive
aws s3 rb s3://ai-weekly-report-bucket

# 删除ECR仓库
aws ecr delete-repository --repository-name ai-weekly-report --force

# 删除IAM角色
aws iam delete-role --role-name lambda-ai-weekly-report-role
```

或使用SAM：

```bash
sam delete --stack-name ai-weekly-report
```

## 🆘 故障排查

### Lambda超时

```bash
# 增加超时时间
aws lambda update-function-configuration \
  --function-name ai-weekly-report-generator \
  --timeout 900
```

### 内存不足

```bash
# 增加内存
aws lambda update-function-configuration \
  --function-name ai-weekly-report-generator \
  --memory-size 2048
```

### 查看详细错误

```bash
aws logs filter-log-events \
  --log-group-name /aws/lambda/ai-weekly-report-generator \
  --filter-pattern "ERROR"
```

## 📞 支持

遇到问题？
1. 查看CloudWatch日志
2. 检查IAM权限配置
3. 验证环境变量设置
4. 提交GitHub Issue

