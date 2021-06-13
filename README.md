## Prometheus-Apache-Log-Expoter

Scott Baker, https://www.smbaker.com/

This is a prometheus exporter for apache log files. This is a relatively simple approach -- I couldn't find something that did exactly what I wanted so I quickly hacked this up in python. I have taken a few steps to try to make it generally usable for others.

My use case is that I run a small personal web server that uses virtual hosts (vhosts) to serve multiple sites. I wanted something that would report in prometheus how much traffic each vhost was receiving.

This program runs continuously looking for a single log file (that's how my Ubuntu Apache2 installation was configured). If the log file is rotated by logrotate, it should automatically handle the change. As new entries are added to the log file, they will be counted in the following prometheus metrics:

* apache_web_request_count: a count of requests
* apache_web_request_sum: a sum of the bytes_out of all the requests
* apache_web_request_bytes_out_bucket: a histogram of request sizes

When first started, the program will not read existing entries from the log file (this would lead to a huge batch of prometheus reports). Instead, it will report new metrics as they occur.

## Configuration

There is a configuration file, apache-log-exporter.yaml that contains options that may be used to configure the exporter. Here is an example:

```yaml
input:
  filename: /var/log/apache2/other_vhosts_access.log
  format: VHOST_COMBINED
  ignoreExisting: true
output:
  port: 9100
resolver:
  127.0.0.1: localhost
  127.0.1.1: localhost
  1.2.3.4: myhome
```

Most of this should be self-explanatory. The `format` directive tells how to parse the log files, using a syntax for the `apachelogs` python library. In addition to `VHOST_COMBINED`, other formats include `COMBINED`, `COMBINED_DEBIAN`, `COMMON`, `COMMON_DEBIAN`, and `VHOST_COMMON`. I'll leave you to investigate the `apachelogs` library documentation to understand these formats. Instead of using one of these predefined constants, you ought to be able to define your own.

The `VHOST_COMBINED` format is the one I use, and seems to handle log lines that look like this:

```log
smbaker.com:443 1.2.3.4 - - [11/Jun/2021:22:06:39 -0700] "GET / HTTP/1.1" 200 35370 "-" "Go-http-client/1.1"
```

I would assume the `COMBINED` format is similar, but drops the `hostname:port` that's at the beginning of the line.

The `resolver` will resolve some client addresses for you. Resolving every client address would result in a massive expansion of prometheus metrics and is probably not advised. So I chose to make it so that you could manually choose to resolve some of them. The list is a simple IP:name format. Anything that doesn't matches will get the name `def`. What I usually do here is to add a resolver entry for my personal home address, so that my requests (I use prometheus-blackbox-exporter to check liveness of the server) aren't reflected in these statistic.

## Prerequisites

You'll need python 3.x. Hopefully your distro already came with it. If not, install a suitable version (`sudo apt install python3`) such as 3.8.5. You'll also need pip  (`apt install python3-pip`)

You'll need a couple python libraries

```bash
sudo pip3 install promteheus_client
sudo pip3 install apachelogs
```

## Installing

Here is more-or-less what I did:

```bash
# put the script in /opt/apache-log-exporter
sudo mkdir -p /opt/apache-log-exporter
sudo cp apache-log-exporter.py /opt/apache-log-exporter

# copy in the systemd file and the config file to the appropriate places
sudo cp apache-log-exporter.service /lib/systemd/system
sudo cp apache-log-exporter.yaml /etc/

# setup a user. The `adm` group may be necessary so it can read the log files.
sudo useradd --no-create-home --shell /bin/false apache-log-exporter
sudo usermod -aG adm apache-log-exporter 
sudo chgrp apache-log-exporter /etc/apache-log-exporter.yaml
sudo chown apache-log-exporter:apache-log-exporter /opt/apache-log-exporter/apache-log-exporter.py

# start it up
sudo systemctl start apache-log-exporter
sudo systemctl enable apache-log-exporter

# make sure it started cleanly
sudo systemctl status apache-log-exporter

# view the metrics (hit your server with a few requests first)
curl http://localhost:9101/metrics
```

## Useful grafana queries

```promql
# count of requests per minute by virtual host
sum by (virtual_host)(rate(apache_web_request_count{virtual_host=~"$vhost",final_status=~"$final_status",server_port=~"$server_port",remote_host=~"$remote_host"}[$__rate_interval]))*60

# sum of bytes per minute by virtual host
sum by (virtual_host)(rate(apache_web_request_sum{virtual_host=~"$vhost",final_status=~"$final_status",server_port=~"$server_port",remote_host=~"$remote_host"}[$__rate_interval]))*60

# count of requests per minute by http code
sum by (final_status)(rate(apache_web_request_count{virtual_host=~"$vhost",final_status=~"$final_status",server_port=~"$server_port",remote_host=~"$remote_host"}[$__rate_interval]))*60

# histogram of request sizes
# (In grafana, set the format to "heatmap" and the Value Options Calculation to "last")
sum by (le) (increase(apache_web_request_bytes_out_bucket{virtual_host=~"$vhost",remote_host=~"$remote_host"}[$__range]))

```

## Caveats

If you're looking here then I hope this script is useful to you, but ultimately I wrote it for my own use, and I can't guarantee it works for anyone other than me.



