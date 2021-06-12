from prometheus_client import Counter, Summary, start_http_server
import os
import stat
import sys
import time
from apachelogs import LogParser, COMBINED


class InodeChangedError(Exception):
    pass


class FileShrunkError(Exception):
    pass


def GetInodeAndSize(fn):
    st = os.lstat(fn)
    return (st[stat.ST_INO], st[stat.ST_SIZE])


def follow(fn):
    """ Yield each line from a file as they are written.
        Return InodeChangedError if the Inode changed.
        Return FileShrunkError if the file shrunk
    """

    origInode, lastSize = GetInodeAndSize(fn)
    file = open("sample.log", 'r')
    line = ''
    while True:
        tmp = file.readline()
        if (tmp is not None) and (tmp != ""):
            line += tmp
            if line.endswith("\n"):
                yield line
                line = ''
        else:
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
    def __init__(self, fn = "sample.log", port=9101):
        self.fn = fn
        self.parser = LogParser(COMBINED)

        self.webRequestCount = Counter('apache_web_request_count', 
                                   'Requests processed by the web server',
                                   ['remote_host_name', 'remote_host_port', 'final_status'])

        self.webRequestSent = Counter('apache_web_request_sent', 
                                   'Size of Requests processed by the web server',
                                   ['remote_host_name', 'remote_host_port', 'final_status'])                                   

        start_http_server(port)

    def parse_line(self, line):
        entry = self.parser.parse(line)

        if not entry.remote_host:
            warn("no remote_host in line: %s" % line)
            return None

        if ":" not in entry.remote_host:
            warn("no colon in remote_host in line: %s" % line)
            return None

        entry.remote_host_name, entry.remote_host_port = entry.remote_host.split(":",1)
        entry.remote_host_port = int(entry.remote_host_port)
        return entry

    def read_log_files(self):
        while True:
            try:
                for line in follow("sample.log"):
                    try:
                        entry = self.parse_line(line)
                    except Exception as e:
                        warn("Failed to parse line %s: %s" % (line, e))
                        continue
                    
                    if not entry:
                        continue

                    self.webRequestCount.labels(
                        remote_host_name=entry.remote_host_name,
                        remote_host_port=str(entry.remote_host_port),
                        final_status = str(entry.final_status)).inc()

                    self.webRequestSent.labels(
                        remote_host_name=entry.remote_host_name,
                        remote_host_port=str(entry.remote_host_port),
                        final_status = str(entry.final_status)).inc(entry.bytes_sent)                        

                    print(entry.remote_host_name, entry.remote_host_port, entry.final_status, entry.bytes_sent, entry.request_line)
            except (FileNotFoundError, InodeChangedError, FileShrunkError) as e:
                time.sleep(1)        


def main():
    le = ApacheLogExporter()
    le.read_log_files()


if __name__ == "__main__":
    main()