#!/bin/bash
cd /home/kali/Desktop/TowerHunter
(sleep 4 && firefox http://localhost:8888) &
python3 -u towerhunter-remote.py
