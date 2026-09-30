"""Download the New Mexico OCD bulk data sets over anonymous FTP.

    host: ftp.emnrd.nm.gov, port 21, anonymous

Nothing to install -- ftplib is standard library. Just Run it; DOWNLOAD is on.

WHY THIS VERSION EXISTS
-----------------------
The previous run reported /volumes as unreadable. That was NOT a permission
problem: the server (FileZilla Pro Enterprise) starts resetting data
connections after ~15 listings in one session, so whichever directory happens
to be 16th fails. Every failure was ConnectionResetError, and the same
directories listed fine earlier in a shallower walk.

So this version reconnects on failure and retries, pauses briefly between
listings, and skips the natural-gas-waste directories, which are large,
irrelevant here, and were burning connections.

THE SERVER LAYOUT (23 Sep 2026) -- not what OCD's own PDF describes
    /Public/OCD/OCD GIS Data/   emptied; a note says GIS moved to the ArcGIS
                                hub, so there are no shapefiles here
    /Public/OCD/OCD Interface v1.1/
        OCD Interface v1.1 Data Dictionary.xlsx
        core/     acreage ogrid ogridroles pod podwc pool property
                  punevent spacingunit wchistory wellhistory
        other/    facility + natural-gas-waste sets  (skipped)
        volumes/  <- the one that matters; production volumes should be here

Writes ocd_ftp_listing.txt beside the script.
"""
import ftplib
import os
import socket
import sys
import time

# ---------------------------------------------------------------- settings --
HOST = 'ftp.emnrd.nm.gov'
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Data', 'NewMexico')
DOWNLOAD = True          # set False for a listing-only dry run

ROOT = '/Public/OCD/OCD Interface v1.1'
PAUSE = 0.4              # seconds between listings; the server dislikes bursts

# Large and irrelevant to this paper -- do not walk, do not fetch.
SKIP_DIRS = {
    'upstreamnaturalgaswaste',
    'upstreamnaturalgaswastebeneficialuse',
    'midstreamnaturalgaswaste',
    'midstreamnaturalgaswastebeneficialuse',
    'midstreamnaturalgaswastegatheredvolume',
}

# Exact names to fetch from wherever they turn up in the tree. ~102 MB.
WANT = {
    'wellhistory.zip',      # wells -- the coordinate source now GIS is gone
    'wchistory.zip',        # well completions
    'pod.zip',
    'podwc.zip',
    'property.zip',
    'pool.zip',
    'spacingunit.zip',
    'acreage.zip',
    'ogrid.zip',            # operators
    'punevent.zip',
    'README_CORE.txt',
    'OCD Interface v1.1 Data Dictionary.xlsx',
}
# Anything found under volumes/ is wanted too, whatever it is called.
WANT_DIRS = {ROOT + '/volumes'}

TRANSIENT = (ConnectionResetError, socket.timeout, TimeoutError, EOFError,
             ftplib.error_temp, OSError)


