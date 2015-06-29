# Nginx Ansible Role

[Nginx](http://nginx.org/) is an HTTP and reverse proxy server.

This playbook install the nginx package.

Устаналивает выбранную версию nginx (по умолчанию пакет nginx без указания конкретной версии).
Если установка содержит модуль lua, создает соответствующую директорию /etc/nginx/lua и прописывает пути для поиска сриптов.

## Dependencies

No.

## Usage

```
# playbook.yml

- hosts: all
  roles:
    - { role: nginx,
      sudo: yes,
      tags: [nginx] }
```

## Variables

For simple generating sites configuration you may use `nginx_sites` variable:
```
# vars/main.yml
nginx_sites: # List of sites configs, each config is object.
  - {
    name: example.org, # Property `name` used for creating file.
    listen: 80, # All properties excepting `name` and `locations` will be added
    server_name: example.org, # to server directive in `key value;` format.
    locations: [ # Array of locations configs, each location is object.
      {
        name: '/', # Property `name` used in location directive.
        proxy_pass: 'http://127.0.0.1:3000', # All properties excepting `name`
        # will be added to current location directive in `key value;` format.
        # If you need set some params with equal names (proxy_set_header for example)
        # you should use array of strings as value instead of string. See below.
        proxy_set_header: ['Host $host', 'X-Real-IP $remote_addr']
      },
      {
        name: '/api',
        proxy_pass: 'http://127.0.0.1:8080',
        # If you use `if` as property it will not be added semicolon at the end of line.
        if: '($request_method !~ ^(GET)$ ) { return 444; }'
      }
    ]
  }

# Will be generate /etc/nginx/sites-available/example.org and also enable it.
server {
  listen 80;
  server_name example.org;

  location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }

  location /api {
    proxy_pass http://127.0.0.1:8080;
    if ($request_method !~ ^(GET)$ ) { return 444; }
  }
}
```
* **nginx_delete_defaul_vhost**: Delete or not default vhost
    * Type: Boolean
    * Default: false
* **nginx_user**:
    * Type: String
    * Default: www-data
* **nginx_worker_processes**:
    * Type: Integer
    * Default: $ansible_processor_count
* **nginx_pid**:
    * Type: String
    * Default: /var/run/nginx.pid
* **nginx_worker_connections**:
    * Type: Integer
    * Default: 768

See other variables in file [defaults/main.yml](defaults/main.yml).

## TODO
 - Проверять конфликты официального nginx и dev-steroidz
 - Переписать контроль restart и reload nginx'a, сейчас он рапортует что всё хорошо на ложные конфиги
 - Написать сниппеты использования