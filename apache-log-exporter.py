#
# setup
#   # note: installed promtheus_clien=0.11.0, apachelogs=0.6.0, pydicti=1.1.4
#   sudo pip3 install promteheus_client
#   sudo pip3 install apachelogs

from prometheus_client import Histogram, Counter, Summary, start_http_server
import argparse
import os
import stat
import sys
import time
import yaml
from apachelogs import LogParser, COMBINED, COMBINED_DEBIAN, COMMON, COMMON_DEBIAN, VHOST_COMBINED, VHOST_COMMON


UNSPECIFIED = "def"


class InodeChangedError(Exception):
    pass


class FileShrunkError(Exception):
    pass


def GetInodeAndSize(fn):
    st = os.lstat(fn)
    return (st[stat.ST_INO], st[stat.ST_SIZE])


def follow(fn, ignoreExisting=False):
    """ Yield each line from a file as they are written.
        Return InodeChangedError if the Inode changed.
        Return FileShrunkError if the file shrunk
    """

    origInode, lastSize = GetInodeAndSize(fn)
    file = open(fn, 'r')
    line = ''
    while True:
        tmp = file.readline()
        if (tmp is not None) and (tmp != ""):
            line += tmp
            if line.endswith("\n"):
                if (not ignoreExisting):
                    yield line
                line = ''
        else:
            ignoreExisting = False
            time.sleep(1)
            newInode, newSize = GetInodeAndSize(fn)
            if (newInode != origInode):
                raise InodeChangedError("Inode changed")
            if (newSize < lastSize):
                raise FileShrunkError("File shrunk")
            lastSize = newSize


def warn(s):
    print(s, file=sys.stderr)


class ApacheLogExporter:
    def __init__(self, fn="sample.log", port=9101, resolver={}, format=VHOST_COMBINED, ignoreExisting=True, enableHistogram=True):
        self.fn = fn
        self.parser = LogParser(format)
        self.resolver = resolver
        self.ignoreExisting = ignoreExisting
        self.enableHistogram = enableHistogram

        # A summary is effectively a pair of counters, one incremented
        # for each observe, and one added to for each observe.
        self.webRequestSummary = Summary('apache_web_request', 
                                   'Requests processed by the web server',
                                   ['virtual_host', 'server_port', 'final_status', "remote_host"])

        if self.enableHistogram:
            # lots of buckets really increases the size of the scrape
            buckets=(4096,8192,16384,32768,65536,131072,262144,524288,1048576)
            self.webRequestBytesOutHistogram = Histogram('apache_web_request_bytes_out', 
                                   'Histogram of request bytes_out',
                                   ['virtual_host', 'remote_host'],
                                   buckets=buckets)

        start_http_server(port)

    def parse_line(self, line):
        entry = self.parser.parse(line)

        #print(entry.virtual_host, entry.server_port, entry.remote_host, entry.final_status, entry.bytes_out)
        #print(dir(entry))
        #sys.exit(-1)

        return entry

    def read_log_files(self):
        ignoreExisting = self.ignoreExisting
        while True:
            try:
                for line in follow(self.fn, ignoreExisting):
                    try:
                        entry = self.parse_line(line)
                    except Exception as e:
                        warn("Failed to parse line %s: %s" % (line, e))
                        continue
                    
                    if not entry:
                        continue

                    remote_host = self.resolver.get(entry.remote_host, UNSPECIFIED)

                    self.webRequestSummary.labels(
                        virtual_host=entry.virtual_host,
                        server_port=str(entry.server_port),
                        final_status = str(entry.final_status),
                        remote_host = remote_host).observe(entry.bytes_out)

                    if self.enableHistogram:
                        self.webRequestBytesOutHistogram.labels(
                            virtual_host=entry.virtual_host,
                            remote_host = remote_host).observe(entry.bytes_out)                        
            except (FileNotFoundError, InodeChangedError, FileShrunkError) as e:
                print("exception: %s", e)
                ignoreExisting = False
                time.sleep(1)        


def getParamDefault(yml, name, default):
    parts = name.split(".")
    for part in parts:
        if part not in yml:
            return default
        yml = yml[part]
    return yml


def parseBool(s):
    if (s==True) or (s==False):
        return s
    if (s.lower()=="true") or (s.lower()=="on") or (s.lower()=="yes"):
        return True
    if (s=="1"):
        return True
    return False


def get_settings():
    cmdParser = argparse.ArgumentParser()
    cmdParser.add_argument("--config_fn", "-f", type=str, default="/etc/apache-log-exporter.yaml", help="name of config file")
    args = cmdParser.parse_args(sys.argv[1:])

    defaults = {
        "input.filename": "apache-log-exporter.yaml",
        "input.format": VHOST_COMBINED,
        "input.ignoreExisting": "true",
        "output.port": 9100,
        "resolver": {"127.0.0.1": "localhost",
                     "127.0.1.1": "localhost"},
    }

    with open(args.config_fn, "r") as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)    

    settings = {
        "fn": getParamDefault(cfg, "input.filename", defaults["input.filename"]),
        "format": getParamDefault(cfg, "input.format", defaults["input.format"]),
        "ignoreExisting": parseBool(getParamDefault(cfg, "input.ignoreExisting", defaults["input.ignoreExisting"])),
        "port": int(getParamDefault(cfg, "output.port", defaults["output.port"])),
        "resolver": getParamDefault(cfg, "resolver", defaults["resolver"]),
    }

    formatMap = {
        "COMBINED": COMBINED,
        "COMBINED_DEBIAN": COMBINED_DEBIAN,
        "COMMON": COMMON,
        "COMMON_DEBIAN": COMMON_DEBIAN,
        "VHOST_COMBINED": VHOST_COMBINED,
        "VHOST_COMMON": VHOST_COMMON
    }

    settings["format"] = formatMap.get(settings["format"], settings["format"])

    return settings


def main():
    if len(sys.argv) == 2:
        config_fn = sys.argv[1]
    else:
        config_fn = "/etc/apache-log-exporter.yaml"

    settings = get_settings()
    print("settings: %s" % settings, file=sys.stderr)

    le = ApacheLogExporter(**settings)
    le.read_log_files()


if __name__ == "__main__":
    main()