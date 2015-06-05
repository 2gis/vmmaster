Ansible используем из репозитория https://launchpad.net/~rquillo/+archive/ansible

Добавляем репозиторий, обновляем пакеты, ставим ansible

`sudo add-apt-repository -y ppa:rquillo/ansible`

`sudo apt-get update`

`sudo apt-get install ansible`

Для работы ansible, на машине куда разворачивают должен быть пользователь ansible с sudo правами
По умолчанию ansible будет деплоить на localhost, изменить/добавить хосты для деплоя можно в hosts/servers

Установка "с нуля"
------------------
Пример деплоя с нуля на localhost c настройками по умолчанию:

```
ansible-playbook -i hosts/servers deploy.yml
```

Пример деплоя с нуля на localhost c установкой postgresql:
```
ansible-playbook -i hosts/servers deploy.yml --extra-vars "use_postgres=true"
```

Если ваш пользователь на удаленной машине не ansible:
```
ansible-playbook -i hosts/servers deploy.yml --extra-vars "deploy_user=username"
```

Пример деплоя с установкой nginx и добавлением конфигов:
```
# может потребоваться переопределить переменные nginx_sites и nginx_upstreams
ansible-playbook -i hosts/servers deploy.yml --extra-vars "nginx=true"
```

Если нужно только установить nginx и настроить его:
```
# может потребоваться переопределить переменные nginx_sites и nginx_upstreams
ansible-playbook -i hosts/servers deploy.yml --extra-vars "only_nginx=true"
```


Обновление существующего vmmaster
---------------------------------
Пример обновления установленного vmmaster со свежей master ветки репозитория :
```
ansible-playbook -i hosts/servers deploy.yml --extra-vars "update=true"
```

Пример обновления установленного vmmaster со свежей master ветки репозитория и работой с postgres :
```
ansible-playbook -i hosts/servers deploy.yml --extra-vars "use_postgres=true update=true"
```

Пример обновления установленного vmmaster с указаной ветки репозитория:
```
ansible-playbook -i hosts/servers deploy.yml --extra-vars "update=true vmmaster_version=<branch_name>"
```

Пример отката установленного vmmaster с указаного коммита репозитория:
```
ansible-playbook -i hosts/servers deploy.yml --extra-vars "update=true vmmaster_version=95a7b6f810b101801a90efd9c2cdd94cfd171e56"
```

Если выполняется из под другого пользователя, например, jenkins, то используй ключ -k:
```
ansible-playbook -i hosts/servers deploy.yml -k
```

Переопределение переменных ([подробнее в доках ансибла](http://www.ansibleworks.com/docs/playbooks_variables.html#passing-variables-on-the-command-line)): 
```
ansible-playbook -i hosts/servers deploy.yml --extra-vars "postgres_user=test_user postgres_host=192.168.0.1"
```

Выполнение консольной команды на всех тачках:
```
ansible all -i hosts/servers -u ansible -m shell -a "echo hello"
```

Настройка конфига base_dir/config.py
---------------------------------------
Параметры config.py, т.е всё его содержимое можено переопределить следующим способом:
* в host_vars добавляем файл с server_name, например, test.local c таким содержимым:
```
vmmaster_config_name: <server_name>
```
* добавляем в install_vmmaster файл с названием server_name со своей версией конфига, например, скопировав базовый конфиг из install_vmmaster/all


