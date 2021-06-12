import os
import stat
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