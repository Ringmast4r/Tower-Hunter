#!/bin/bash
# TowerHunter Launcher
cd ~/Desktop/TowerHunter
echo "Starting TowerHunter..."
echo "Live Dashboard: http://localhost:8888"
echo "Remote Access:  http://10.0.0.15:8888"
echo ""
sudo python3 towerhunter.py "$@"
