#!/bin/bash

# Install dependencies and create virtual environment
uv sync

echo [Desktop Entry] > Clocking.desktop
echo Type=Application >> Clocking.desktop
echo Name=Clocking >> Clocking.desktop
echo Path=$(pwd) >> Clocking.desktop
echo Exec=$(pwd)/.venv/bin/python $(pwd)/app.py >> Clocking.desktop
echo Terminal=false >> Clocking.desktop
echo Icon=$(pwd)/clock.png >> Clocking.desktop

chmod +x Clocking.desktop