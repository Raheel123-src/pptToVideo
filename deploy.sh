#!/bin/bash

echo "🚀 Deploying PDF to Video API to Modal Pro Tier..."

# Install Modal if not already installed
if ! command -v modal &> /dev/null; then
    echo "📦 Installing Modal..."
    pip install modal
fi

# Check if user is logged in
if ! modal token current &> /dev/null; then
    echo "🔐 Please log in to Modal first:"
    modal token new
    exit 1
fi

# Set up Modal secrets for Pro tier
echo "🔐 Setting up Modal secrets for Pro tier..."
echo "Creating OpenAI API key secret..."
modal secret create openai-api-key OPENAI_API_KEY=your_openai_key_here

echo "Creating AWS credentials secret..."
modal secret create aws-credentials AWS_ACCESS_KEY_ID=your_aws_key AWS_SECRET_ACCESS_KEY=your_aws_secret AWS_DEFAULT_REGION=us-east-1

# Deploy the Pro tier application
echo "🌐 Deploying Pro tier application..."
modal deploy modal_app.py

echo "✅ Pro tier deployment complete!"
echo ""
echo "🚀 Pro Tier Features:"
echo "   - 8GB RAM per function"
echo "   - 4 CPU cores per function"
echo "   - 10,000 function calls/day"
echo "   - 100GB storage"
echo "   - 1TB bandwidth/month"
echo "   - GPU acceleration (T4)"
echo "   - Warm instances for faster response"
echo ""
echo "🌐 Your API endpoints:"
echo "   - PDF + Audio: https://pdf-to-video-api-pro--upload-pdf-audio-endpoint-pro.modal.run"
echo "   - PowerPoint + Audio: https://pdf-to-video-api-pro--upload-ppt-audio-endpoint-pro.modal.run"
echo "   - Health Check: https://pdf-to-video-api-pro--health-pro.modal.run"
echo "   - Status: https://pdf-to-video-api-pro--status-pro.modal.run"
echo ""
echo "💰 Monthly Cost: $25 + usage-based charges"
echo "📈 Monitor usage: modal app logs pdf-to-video-api-pro" 