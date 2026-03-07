#!/bin/bash
# EduPulse Firewall Setup Script
# Usage: sudo bash firewall_setup.sh [dev|prod]

MODE=${1:-dev}
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           EduPulse Firewall & Network Security Setup           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root (use: sudo bash firewall_setup.sh)"
   exit 1
fi

# Check if UFW is available
if ! command -v ufw &> /dev/null; then
    echo "⚠️  UFW not found. Installing..."
    apt-get update && apt-get install -y ufw
fi

echo "🔧 Configuring firewall for $MODE mode..."
echo ""

# Reset UFW to defaults
echo "1️⃣  Resetting UFW to defaults..."
ufw --force reset > /dev/null 2>&1
echo "✅ Reset complete"

# Set default policies
echo "2️⃣  Setting default policies..."
ufw default deny incoming
ufw default allow outgoing
echo "✅ Default deny incoming, allow outgoing"

# Allow SSH to avoid lockout
echo "3️⃣  Allowing SSH (port 22)..."
ufw allow 22/tcp
echo "✅ SSH allowed"

# Mode-specific rules
if [ "$MODE" == "dev" ]; then
    echo "4️⃣  Configuring for DEVELOPMENT mode..."
    ufw allow 5000/tcp comment "EduPulse Backend API"
    ufw allow 5173/tcp comment "EduPulse Frontend (Vite)"
    ufw allow 5433/tcp comment "EduPulse Database"
    echo "✅ Development ports allowed:"
    echo "   - 5000/tcp (Backend API)"
    echo "   - 5173/tcp (Frontend)"
    echo "   - 5433/tcp (Database)"
elif [ "$MODE" == "prod" ]; then
    echo "4️⃣  Configuring for PRODUCTION mode..."
    echo "   (App ports bound to localhost; use reverse proxy for external access)"
    echo "✅ Only SSH allowed"
else
    echo "❌ Unknown mode: $MODE"
    echo "Usage: sudo bash firewall_setup.sh [dev|prod]"
    exit 1
fi

# Enable UFW
echo "5️⃣  Enabling UFW..."
ufw --force enable > /dev/null 2>&1
echo "✅ UFW enabled"

# Show final status
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                        FIREWALL STATUS                         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
ufw status verbose
echo ""

# Port binding verification
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    BINDING CONFIGURATION                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
if [ "$MODE" == "dev" ]; then
    echo "📌 For development access from other machines, update .env:"
    echo "   BACKEND_BIND=0.0.0.0"
    echo "   DB_BIND=0.0.0.0"
    echo ""
    echo "   Then restart: docker-compose down && docker-compose up --build"
else
    echo "🔒 Production mode (secure defaults):"
    echo "   BACKEND_BIND=127.0.0.1"
    echo "   DB_BIND=127.0.0.1"
    echo ""
    echo "💡 Use a reverse proxy (Nginx/Apache) for external client access"
fi

echo ""
echo "✅ Firewall setup complete!"
echo ""
