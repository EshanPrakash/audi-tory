#!/bin/bash
set -e

# config
FUNCTION_NAME="audi-tory-pipeline"
ROLE_NAME="audi-tory-lambda-role"
API_NAME="audi-tory-api"
RUNTIME="python3.11"

REGION=$(grep AWS_REGION ../.env | cut -d '=' -f2)
S3_BUCKET=$(grep S3_BUCKET ../.env | cut -d '=' -f2)
BEDROCK_MODEL_ID=$(grep BEDROCK_MODEL_ID ../.env | cut -d '=' -f2)

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "==> Account: $ACCOUNT_ID | Region: $REGION"

# STEP 1: create IAM role for Lambda (skips if already exists)
echo "==> Creating IAM role..."
TRUST_POLICY='{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}'

ROLE_ARN=$(aws iam create-role \
  --role-name "$ROLE_NAME" \
  --assume-role-policy-document "$TRUST_POLICY" \
  --query "Role.Arn" --output text 2>/dev/null || \
  aws iam get-role --role-name "$ROLE_NAME" --query "Role.Arn" --output text)

echo "    Role ARN: $ROLE_ARN"

# attach permissions for S3, Polly, Bedrock, and basic Lambda logging
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonPollyFullAccess
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

echo "    Waiting for role to propagate..."
sleep 10

# STEP 2: package code and dependencies into a zip for Lambda
echo "==> Packaging Lambda..."
rm -rf /tmp/lambda_pkg /tmp/lambda.zip

pip install -r requirements.txt -t /tmp/lambda_pkg --quiet

cp lambda_handler.py pipeline.py /tmp/lambda_pkg/

cd /tmp/lambda_pkg
zip -r /tmp/lambda.zip . --quiet
cd -

echo "    Package size: $(du -sh /tmp/lambda.zip | cut -f1)"

# STEP 3: create or update the Lambda function
echo "==> Deploying Lambda function..."
EXISTING=$(aws lambda get-function --function-name "$FUNCTION_NAME" \
  --region "$REGION" --query "Configuration.FunctionName" --output text 2>/dev/null || echo "")

ENV_VARS="Variables={S3_BUCKET=$S3_BUCKET,BEDROCK_MODEL_ID=$BEDROCK_MODEL_ID}"

if [ -z "$EXISTING" ]; then
  LAMBDA_ARN=$(aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime "$RUNTIME" \
    --role "$ROLE_ARN" \
    --handler lambda_handler.handler \
    --zip-file fileb:///tmp/lambda.zip \
    --timeout 180 \
    --memory-size 512 \
    --environment "$ENV_VARS" \
    --region "$REGION" \
    --query "FunctionArn" --output text)
  echo "    Created: $LAMBDA_ARN"
else
  # wait for any in-progress update to settle before pushing new code
  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" --region "$REGION"
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb:///tmp/lambda.zip \
    --region "$REGION" --output text > /dev/null
  aws lambda wait function-updated \
    --function-name "$FUNCTION_NAME" --region "$REGION"
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --environment "$ENV_VARS" \
    --region "$REGION" --output text > /dev/null
  LAMBDA_ARN="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION_NAME"
  echo "    Updated: $LAMBDA_ARN"
fi

# STEP 4: create API Gateway (skips if already exists)
echo "==> Setting up API Gateway..."
API_ID=$(aws apigatewayv2 get-apis --region "$REGION" \
  --query "Items[?Name=='$API_NAME'].ApiId | [0]" --output text)

if [ "$API_ID" == "None" ] || [ -z "$API_ID" ]; then
  API_ID=$(aws apigatewayv2 create-api \
    --name "$API_NAME" \
    --protocol-type HTTP \
    --cors-configuration '{"AllowOrigins":["*"],"AllowMethods":["POST","OPTIONS"],"AllowHeaders":["Content-Type"]}' \
    --region "$REGION" \
    --query "ApiId" --output text)
  echo "    Created API: $API_ID"

  INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id "$API_ID" \
    --integration-type AWS_PROXY \
    --integration-uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations" \
    --payload-format-version "2.0" \
    --region "$REGION" \
    --query "IntegrationId" --output text)

  aws apigatewayv2 create-route \
    --api-id "$API_ID" \
    --route-key "POST /process" \
    --target "integrations/$INTEGRATION_ID" \
    --region "$REGION" --output text > /dev/null

  aws apigatewayv2 create-stage \
    --api-id "$API_ID" \
    --stage-name "prod" \
    --auto-deploy \
    --region "$REGION" --output text > /dev/null

  aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "apigateway-invoke" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_ID/*/*/process" \
    --region "$REGION" --output text > /dev/null 2>&1 || true
else
  echo "    Existing API: $API_ID"
fi

API_URL="https://$API_ID.execute-api.$REGION.amazonaws.com/prod/process"

# STEP 5: S3 lifecycle rule — auto-delete audio files after 1 day
echo "==> Setting S3 lifecycle rule..."
aws s3api put-bucket-lifecycle-configuration \
  --bucket "$S3_BUCKET" \
  --lifecycle-configuration '{"Rules":[{"ID":"delete-old-audio","Status":"Enabled","Filter":{"Prefix":"pipeline_output"},"Expiration":{"Days":1}}]}' \
  --region "$REGION"
echo "    Audio files will be deleted after 1 day."

echo ""
echo "✓ Deployment complete!"
echo "  API endpoint: $API_URL"
echo ""
echo "  Test with:"
echo "  curl -X POST $API_URL \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"notes\": \"Photosynthesis converts sunlight to energy.\", \"style\": \"podcast\", \"length\": \"short\", \"voice\": \"Matthew\"}'"
echo ""
echo "  Save this URL — you'll need it for the React frontend."
