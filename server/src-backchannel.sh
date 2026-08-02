#!/bin/bash
# Server — forwards backchannel audio to Pi's TCP listener (port 5555)
exec sshpass -p 'PASSWORD' ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
  andreas@192.168.178.11 socat - TCP:127.0.0.1:5555,connect-timeout=5 2>/dev/null
