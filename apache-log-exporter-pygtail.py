from pygtail import Pygtail
import os
import time

# https://stackoverflow.com/questions/12544510/parsing-apache-log-files
def apache2_logrow(s):
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
    return row

# https://stackoverflow.com/questions/12523044/how-can-i-tail-a-log-file-in-python
def follow(file):
    """ Yield each line from a file as they are written. """
    line = ''
    while True:
        tmp = file.readline()
        if tmp is not None:
            line += tmp
            if line.endswith("\n"):
                yield line
                line = ''
        else:
            time.sleep(0.1)


def main():
    fn = "sample.log"
    while True:
        try:
            if os.path.exists(fn):
                print("exist")
                for line in Pygtail(fn):
                    parts = apache2_logrow(line)
                    print(parts)
        except FileNotFoundError:
            pass
        time.sleep(1)


if __name__ == "__main__":
    main()