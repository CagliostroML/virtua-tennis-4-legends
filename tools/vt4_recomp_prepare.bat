@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "GAME_DIR="
set "OUT_DIR=%~dp0"
if "%OUT_DIR:~-1%"=="\" set "OUT_DIR=%OUT_DIR:~0,-1%"

:parse_args
if "%~1"=="" goto args_done
set "ARG=%~1"
if /I "!ARG!"=="--game" (
    set "GAME_DIR=%~2"
    shift
    shift
    goto parse_args
)
if /I "!ARG!"=="--out" (
    set "OUT_DIR=%~2"
    shift
    shift
    goto parse_args
)
if /I "!ARG:~0,7!"=="--game=" (
    set "GAME_DIR=!ARG:~7!"
    shift
    goto parse_args
)
if /I "!ARG:~0,6!"=="--out=" (
    set "OUT_DIR=!ARG:~6!"
    shift
    goto parse_args
)
shift
goto parse_args

:args_done
if "%OUT_DIR:~-1%"=="\" set "OUT_DIR=%OUT_DIR:~0,-1%"

if not defined GAME_DIR (
    if exist "%OUT_DIR%\VT4.exe" if exist "%OUT_DIR%\resource.bin" if exist "%OUT_DIR%\resource.1.bin" (
        if not exist "%OUT_DIR%\save" mkdir "%OUT_DIR%\save" >nul 2>&1
        > "%OUT_DIR%\.vt4_prepared" echo prepared=1
        echo progress 1.00 Already prepared
        exit /b 0
    )
    echo Your Virtua Tennis 4 PC folder was not provided. Pick your copy containing VT4.exe and resource.bin.
    exit /b 1
)

if "%GAME_DIR:~-1%"=="\" set "GAME_DIR=%GAME_DIR:~0,-1%"

if not exist "%GAME_DIR%\VT4.exe" (
    echo Missing VT4.exe in "%GAME_DIR%". Pick your unpacked Virtua Tennis 4 PC folder.
    exit /b 1
)
if not exist "%GAME_DIR%\vt4.dll" (
    echo Missing vt4.dll in "%GAME_DIR%". Pick your complete Virtua Tennis 4 PC folder.
    exit /b 1
)
if not exist "%GAME_DIR%\resource.bin" (
    echo Missing resource.bin in "%GAME_DIR%". Pick your complete Virtua Tennis 4 PC folder.
    exit /b 1
)
if not exist "%GAME_DIR%\resource.1.bin" (
    echo Missing resource.1.bin in "%GAME_DIR%". Pick your complete Virtua Tennis 4 PC folder.
    exit /b 1
)

if exist "%OUT_DIR%\.vt4_prepared" del /f /q "%OUT_DIR%\.vt4_prepared" >nul 2>&1

if /I "%GAME_DIR%"=="%OUT_DIR%" (
    if not exist "%OUT_DIR%\save" mkdir "%OUT_DIR%\save" >nul 2>&1
    > "%OUT_DIR%\.vt4_prepared" echo prepared=1
    echo progress 1.00 Virtua Tennis 4 files verified
    exit /b 0
)

echo progress 0.10 Copying VT4.exe and engine libraries
for %%F in (VT4.exe VT4.exe.cat VT4.exe.cfg vt4.dll msvcr90.dll msvcp90.dll msvcm90.dll XAudio2_7.dll) do (
    if exist "%GAME_DIR%\%%F" (
        copy /Y "%GAME_DIR%\%%F" "%OUT_DIR%\%%F" >nul
        if errorlevel 1 (
            echo Failed copying %%F into "%OUT_DIR%".
            exit /b 1
        )
    )
)

echo progress 0.45 Copying resource.bin
copy /Y "%GAME_DIR%\resource.bin" "%OUT_DIR%\resource.bin" >nul
if errorlevel 1 (
    echo Failed copying resource.bin into "%OUT_DIR%" - check disk space.
    exit /b 1
)

echo progress 0.85 Copying resource.1.bin
copy /Y "%GAME_DIR%\resource.1.bin" "%OUT_DIR%\resource.1.bin" >nul
if errorlevel 1 (
    echo Failed copying resource.1.bin into "%OUT_DIR%" - check disk space.
    exit /b 1
)

if not exist "%OUT_DIR%\save" mkdir "%OUT_DIR%\save" >nul 2>&1
> "%OUT_DIR%\.vt4_prepared" echo prepared=1
echo progress 1.00 Virtua Tennis 4 retail files ready
exit /b 0
