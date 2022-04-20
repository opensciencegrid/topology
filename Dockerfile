FROM opensciencegrid/software-base:3.6-el8-release

# Install dependencies (application, Apache)
RUN \
    yum update -y \
    && yum install -y \
      gcc \
      git \
      libyaml-devel \
      python3-devel \
      python3-pip \
    && yum install -y \
      fetch-crl \
      httpd \
      httpd-devel \
      mod_ssl \
      gridsite \
      osg-ca-certs \
      /usr/bin/pkill \
    && yum clean all && rm -rf /var/cache/yum/*

WORKDIR /app

# Install application dependencies
COPY requirements-apache.txt src/ ./
RUN pip3 install --no-cache-dir -r requirements-apache.txt

# Create data directory, and gather SSH keys for git
RUN mkdir                  /data && \
    chown -v apache:apache /data && \
    ssh-keyscan github.com bitbucket.org >> /etc/ssh/ssh_known_hosts

# Add fetch-crl cronjob
# Add daily restart of httpd to load renewed certificates
RUN echo "45 */6 * * * root /usr/sbin/fetch-crl -q -r 21600 -p 10" >  /etc/cron.d/fetch-crl && \
    echo "@reboot      root /usr/sbin/fetch-crl -q          -p 10" >> /etc/cron.d/fetch-crl && \
    echo "0 0 * * *    root /usr/bin/pkill -USR1 httpd"            >  /etc/cron.d/httpd


# Set up Apache configuration
# Remove default SSL config: default certs don't exist on EL8 so the
# default vhost (that we don't use) causes httpd startup failures
RUN rm /etc/httpd/conf.d/ssl.conf
COPY docker/apache.conf /etc/httpd/conf.d/topology.conf
COPY docker/supervisor-apache.conf /etc/supervisord.d/40-apache.conf

EXPOSE 8080/tcp 8443/tcp
