@echo off
set "GHIDRA_INSTALL_DIR=c:\Users\acorr\Documents\tenis\tools\ghidra_12.1.4_PUBLIC"
set "JAVA_HOME=c:\Users\acorr\Documents\tenis\tools\jdk21"
set "PATH=%JAVA_HOME%\bin;c:\Users\acorr\Documents\tenis\tools\node24;%PATH%"
"c:\Users\acorr\Documents\tenis\tools\node24\node.exe" "c:\Users\acorr\Documents\tenis\tools\rea\node_modules\rea-agents\scripts\rea.mjs" %*
