#ps1_sysnative
$ErrorActionPreference = 'Stop'

$JAVA_VERSION = "8u45"
$AGENT = "agent.exe"
$JAVA = "jre-$JAVA_VERSION-windows-x64.exe"
$SELENIUM = "selenium-launchers-master"

$STORAGE = "http://storage.auto.ostack.test"
$JAVA_URL = "$STORAGE/windows/java/jre-$JAVA_VERSION-windows-x64.exe"
$SELENIUM_URL = "$STORAGE/$SELENIUM.zip"
$AGENT_URL = "$STORAGE/windows/agent.exe"

$DIRECTORY = "C:\\"
#$USERNAME = "test"

Write-Output "------------------software--------------------"
$wc = New-Object System.Net.WebClient

# install oracle java
$wc.Downloadfile($JAVA_URL, "$DIRECTORY\$JAVA")
Start-Process -FilePath "$DIRECTORY\$JAVA" -passthru -wait -ArgumentList "/s INSTALLDIR=c:\java /L install64.log"

# download selenium-server
$wc.Downloadfile("$STORAGE/windows/7za.exe", "$DIRECTORY\7za.exe")
$wc.Downloadfile($SELENIUM_URL, "$DIRECTORY\$SELENIUM.zip")
cmd /c $DIRECTORY\7za x $DIRECTORY\$SELENIUM.zip

# download vmmaster-agent
$wc.DownloadFile($AGENT_URL, "$DIRECTORY\$AGENT")

Write-Output "---------------configurations-----------------"
# disable firewall
netsh firewall set opmode disable
# disable UAC
C:\Windows\System32\cmd.exe /k %windir%\System32\reg.exe ADD HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System /v EnableLUA /t REG_DWORD /d 0 /f

# disable IE Protected Mode
REG ADD "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\1" /v "2500" /t REG_DWORD /d 3 /f
REG ADD "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\2" /v "2500" /t REG_DWORD /d 3 /f
REG ADD "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\3" /v "2500" /t REG_DWORD /d 3 /f
REG ADD "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings\Zones\4" /v "2500" /t REG_DWORD /d 3 /f

# disable IE Enchanced Security Configuration
REG ADD "HKLM\SOFTWARE\Microsoft\Active Setup\Installed Components\{A509B1A7-37EF-4b3f-8CFC-4F3A74704073}" /v "IsInstalled" /t REG_DWORD /d 0 /f
REG ADD "HKLM\SOFTWARE\Microsoft\Active Setup\Installed Components\{A509B1A8-37EF-4b3f-8CFC-4F3A74704073}" /v "IsInstalled" /t REG_DWORD /d 0 /f
REG ADD "HKEY_CURRENT_USER\Software\Microsoft\Internet Explorer\LowRegistry\DontShowMeThisDialogAgain" /v "DisplayTrustAlertDlg" /t REG_DWORD /d 0 /f

Write-Output "-------------switch to desktop----------------"
(New-Object -ComObject shell.application).toggleDesktop()

Write-Output "---------------start software-----------------"

$machine = [Environment]::MachineName
$user = "$machine\$USERNAME"

$agent_task = "agent"
$selenium_task = "selenium_server"
#$agent_action = New-ScheduledTaskAction "$DIRECTORY\$AGENT"
#Register-ScheduledTask -TaskName $agent_task -User $user -Action $agent_action
schtasks.exe /create /tn $agent_task /tr "$DIRECTORY\$AGENT" /sc ONLOGON
schtasks.exe /create /tn $selenium_task /tr "$DIRECTORY\$SELENIUM\start-win.bat" /sc ONLOGON

#$selenium_server_action = New-ScheduledTaskAction -Execute "java" -Argument "-jar $DIRECTORY\$SELENIUM_SERVER_STANDALONE -port 4445"
#Register-ScheduledTask -TaskName $selenium_server_task -User $user -Action $selenium_server_action
schtasks.exe /run /tn "$agent_task"
schtasks.exe /run /tn "$selenium_task"

#Start-ScheduledTask $agent_task
#Start-ScheduledTask $selenium_server_task
