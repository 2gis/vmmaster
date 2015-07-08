#!/bin/bash

SELENIUM_SERVER_STANDALONE=selenium-server-standalone-2.46.0.jar

echo "-------------------------------------user-----------------------------------------"
VAGRANT_USER=vagrant
VAGRANT_HOME=/home/$VAGRANT_USER
VAGRANT_KEY_URL=https://raw.githubusercontent.com/mitchellh/vagrant/master/keys/vagrant.pub

# create Vagrant user (if not already present)
if ! id -u $VAGRANT_USER >/dev/null 2>&1; then
    /usr/sbin/groupadd $VAGRANT_USER
    /usr/sbin/useradd $VAGRANT_USER -g $VAGRANT_USER -G sudo -d $VAGRANT_HOME --create-home
    echo "${VAGRANT_USER}:${VAGRANT_USER}" | chpasswd
fi

# Set up passwordless sudo
echo "${VAGRANT_USER}        ALL=(ALL)       NOPASSWD: ALL" >> /etc/sudoers

echo "-----------------------------------settings---------------------------------------"
# open all ports
iptables -F
iptables -P INPUT ACCEPT

echo "-----------------------------------software---------------------------------------"
# install oracle java
cd $VAGRANT_HOME
wget http://storage.auto.ostack.test/linux/java/jre-8u45-linux-x64.tar.gz 2>/dev/null
mkdir java
tar xf jre-8u45-linux-x64.tar.gz -C java
JAVA=$VAGRANT_HOME/`find java -name "java" -type f`

# download selenium-server
cd $VAGRANT_HOME
wget http://storage.auto.ostack.test/$SELENIUM_SERVER_STANDALONE 2>/dev/null

# install vmmaster-agent
cd $VAGRANT_HOME
wget http://storage.auto.ostack.test/linux/agent 2>/dev/null
VMMASTER_AGENT=$VAGRANT_HOME/agent
chmod +x $VMMASTER_AGENT

echo "-----------------------------------autostart--------------------------------------"
mkdir $VAGRANT_HOME/.config
mkdir $VAGRANT_HOME/.config/autostart

cat > $VAGRANT_HOME/.config/autostart/selenium-launchers.desktop << EOF
[Desktop Entry]
Type=Application
Name=selenium-launchers
Exec=xterm -e '$JAVA -jar ${VAGRANT_HOME}/${SELENIUM_SERVER_STANDALONE}'
X-GNOME-Autostart-enabled=true
EOF
cat > $VAGRANT_HOME/.config/autostart/vmmaster_agent.desktop << EOF
[Desktop Entry]
Type=Application
Name=vmmaster_agent
Exec=xterm -e 'sudo $VMMASTER_AGENT'
X-GNOME-Autostart-enabled=true
EOF

chown -R vagrant:vagrant $VAGRANT_HOME/.config

echo "-----------------------------------autologin--------------------------------------"
sudo mkdir /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-autologin.conf << EOF
[SeatDefaults]
autologin-user=${VAGRANT_USER}
EOF
sudo service lightdm restart
