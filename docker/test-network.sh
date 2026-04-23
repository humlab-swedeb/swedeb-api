#!/bin/bash
# Network troubleshooting script for Swedeb API container
# Usage: 
#   From host: podman exec -it <container-name> /app/docker/test-network.sh
#   From container: /app/docker/test-network.sh

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_section() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

log_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_error() {
    echo -e "${RED}✗ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

test_command() {
    if command -v "$1" >/dev/null 2>&1; then
        log_success "$1 is installed"
        return 0
    else
        log_error "$1 is NOT installed"
        return 1
    fi
}

test_dns_resolution() {
    local host="$1"
    
    if command -v nslookup >/dev/null 2>&1; then
        if nslookup "$host" >/dev/null 2>&1; then
            log_success "DNS resolution for $host (nslookup)"
            nslookup "$host" | grep -A2 "Name:" || true
        else
            log_error "DNS resolution failed for $host (nslookup)"
            return 1
        fi
    elif command -v dig >/dev/null 2>&1; then
        if dig +short "$host" >/dev/null 2>&1; then
            log_success "DNS resolution for $host (dig)"
            dig +short "$host"
        else
            log_error "DNS resolution failed for $host (dig)"
            return 1
        fi
    elif command -v host >/dev/null 2>&1; then
        if host "$host" >/dev/null 2>&1; then
            log_success "DNS resolution for $host (host)"
            host "$host" | head -n 3
        else
            log_error "DNS resolution failed for $host (host)"
            return 1
        fi
    else
        log_warning "No DNS tools available (nslookup, dig, host)"
        return 2
    fi
    return 0
}

test_ping() {
    local host="$1"
    
    if ! command -v ping >/dev/null 2>&1; then
        log_warning "ping not installed, skipping connectivity test"
        return 2
    fi
    
    if ping -c 3 -W 2 "$host" >/dev/null 2>&1; then
        log_success "Ping to $host successful"
    else
        log_error "Ping to $host failed"
        return 1
    fi
    return 0
}

test_http_connectivity() {
    local url="$1"
    
    if ! command -v curl >/dev/null 2>&1; then
        log_error "curl not installed - required for HTTP testing"
        return 1
    fi
    
    echo -n "Testing HTTP connectivity to $url... "
    if curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" | grep -q "200\|301\|302"; then
        log_success "HTTP connection to $url successful"
    else
        log_error "HTTP connection to $url failed"
        echo "Verbose curl output:"
        curl -v --connect-timeout 5 "$url" 2>&1 | head -n 20
        return 1
    fi
    return 0
}

test_github_download() {
    local url="https://github.com/humlab-swedeb/swedeb_frontend/releases/download/frontend-staging/frontend-staging.tar.gz"
    
    echo -n "Testing GitHub tarball download... "
    if curl -L --fail --connect-timeout 10 --max-time 30 -o /dev/null "$url" 2>/dev/null; then
        log_success "GitHub tarball download successful"
    else
        log_error "GitHub tarball download failed"
        echo "Verbose curl output:"
        curl -L -v --connect-timeout 10 --max-time 30 "$url" 2>&1 | head -n 30
        return 1
    fi
    return 0
}

# Main execution
log_section "Network Troubleshooting Script"
echo "Container: $(hostname)"
echo "Date: $(date)"

log_section "1. Basic Tools Check"
test_command curl || true
test_command wget || true
test_command ping || true
test_command nslookup || true
test_command dig || true
test_command host || true
test_command netstat || true
test_command ss || true

log_section "2. Network Configuration"
echo "Network interfaces:"
if command -v ip >/dev/null 2>&1; then
    ip addr show | grep -E "^[0-9]+:|inet " || true
elif command -v ifconfig >/dev/null 2>&1; then
    ifconfig | grep -E "^[a-z]+[0-9]+:|inet " || true
else
    log_warning "No network interface tools available"
fi

echo -e "\nDNS Configuration (/etc/resolv.conf):"
cat /etc/resolv.conf 2>/dev/null || log_warning "/etc/resolv.conf not readable"

echo -e "\nDefault route:"
if command -v ip >/dev/null 2>&1; then
    ip route show default || log_warning "No default route found"
elif command -v route >/dev/null 2>&1; then
    route -n | grep "^0.0.0.0" || log_warning "No default route found"
else
    log_warning "No routing tools available"
fi

log_section "3. DNS Resolution Tests"
test_dns_resolution "github.com" || true
test_dns_resolution "api.github.com" || true
test_dns_resolution "google.com" || true

# Try with specific DNS server if resolution fails
if ! test_dns_resolution "github.com" >/dev/null 2>&1; then
    echo -e "\nTrying with Google DNS (8.8.8.8):"
    if command -v nslookup >/dev/null 2>&1; then
        nslookup github.com 8.8.8.8 2>&1 || true
    fi
fi

log_section "4. Network Connectivity Tests"
test_ping "8.8.8.8" || log_warning "Cannot ping Google DNS"
test_ping "1.1.1.1" || log_warning "Cannot ping Cloudflare DNS"

# Only test ping to github.com if DNS works
if test_dns_resolution "github.com" >/dev/null 2>&1; then
    test_ping "github.com" || log_warning "Cannot ping github.com"
fi

log_section "5. HTTP/HTTPS Connectivity Tests"
test_http_connectivity "https://www.google.com" || true
test_http_connectivity "https://github.com" || true
test_http_connectivity "https://api.github.com" || true

log_section "6. GitHub API Test"
if command -v curl >/dev/null 2>&1; then
    echo "Testing GitHub API access..."
    if RESPONSE=$(curl -s --connect-timeout 10 https://api.github.com/repos/humlab-swedeb/swedeb_frontend/releases/latest 2>&1); then
        log_success "GitHub API accessible"
        echo "$RESPONSE" | grep -o '"tag_name":[^,]*' | head -n 1 || true
    else
        log_error "GitHub API not accessible"
        echo "Error: $RESPONSE"
    fi
fi

log_section "7. GitHub Tarball Download Test"
test_github_download || true

log_section "8. Summary and Recommendations"
echo ""

# Check for common issues
if ! test_dns_resolution "github.com" >/dev/null 2>&1; then
    echo -e "${RED}ISSUE: DNS resolution is not working${NC}"
    echo "Recommendation: Add DNS servers to your container configuration"
    echo "  - In compose.yml, add:"
    echo "    dns:"
    echo "      - 8.8.8.8"
    echo "      - 8.8.4.4"
    echo ""
fi

if ! test_ping "8.8.8.8" >/dev/null 2>&1; then
    echo -e "${RED}ISSUE: Cannot reach external networks${NC}"
    echo "Recommendation: Check firewall and network configuration"
    echo "  - Verify podman network: podman network inspect <network-name>"
    echo "  - Check host firewall: sudo firewall-cmd --list-all"
    echo ""
fi

if ! test_http_connectivity "https://github.com" >/dev/null 2>&1; then
    echo -e "${RED}ISSUE: HTTPS connectivity is blocked${NC}"
    echo "Recommendation: Check for proxy or firewall blocking HTTPS"
    echo "  - Verify no proxy settings are interfering"
    echo "  - Check SELinux: sudo setenforce 0 (for testing only)"
    echo ""
fi

if test_dns_resolution "github.com" >/dev/null 2>&1 && \
   test_ping "8.8.8.8" >/dev/null 2>&1 && \
   test_http_connectivity "https://github.com" >/dev/null 2>&1; then
    echo -e "${GREEN}All basic connectivity tests passed!${NC}"
    echo "Network configuration appears to be working correctly."
fi

echo -e "\n${BLUE}For more help, see:${NC}"
echo "  - docs/TROUBLESHOOTING.md"
echo "  - https://docs.podman.io/en/latest/markdown/podman-run.1.html#network"
