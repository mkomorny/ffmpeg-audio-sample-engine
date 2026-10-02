@echo off
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw audio_sample_tool.py & exit /b)
where pythonw >nul 2>nul && (start "" pythonw audio_sample_tool.py & exit /b)
where py >nul 2>nul && (start "" py audio_sample_tool.py & exit /b)
where python >nul 2>nul && (start "" python audio_sample_tool.py & exit /b)
echo Could not find a Python interpreter (pyw/pythonw/py/python) on PATH.
pause
