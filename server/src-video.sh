#!/bin/bash
# Server — launches rpicam raw H264 pipe on the Pi via SSH
exec sshpass -p 'PASSWORD' ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
  andreas@192.168.178.11 /opt/rpicam-stream.sh 2>/dev/null
