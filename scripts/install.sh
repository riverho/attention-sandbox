#!/bin/bash
# scripts/install.sh — Install attention-sandbox as a Pi skill

set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "🛡️  Installing Attention Sandbox..."
echo "   Source: $SKILL_DIR"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ python3 not found. Please install Python 3.9+"
    exit 1
fi

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 not found. Please install pip."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip3 install pyyaml 2>/dev/null || pip install pyyaml

# Verify import
echo "🔍 Verifying import..."
python3 -c "from sandbox import SandboxMap, HILApprover, SandboxInterceptor, get_all_tools; print('✅ Sandbox imports OK')"

# Link to Pi skill locations
echo "🔗 Linking to Pi skill locations..."
PI_GLOBAL_SKILLS="$HOME/.pi/agent/skills"
OPENCLAW_SKILLS="$HOME/.openclaw/skills"

mkdir -p "$PI_GLOBAL_SKILLS"
mkdir -p "$OPENCLAW_SKILLS"

# Create symlinks (or copy if symlinks not preferred)
if [ ! -L "$PI_GLOBAL_SKILLS/attention-sandbox" ]; then
    ln -s "$SKILL_DIR" "$PI_GLOBAL_SKILLS/attention-sandbox" 2>/dev/null || \
        cp -r "$SKILL_DIR" "$PI_GLOBAL_SKILLS/attention-sandbox"
    echo "   → Linked to ~/.pi/agent/skills/"
fi

if [ ! -L "$OPENCLAW_SKILLS/attention-sandbox" ]; then
    ln -s "$SKILL_DIR" "$OPENCLAW_SKILLS/attention-sandbox" 2>/dev/null || \
        cp -r "$SKILL_DIR" "$OPENCLAW_SKILLS/attention-sandbox"
    echo "   → Linked to ~/.openclaw/skills/"
fi

# Create .wenmei marker in current dir if not exists
if [ ! -d ".wenmei" ]; then
    mkdir -p .wenmei
    echo '{"version":1}' > .wenmei/vault.json
    echo "   → Created .wenmei/ vault marker"
fi

echo ""
echo "✅ Attention Sandbox installed!"
echo ""
echo "Try the REPL:"
echo "   python -m sandbox.repl"
echo ""
echo "Or use in Pi:"
echo "   /skill:attention-sandbox"
