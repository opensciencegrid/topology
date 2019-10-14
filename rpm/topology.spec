Summary: osg-notify tool
Name: osg-notify
Version: 1.0.0
Release: 1%{?dist}
Source0: topology-%{version}.tar.gz
License: Apache 2.0
BuildArch: noarch
Url: https://github.com/opensciencegrid/topology/
Provides: osg-notify = %{version}-%{release}
Requires: python-gnupg
Requires: python-requests

%description
A simple tool for generating notification emails to the OSG

%prep
tar xzf %{SOURCE0}
cd topology-%{version}


%install
install -D -m 0755 topology-%{version}/bin/osg-notify %{buildroot}/%{_bindir}/osg-notify
install -D -m 0644 topology-%{version}/src/net_name_addr_utils.py  %{buildroot}/%{python_sitelib}/net_name_addr_utils.py
install -D -m 0644 topology-%{version}/src/topology_utils.py %{buildroot}/%{python_sitelib}/topology_utils.py

%files
%{_bindir}/osg-notify
%{python_sitelib}/net_name_addr_utils.py*
%{python_sitelib}/topology_utils.py*


%changelog

