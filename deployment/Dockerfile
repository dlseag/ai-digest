# Multi-stage build for AWS Lambda
# Stage 1: Build stage
FROM public.ecr.aws/lambda/python:3.11 as builder

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt -t /app/python

# Stage 2: Runtime stage
FROM public.ecr.aws/lambda/python:3.11

WORKDIR ${LAMBDA_TASK_ROOT}

# Copy installed dependencies
COPY --from=builder /app/python ${LAMBDA_TASK_ROOT}

# Copy application code
COPY src/ ${LAMBDA_TASK_ROOT}/src/
COPY config/ ${LAMBDA_TASK_ROOT}/config/
COPY templates/ ${LAMBDA_TASK_ROOT}/templates/

# Copy Lambda handler
COPY deployment/lambda_function.py ${LAMBDA_TASK_ROOT}/

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${LAMBDA_TASK_ROOT}"

# Lambda handler
CMD ["lambda_function.handler"]

