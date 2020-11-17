Docker configuration
--------------------

1. Copy `config.example.py` to `config.py` for application config
2. Copy `config-webhook.example.py` to `config-webhook.py` for webhook config
3. Add secrets:
    - `secrets/bitbucket`
    - `secrets/cilogon-ldap`
    - `secrets/github_access_token`
    - `secrets/github_webhook_secret`
4. Create self-signed certificate (for local testing)
    - `secrets/certs/tls.key`
    - `secrets/certs/tls.crt`
    - Ex. `openssl req -x509 -newkey rsa:4096 -keyout tls.key -out tls.crt -days 365 -nodes`
5. Start application with `docker-compose up`
