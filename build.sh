#!/bin/bash
# Build script for Render deployment

# Update package list
apt-get update

# Install ffmpeg and other required system dependencies
apt-get install -y ffmpeg

# Install Python dependencies
pip install -r requirements.txt

echo "Build completed successfully!" 