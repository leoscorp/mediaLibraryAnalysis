@echo off
mode con cols=200 lines=50
:: echo "id","filePath","fileExt","videoCodecName","audioCodecName","frameWidth","frameHeight","durationSeconds","formattedDuration","fileSize","kbps" 

echo [ > "fileList.json"

set subString="%~1"
if "%~1"==""  set subString="\Home Videos,\Christmas"
if "%~1"=="0" set subString=""

set subString=%subString:&=$%
set subString=%subString: \=\%

setlocal EnableExtensions EnableDelayedExpansion

:: Define carriage return and backspace characters
for /f %%a in ('copy /Z "%~dpf0" nul') do set "CR=%%a"
for /f %%a in ('"prompt $H&for %%b in (0) do rem"') do set "BS=%%a" <nul

set "loop_count=0"
echo excluding: %subString:$=&%
echo.

set "td=H:\HTPC\embyServer\libraries\Public Libraries\"
call fileCount.bat "%td%"
set /a treeFileCount=%fcReturnValue%

for /D /R "%td%" %%d IN (*) DO (

    set "mainString=%%d"
    set "mainString=!mainString:&=$!"
    
    if !subString! NEQ "" (
        set subString=!subString:"=!
        :: Replace the substring with nothing in a copy of the main string
        for /f "delims=, tokens=1*" %%A in ("!subString!") do (
            set "tempString=!mainString:%%A=!"
        )
        for /f "delims=, tokens=2*" %%B in ("!subString!") do (
            set "tempString=!tempString:%%B=!"
        )
    ) else (
        set tempString=!mainString!
    )
    if "!mainString!" NEQ "!tempString!" (
        if !loop_count!==0 (
            echo Skipped: %%d
        )
    ) else (
        set "strTotalCount=    (!loop_count!)"
        set "this_loop_count=0"
        set /a "strPct=!loop_count! * 100 / !treeFileCount!
        <nul set /p "=Scanning for files !strTotalCount:~-7!:            !strPct!%%: !mainString!                            !CR!"
        
        type nul > fileListTmp.json
        for %%F IN ("%%d\*.mkv" "%%d\*.avi" "%%d\*.mpeg" "%%d\*.mp4" "%%d\*.mov" "%%d\*.wmv" "%%d\*.flv" "%%d\*.webm") DO (
            call :isTrailer "%%F"
            if %errorlevel%==0 (
                set /A this_loop_count=!this_loop_count! + 1
                set /A loop_count=!loop_count! + 1
                setlocal DisableDelayedExpansion
                    set "inputFile=%%F"
                    set "fileSize=%%~zF"
                    set "fileName_noExt=%%~nF"
                    set "fileExt=%%~xF"
                    set "originalFileBackup="
                    set "originalFileSize="
                    pushd H:\HTPC\libraryAnalyzer\originalStreams
                    for /F "delims=" %%e in ('DIR "%%~nF".* /A-D /S /B 2^>nul') DO (
                        set originalFileBackup=%%e
                        set originalFileSize=%%~ze
                    )
                    popd
                setlocal EnableExtensions EnableDelayedExpansion
                
                set fileExt=!fileExt:.=!
    
                if defined originalFileBackup (
                    set "originalFileBackup=!originalFileBackup:\=\\!"
                )
                for /F "delims=" %%a in ('H:\ffmpeg\ffprobe -v error -show_streams -show_entries ^
                        format^=duration:stream^=codec_type^,codec_name^,width^,height ^
                        -of json^=c^=1 "!inputFile!"') DO (
                    set "ffprobeReturnString=!ffprobeReturnString!%%a"
                )
    
                set "ffprobeReturnString=!ffprobeReturnString:"=""!"
                for /F "delims=" %%C in ('python.exe parse_json_columns.py "!ffprobeReturnString!" !fileSize!') DO (
                    set "formattedReturnString=%%C"
                )
                
                if "!loop_count!"=="1" (
                    echo  {"id": !loop_count!, "filePath": "!inputFile:\=\\!", "fileExt": "!fileExt!", !formattedReturnString!, "originalFileBackup": "!originalFileBackup!", "originalFileSize": "!originalFileSize!"} >> "fileListTmp.json"
                ) else (
                    echo ,{"id": !loop_count!, "filePath": "!inputFile:\=\\!", "fileExt": "!fileExt!", !formattedReturnString!, "originalFileBackup": "!originalFileBackup!", "originalFileSize": "!originalFileSize!"} >> "fileListTmp.json"
                )
        
                set "strLoopCount=  !this_loop_count!"
                set "strTotalCount=    (!loop_count!)"
                set /a "strPct=!loop_count! * 100 / !treeFileCount!
    
                <nul set /p "=Scanning for files !strTotalCount:~-7!: !strLoopCount:~-3! found  !strPct!%%: !mainString!                            !CR!"
        
                endlocal
                endlocal
            )
        )
        type fileListTmp.json >> fileList.json
    )
)

endlocal

echo ] >> "fileList.json"

pause 

call python json_to_csv.py
exit /b

:isTrailer
    set str1=%1
    if not x%str1:-trailer.=%==x%str1% (
        exit /b 1
    ) else (
        exit /b 0
    ) 

:fixEquals
    set fixedString=
    set myString=%~1
    set "stringLength=0"
    set "iterString=!myString!"
    
    :: Get the length of the string
:getLength
if defined iterString (
    set /a stringLength+=1
    set "iterString=!iterString:~1!"
    goto getLength
)

:: Loop through each character
for /L %%i in (0,1,%stringLength% - 1) do (
    set "currentChar=!myString:~%%i,1!"
    if "!currentChar!"=="%~2" set currentChar=%~3
    set fixedString=!fixedString!!currentChar!
)
    set "%4=!fixedString!"

exit /b