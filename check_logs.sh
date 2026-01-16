#!/bin/bash
# Diagnostic script to check GATE_ERROR logs

TRACE_ID="${1:-spb6jwp}"
CONTAINER="${2:-eatfit24-ai-proxy}"

echo "==================================="
echo "Searching for trace_id: $TRACE_ID"
echo "==================================="

# Find the exact error
echo -e "\n1. Error entry:"
docker logs "$CONTAINER" 2>&1 | grep -A 5 -B 5 "$TRACE_ID" | head -30

echo -e "\n==================================="
echo "2. Gate-related errors (last 15 min):"
echo "==================================="
docker logs "$CONTAINER" --since 15m 2>&1 | grep -i "gate.*error\|gate.*warning\|raw_preview" | tail -20

echo -e "\n==================================="
echo "3. Recent GATE_ERROR occurrences:"
echo "==================================="
docker logs "$CONTAINER" --since 30m 2>&1 | grep "GATE_ERROR" | wc -l
echo "occurrences in last 30 minutes"

echo -e "\n==================================="
echo "4. Sample of recent gate responses:"
echo "==================================="
docker logs "$CONTAINER" --since 30m 2>&1 | grep "Gate result" | tail -10
