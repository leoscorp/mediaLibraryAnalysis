@echo off
set "target_directory=%~1"
pushd "%target_directory%"

for /f %%i in ('dir *.mp4 *.mkv *.avi /s /b /a-d 2^>nul ^| find /c /v ""') do set file_count=%%i
set fcReturnValue=%file_count%

popd