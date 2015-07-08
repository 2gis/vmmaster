#ps1_sysnative

$JAVA_VERSION = "8u45"
$AGENT = "agent.exe"
$JAVA = "jre-$JAVA_VERSION-windows-x64.exe"
$SELENIUM_SERVER_STANDALONE = "selenium-server-standalone-2.46.0.jar"

$STORAGE = "http://storage.auto.ostack.test"
$JAVA_URL = "$STORAGE/windows/java/jre-$JAVA_VERSION-windows-x64.exe"
$SELENIUM_URL = "$STORAGE/$SELENIUM_SERVER_STANDALONE"
$AGENT_URL = "$STORAGE/windows/agent.exe"

Write-Output "User:"
[Environment]::UserName

Write-Output "------------------software--------------------"

cd C:\
$wc = New-Object System.Net.WebClient

# install oracle java
$wc.Downloadfile($JAVA_URL, "$JAVA")
Start-Process -FilePath "$JAVA" -passthru -wait -ArgumentList "/s INSTALLDIR=c:\java /L install64.log"

# download selenium-server
$wc.Downloadfile($SELENIUM_URL, "$SELENIUM_SERVER_STANDALONE")

# download vmmaster-agent
$wc.DownloadFile($AGENT_URL, "$AGENT")

Write-Output "--------------credential user-----------------"
$username = "test"
$password = ConvertTo-SecureString -String "123456" -AsPlainText -Force
$user = [ADSI]'WinNT://./test'
$user.SetPassword("123456")
$cred = New-Object System.Management.Automation.PSCredential $username,$password

Write-Output "-------------switch to desktop----------------"
(New-Object -ComObject shell.application).toggleDesktop()

Write-Output "---------------start software-----------------"
Start-Process $AGENT -Credential $cred
Start-Process java -ArgumentList "-jar $SELENIUM_SERVER_STANDALONE"  -Credential $cred
