@echo off
cd /d "%~dp0"

echo Creating a virtual environment...
python -m venv Venv

echo Virtual Environment Activation...
call Venv/Scripts/activate.bat

echo Requirements Setup...
pip install -r requirements.txt

del "README.MD"
del "requirements.txt"
del "Setup.bat"
