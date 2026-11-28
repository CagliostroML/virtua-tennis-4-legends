@echo off
set "TOOLS_DIR=%~dp0"
set "GHIDRA_INSTALL_DIR=%TOOLS_DIR%ghidra_12.1.4_PUBLIC"
set "JAVA_HOME=%TOOLS_DIR%jdk21"
set "PATH=%JAVA_HOME%\bin;%TOOLS_DIR%node24;%PATH%"
"%TOOLS_DIR%node24\node.exe" "%TOOLS_DIR%rea\node_modules\rea-agents\scripts\rea.mjs" %*
