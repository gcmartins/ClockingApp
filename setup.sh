#!/bin/bash

# Create virtual environment
python3 -m venv env

# Activate virtual environment
source env/bin/activate

# Install necessary packages
pip install -r requirements.txt

echo [Desktop Entry] > Clocking.desktop
echo Type=Application >> Clocking.desktop
echo Name=Clocking >> Clocking.desktop
echo Path=$(pwd) >> Clocking.desktop
echo Exec=$(pwd)/env/bin/python $(pwd)/app.py >> Clocking.desktop
echo Terminal=false >> Clocking.desktop
echo Icon=$(pwd)/clock.png >> Clocking.desktop

chmod +x Clocking.desktop