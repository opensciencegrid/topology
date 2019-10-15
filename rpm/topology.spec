Summary: osg-notify tool
Name: osg-notify
Version: 1.0.0
Release: 1%{?dist}
Source: topology-%{version}.tar.gz
License: Apache 2.0
BuildArch: noarch
Url: https://github.com/opensciencegrid/topology/
Requires: python-gnupg
Requires: python-requests

%description
A simple tool for generating notification emails to the OSG

%prep
%setup -q -n topology-%{version}

%install
install -D -m 0755 bin/osg-notify %{buildroot}/%{_bindir}/osg-notify
install -D -m 0644 src/net_name_addr_utils.py  %{buildroot}/%{python_sitelib}/net_name_addr_utils.py
install -D -m 0644 src/topology_utils.py %{buildroot}/%{python_sitelib}/topology_utils.py

%files
%{_bindir}/osg-notify
%{python_sitelib}/net_name_addr_utils.py*
%{python_sitelib}/topology_utils.py*


%changelog
* Tue Oct 15 2019 Diego Davila <didavila@ucsd.edu> 1.0.0-1
- Initial
