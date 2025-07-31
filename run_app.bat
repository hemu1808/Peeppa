@echo off
set PATH=%PATH%;%USERPROFILE%\scoop\apps\mongodb\current\bin
call venv\Scripts\activate
set FLASK_APP=app.py
set FLASK_ENV=development
if not exist "data\db" mkdir data\db
start "" mongod --dbpath data/db
timeout /t 2
python -m flask run