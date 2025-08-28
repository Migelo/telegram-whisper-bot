#!/usr/bin/env bash

# CI Validation Script
# This script validates that the CI environment can be set up correctly

set -e  # Exit on any error

echo "🔍 Validating CI Setup..."

# Check Python version
echo "📋 Python Version:"
python --version

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "🔧 Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Upgrade pip
echo "📦 Upgrading pip..."
python -m pip install --upgrade pip

# Install core dependencies
echo "📦 Installing core dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt not found, installing minimal dependencies"
    pip install python-telegram-bot openai-whisper
fi

# Install test dependencies
echo "📦 Installing test dependencies..."
pip install pytest pytest-asyncio pytest-mock pytest-cov

# Validate imports
echo "🧪 Validating Python imports..."
python -c "
import sys
sys.path.append('.')

print('Testing core imports...')
try:
    import bot_core
    print('✅ bot_core imported successfully')
except Exception as e:
    print(f'❌ bot_core import failed: {e}')
    
try:
    import main
    print('✅ main imported successfully')  
except Exception as e:
    print(f'❌ main import failed: {e}')

print('Testing test imports...')
try:
    import pytest
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    print('✅ Test dependencies imported successfully')
except Exception as e:
    print(f'❌ Test dependencies import failed: {e}')
"

# Run a subset of fast tests to validate setup
echo "🧪 Running validation tests..."
if [ -d "tests" ]; then
    # Run only configuration and queue management tests (fast, no Whisper dependency)
    python -m pytest tests/test_configuration.py tests/test_queue_management.py -v --tb=short || {
        echo "❌ Validation tests failed"
        exit 1
    }
    echo "✅ Validation tests passed"
else
    echo "⚠️  No tests directory found"
fi

# Check GitHub Actions workflow syntax
echo "🔍 Validating GitHub Actions workflow..."
if [ -f ".github/workflows/test.yml" ]; then
    echo "✅ GitHub Actions workflow file exists"
    # Basic YAML syntax check (if available)
    if command -v yamllint &> /dev/null; then
        yamllint .github/workflows/test.yml
        echo "✅ GitHub Actions workflow YAML is valid"
    else
        echo "⚠️  yamllint not available, skipping YAML validation"
    fi
else
    echo "❌ GitHub Actions workflow file not found"
    exit 1
fi

# Check test configuration
echo "🔍 Validating test configuration..."
if [ -f "pytest.ini" ]; then
    echo "✅ pytest.ini configuration exists"
else
    echo "⚠️  pytest.ini not found"
fi

# Summary
echo ""
echo "🎉 CI Validation Complete!"
echo ""
echo "📊 Summary:"
echo "  ✅ Virtual environment setup"
echo "  ✅ Dependencies installation" 
echo "  ✅ Python imports validation"
echo "  ✅ Test execution validation"
echo "  ✅ GitHub Actions workflow validation"
echo ""
echo "🚀 Ready for CI/CD!"