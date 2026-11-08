Get-WinEvent -FilterHashtable @{LogName='Application'; ProviderName='Application Error'} -MaxEvents 10 | ForEach-Object {
    if ($_.Message -match 'VT4') {
        $msg = ($_.Message -split [Environment]::NewLine | Where-Object { $_ -match 'Desplazamiento|módulo' }) -join ' | '
        Write-Host "$($_.TimeCreated.ToString('HH:mm:ss')) : $msg"
    }
}
