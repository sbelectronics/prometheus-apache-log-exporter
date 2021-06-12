import os
import stat
import time
from apachelogs import LogParser, COMBINED

class InodeChangedError(Exception):
    pass

class FileShrunkError(Exception):
    pass

class LogRowIncorrectPartCount(Exception):
    pass

class ApacheLogRow:
    def __init__(self):
        pass

    # https://stackoverflow.com/questions/12544510/parsing-apache-log-files
    def processLine(self, s):
        ''' Fast split on Apache2 log lines

        http://httpd.apache.org/docs/trunk/logs.html
        '''
        row = [ ]
        qe = qp = None # quote end character (qe) and quote parts (qp)
        for s in s.replace('\r','').replace('\n','').split(' '):
            if qp:
                qp.append(s)
            elif '' == s: # blanks
                row.append('')
            elif '"' == s[0]: # begin " quote "
                qp = [ s ]
                qe = '"'
            elif '[' == s[0]: # begin [ quote ]
                qp = [ s ]
                qe = ']'
            else:
                row.append(s)

            l = len(s)
            if l and qe == s[-1]: # end quote
                if l == 1 or s[-2] != '\\': # don't end on escaped quotes
                    row.append(' '.join(qp)[1:-1].replace('\\'+qe, qe))
                    qp = qe = None

        if (len(row) != 10):
            raise LogRowIncorrectOartCount

        self.parseParts(row)

    def parseParts(self, parts):
        # part0 is host:port
        if ":" in parts[0]:
            (self.localAddress, self.localPort) = parts[0].split(":", 1)
        else:
            self.localAddress = parts[0]
            self.localPort = 80  # took a guess

        self.remoteAddress = parts[1]

        self.dateStr = parts[4]

        (self.cmd, self.url, self.proto) = self.decodeCommand(parts[5])

        self.code = self.decodeInt(parts[6])

        self.length = self.decodeInt(parts[7])


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


def main():
    parser = LogParser(COMBINED)
    while True:
        try:
            for line in follow("sample.log"):
                entry = parser.parse(line)
                print(entry.remote_host, entry.final_status, entry.bytes_sent, entry.request_line)
        except (FileNotFoundError, InodeChangedError, FileShrunkError) as e:
            time.sleep(1)



if __name__ == "__main__":
    main()