class Session:
    """An FTP connection that reopens itself when the server drops it."""

    def __init__(self, host):
        self.host = host
        self.ftp = None
        self.reconnects = 0

    def open(self):
        if self.ftp is not None:
            try:
                self.ftp.quit()
            except Exception:
                pass
        self.ftp = ftplib.FTP(timeout=30)
        self.ftp.connect(self.host, 21)
        self.ftp.login()                 # anonymous
        self.ftp.set_pasv(True)
        return self.ftp

    def _retry(self, fn, what, tries=4):
        for attempt in range(tries):
            if self.ftp is None:
                self.open()
            try:
                return fn(self.ftp)
            except TRANSIENT as exc:
                last = exc
                self.reconnects += 1
                wait = 1.5 * (attempt + 1)
                print('   .. %s dropped (%s); reconnect %d, wait %.1fs'
                      % (what, type(exc).__name__, self.reconnects, wait))
                time.sleep(wait)
                try:
                    self.open()
                except Exception:
                    self.ftp = None
            except ftplib.error_perm as exc:
                raise                    # a real permission error: do not retry
        raise last

    def listdir(self, path):
        def go(ftp):
            try:
                return [(n, f) for n, f in ftp.mlsd(path) if n not in ('.', '..')]
            except ftplib.error_perm:
                return [(os.path.basename(n), {'type': '?'}) for n in ftp.nlst(path)]
        out = self._retry(go, 'list ' + path)
        time.sleep(PAUSE)
        return out

    def retr(self, remote, local, size):
        def go(ftp):
            done = [0]
            t0 = time.time()
            with open(local, 'wb') as fh:
                def block(data):
                    done[0] += len(data)
                    fh.write(data)
                    if size:
                        rate = done[0] / 1e6 / max(time.time() - t0, 1e-6)
                        print('\r  %-46s %5.1f%%  %6.2f MB/s'
                              % (os.path.basename(remote),
                                 100.0 * done[0] / size, rate), end='')
                ftp.retrbinary('RETR ' + remote, block, blocksize=1 << 16)
            print()
            return local
        return self._retry(go, 'get ' + os.path.basename(remote))


def walk(s, path='/', depth=0, max_depth=6):
    found = []
    try:
        ents = s.listdir(path)
    except Exception as exc:
        print('%s!! %s -- %s: %s' % ('  ' * depth, path, type(exc).__name__, exc))
        return found
    for name, facts in sorted(ents):
        if name in SKIP_DIRS:
            print('%s[%s]  (skipped)' % ('  ' * depth, name))
            continue
        full = path.rstrip('/') + '/' + name
        if facts.get('type') == 'dir':
            print('%s[%s]' % ('  ' * depth, name))
            if depth < max_depth:
                found += walk(s, full, depth + 1, max_depth)
        else:
            size = int(facts.get('size', 0) or 0)
            print('%s%-58s %9.1f MB' % ('  ' * depth, name, size / 1e6))
            found.append((full, size))
    return found


class Tee:
    def __init__(self, path):
        self.term = sys.stdout
        self.log = open(path, 'w', encoding='utf-8')

    def write(self, s):
        self.term.write(s)
        self.log.write(s)

    def flush(self):
        self.term.flush()
        self.log.flush()


def main():
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'ocd_ftp_listing.txt')
    sys.stdout = Tee(log_path)
    download = DOWNLOAD or '--download' in sys.argv

    s = Session(HOST)
    print('connecting to %s ...' % HOST)
    print(s.open().getwelcome())

    print('\n--- tree ---')
    files = walk(s, '/')
    print('\n%d files found, %d reconnects.' % (len(files), s.reconnects))

    picks = [(p, sz) for p, sz in files
             if os.path.basename(p) in WANT
             or any(p.startswith(d + '/') for d in WANT_DIRS)]
    missing = WANT - {os.path.basename(p) for p, _ in picks}
    print('\n--- %d files selected, %.1f MB ---'
          % (len(picks), sum(sz for _, sz in picks) / 1e6))
    for p, sz in sorted(picks):
        print('  %-70s %8.1f MB' % (p, sz / 1e6))
    if missing:
        print('  NOT FOUND: %s' % ', '.join(sorted(missing)))

    if download and picks:
        os.makedirs(OUT_DIR, exist_ok=True)
        print('\ndownloading to %s' % OUT_DIR)
        for p, sz in sorted(picks, key=lambda t: t[1]):     # small first
            local = os.path.join(OUT_DIR, os.path.basename(p))
            if os.path.exists(local) and os.path.getsize(local) == sz:
                print('  have   %s' % os.path.basename(p))
                continue
            try:
                s.retr(p, local, sz)
            except Exception as exc:
                print('\n  FAILED %s -- %s: %s' % (p, type(exc).__name__, exc))
        print('\ndone, %d reconnects total.' % s.reconnects)

    try:
        s.ftp.quit()
    except Exception:
        pass
    print('\nlisting written to %s' % log_path)
    sys.stdout.flush()


if __name__ == '__main__':
    main()
