#!/bin/bash

# Test script for conversation context functionality

API_BASE="http://localhost:8000/api"

echo "=== Test 1: Create a new conversation ==="
CONV_RESPONSE=$(curl -s -X POST "$API_BASE/conversations")
CONV_ID=$(echo "$CONV_RESPONSE" | jq -r '.conversation_id')
echo "Created conversation: $CONV_ID"
echo "Response: $CONV_RESPONSE" | jq .
echo ""

echo "=== Test 2: Send first message (Linux install question) ==="
curl -s -X POST "$API_BASE/chat/stream" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Share steps for linux install\", \"conversation_id\": \"$CONV_ID\"}" | head -20
echo ""
echo ""

echo "=== Test 3: Get conversation history after first message ==="
curl -s -X GET "$API_BASE/conversations/$CONV_ID" | jq .
echo ""

echo "=== Test 4: Send follow-up question with context ==="
curl -s -X POST "$API_BASE/chat/stream" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"what is the prerequisites for this?\", \"conversation_id\": \"$CONV_ID\"}" | head -30
echo ""

echo "=== Test 5: Get final conversation history ==="
curl -s -X GET "$API_BASE/conversations/$CONV_ID" | jq .
