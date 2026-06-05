#!/bin/bash
set -e

# Configuration
AGENT_A_URL="http://localhost:8001"
AGENT_B_URL="http://localhost:8002"
SERVER_URL="http://localhost:8080"

echo "=== Checking Connectivity ==="
curl -s $SERVER_URL/health | grep -q "ok" && echo "Server: OK" || (echo "Server: Offline"; exit 1)
curl -s $AGENT_A_URL/health | grep -q "ok" && echo "Agent A: OK" || (echo "Agent A: Offline"; exit 1)
curl -s $AGENT_B_URL/health | grep -q "ok" && echo "Agent B: OK" || (echo "Agent B: Offline"; exit 1)

echo -e "\n=== Uploading test file to Agent A ==="
echo "Hello RockDove Integration Test" > test_file.txt
UPLOAD_RES=$(curl -s -F "file=@test_file.txt" $AGENT_A_URL/files/)
FILE_ID=$(echo $UPLOAD_RES | grep -oP '(?<="file_id":")[^"]+')
echo "File ID: $FILE_ID"

echo -e "\n=== Triggering transfer from Agent A to Agent B ==="
# Agent A will contact Agent B at http://agent-b:8000/transfer/receive
# and send UDP packets to agent-b:9001 (internal Docker network)
SEND_RES=$(curl -s -X POST $AGENT_A_URL/transfer/send \
  -H "Content-Type: application/json" \
  -d "{
    \"file_id\": \"$FILE_ID\",
    \"target_peer_id\": \"agent-b\"
  }")
TRANSFER_ID=$(echo $SEND_RES | grep -oP '(?<="transfer_id":")[^"]+')
echo "Transfer ID: $TRANSFER_ID"

echo -e "\n=== Waiting for transfer to complete ==="
for i in {1..20}; do
  STATUS_RES=$(curl -s $AGENT_B_URL/transfer/$TRANSFER_ID/status)
  STATUS=$(echo $STATUS_RES | grep -oP '(?<="status":")[^"]+')
  echo "Current status on Agent B: $STATUS"
  if [[ "$STATUS" == "ok" || "$STATUS" == "degraded" ]]; then
    echo "Transfer successful!"
    break
  fi
  if [[ "$STATUS" == "failed" ]]; then
    echo "Transfer failed!"
    echo $STATUS_RES
    exit 1
  fi
  sleep 1
done

echo -e "\n=== Verifying file on Agent B ==="
FILE_LIST=$(curl -s $AGENT_B_URL/files/)
if echo $FILE_LIST | grep -q "test_file.txt"; then
  echo "File 'test_file.txt' found in Agent B storage!"
else
  echo "File NOT found in Agent B storage."
  echo $FILE_LIST
fi

rm test_file.txt
echo -e "\n=== Integration Test Finished ==="
