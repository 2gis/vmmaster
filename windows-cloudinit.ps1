#ps1_sysnative
$ErrorActionPreference = 'Stop'

$JAVA_VERSION = "8u45"
$AGENT = "agent.exe"
$JAVA = "jre-$JAVA_VERSION-windows-x64.exe"
$SELENIUM_SERVER_STANDALONE = "selenium-server-standalone-2.46.0.jar"

$STORAGE = "http://storage.auto.ostack.test"
$JAVA_URL = "$STORAGE/windows/java/jre-$JAVA_VERSION-windows-x64.exe"
$SELENIUM_URL = "$STORAGE/$SELENIUM_SERVER_STANDALONE"
$AGENT_URL = "$STORAGE/windows/agent.exe"

$DIRECTORY = "C:\\"
$USERNAME = "test"

Write-Output "------------------software--------------------"
$wc = New-Object System.Net.WebClient

# install oracle java
$wc.Downloadfile($JAVA_URL, "$DIRECTORY\$JAVA")
Start-Process -FilePath "$DIRECTORY\$JAVA" -passthru -wait -ArgumentList "/s INSTALLDIR=c:\java /L install64.log"

# download selenium-server
$wc.Downloadfile($SELENIUM_URL, "$DIRECTORY\$SELENIUM_SERVER_STANDALONE")

# download vmmaster-agent
$wc.DownloadFile($AGENT_URL, "$DIRECTORY\$AGENT")

Write-Output "-------------switch to desktop----------------"
(New-Object -ComObject shell.application).toggleDesktop()

Write-Output "---------------start software-----------------"

$machine = [Environment]::MachineName
$user = "$machine\$USERNAME"

$agent_action = New-ScheduledTaskAction "$DIRECTORY\$AGENT"
$agent_task = "agent"
Register-ScheduledTask -TaskName $agent_task -User $user -Action $agent_action

$selenium_server_action = New-ScheduledTaskAction -Execute "java" -Argument "-jar $DIRECTORY\$SELENIUM_SERVER_STANDALONE -port 4445"
$selenium_server_task = "selenium_server"
Register-ScheduledTask -TaskName $selenium_server_task -User $user -Action $selenium_server_action

Start-ScheduledTask $agent_task
Start-ScheduledTask $selenium_server_task
