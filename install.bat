@echo off
echo ================================
echo    Posture App Installing...
echo ================================

echo Installing libraries...
py -m pip install mediapipe==0.10.5
py -m pip install opencv-python
py -m pip install plyer

echo Copying files...
mkdir "%USERPROFILE%\PostureApp"
copy posture.py "%USERPROFILE%\PostureApp"

echo Creating shortcut...
powershell -Command "$desktop=[Environment]::GetFolderPath('Desktop');$s=(New-Object -COM WScript.Shell).CreateShortcut($desktop+'\PostureApp.lnk');$s.TargetPath='py';$s.Arguments='%USERPROFILE%\PostureApp\posture.py';$s.Save()"

echo ================================
echo    Install Complete!
echo    Click PostureApp on Desktop!
echo ================================
pause