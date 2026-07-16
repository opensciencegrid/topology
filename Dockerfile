FROM hub.osg-htc.org/osg-htc/software-base:25-el9-release

# Install dependencies (application, Apache)
RUN \
    yum update -y \
    && yum install -y \
      gcc \
      git \
      libyaml-devel \
      python3.12-devel \
      python3.12-pip \
    && yum install -y \
      fetch-crl \
      httpd \
      httpd-devel \
      mod_ssl \
      gridsite \
      /usr/bin/pkill \
      osg-ca-certs \
    && yum install -y --enablerepo=osg-internal \
      osg-internal-cas \
    && yum clean all && rm -rf /var/cache/yum/*

WORKDIR /app

# Needed for webhook:
RUN alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 10 && alternatives --set python3 /usr/bin/python3.12

# Install application dependencies
COPY requirements-apache.txt requirements-rootless.txt ./
RUN python3.12 -m pip install --no-cache-dir -r requirements-apache.txt

# Create data directory, and gather SSH keys for git
RUN mkdir                  /data && \
    chown -v apache:apache /data && \
    ssh-keyscan github.com bitbucket.org >> /etc/ssh/ssh_known_hosts && \
    git config --global --add safe.directory /data/app/topology && \
    git config --global --add safe.directory /data/app/contact

# Add fetch-crl cronjob
# Add daily restart of httpd to load renewed certificates
RUN echo "45 */6 * * * root /usr/sbin/fetch-crl -q -r 21600 -p 10" >  /etc/cron.d/fetch-crl && \
    echo "@reboot      root /usr/sbin/fetch-crl -q          -p 10" >> /etc/cron.d/fetch-crl && \
    echo "0 0 * * *    root /usr/bin/pkill -USR1 httpd"            >  /etc/cron.d/httpd

# Install application
COPY src/ ./

# Set up Apache configuration
# Remove default SSL config: default certs don't exist on EL8 so the
# default vhost (that we don't use) causes httpd startup failures
RUN rm /etc/httpd/conf.d/ssl.conf
COPY docker/apache.conf /etc/httpd/conf.d/topology.conf
COPY docker/supervisor-apache.conf /etc/supervisord.d/40-apache.conf
# Give the api keys file its own dir so it can be updated without a pod restart.
RUN mkdir -p /secrets/api_keys
COPY --chown=apache:apache --chmod=600 docker/api_keys.yaml /secrets/api_keys/api_keys.yaml

EXPOSE 8080/tcp 8443/tcp

ENV ENABLE_SHA1=YES
