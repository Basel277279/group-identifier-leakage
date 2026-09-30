"""Turn the New Mexico OCD XML dumps into CSV.

The OCD files are SQL Server FOR XML exports: UTF-16, no XML declaration, an
inline xsd:schema at the top, then one element per row. wcproduction.xml is
roughly 20 GB uncompressed, so everything here streams -- nothing is unzipped
to disk and nothing is held in memory.

    python nm_ocd_extract.py --schema      print each table's field list, fast
    python nm_ocd_extract.py               write CSVs for the tables in TABLES
    python nm_ocd_extract.py wellhistory   just one table

Output goes to <DATA>/csv/<table>.csv
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_paths as P
import codecs
import csv
import os
import re
import sys
import time
import zipfile
from html import unescape

DATA = P.NM_DIR
OUT = os.path.join(DATA, 'csv')

# table -> (zip name, inner xml name, row tag)
TABLES = {
    'wellhistory':  ('wellhistory.zip',  'wellhistory.xml',  'wellhistory'),
    'wchistory':    ('wchistory.zip',    'wchistory.xml',    'wchistory'),
    'wcproduction': ('wcproduction.zip', 'wcproduction.xml', 'wcproduction'),
    'pod':          ('pod.zip',          'pod.xml',          'pod'),
    'podwc':        ('podwc.zip',        'podwc.xml',        'podwc'),
    'property':     ('property.zip',     'property.xml',     'property'),
    'pool':         ('pool.zip',         'pool.xml',         'pool'),
    'ogrid':        ('ogrid.zip',        'ogrid.xml',        'ogrid'),
    'spacingunit':  ('spacingunit.zip',  'spacingunit.xml',  'spacingunit'),
    'acreage':      ('acreage.zip',      'acreage.xml',      'acreage'),
    'punevent':     ('punevent.zip',     'punevent.xml',     'punevent'),
    # also downloaded; not needed for the pad/leakage work but here for --schema
    'wcinjection':  ('wcinjection.zip',  'wcinjection.xml',  'wcinjection'),
    'podvolume':    ('podvolume.zip',    'podvolume.xml',    'podvolume'),
    'podstorage':   ('podstorage.zip',   'podstorage.xml',   'podstorage'),
    'othervolume':  ('othervolume.zip',  'othervolume.xml',  'othervolume'),
}

# The tables this paper actually needs, in the order worth running them.
NEEDED = ['wellhistory', 'pod', 'podwc', 'property', 'pool', 'ogrid',
          'spacingunit', 'acreage', 'punevent', 'wchistory', 'wcproduction']

CHUNK = 1 << 20          # 1 MB of decoded text per feed


def local(tag):
    return tag.rsplit('}', 1)[-1]


def open_xml(zip_path, inner):
    """A text stream over the XML inside the zip, without extracting it."""
    zf = zipfile.ZipFile(zip_path)
    names = zf.namelist()
    if inner not in names:
        if len(names) != 1:
            raise RuntimeError('%s: expected one member, got %s' % (zip_path, names))
        inner = names[0]
    fh = zf.open(inner)
    return zf, codecs.getreader('utf-16')(fh)


def schema(zip_path, inner):
    """Field names, read off the inline xsd without touching the data."""
    import re
    zf, rd = open_xml(zip_path, inner)
    try:
        buf = ''
        while '</xsd:schema>' not in buf and len(buf) < 2_000_000:
            piece = rd.read(CHUNK)
            if not piece:
                break
            buf += piece
        head = buf.split('</xsd:schema>')[0]
        return re.findall(r'<xsd:element name="([^"]+)"', head)[1:]
    finally:
        zf.close()


FIELD_RE = re.compile(r'<([A-Za-z_][\w.\-]*)(?:\s[^>]*?)?(?:/>|>([^<]*)</\1>)')


def fields_of(text):
    """Pull <name>value</name> pairs out of one record. Values never contain
    '<' -- SQL Server escapes them -- so this is exact, not a heuristic."""
    out = {}
    for m in FIELD_RE.finditer(text):
        v = m.group(2)
        if v is None:
            out[m.group(1)] = ''                 # <field xsi:nil="true"/>
        elif '&' in v:
            out[m.group(1)] = unescape(v).strip()
        else:
            out[m.group(1)] = v.strip()
    return out


def rows(zip_path, inner, tag):
    """Yield one dict per record, at constant memory and with no size limit.

    Deliberately NOT an XML parser. expat tracks its position in a 32-bit
    counter, and these exports are a single line with no newlines, so any
    document past 2 GB dies with 'out of memory: line 1, column 2146435061'
    however carefully the tree is cleared. wcproduction.xml is about 20 GB.
    The format is machine-generated and flat -- one element per row, one level
    of simple fields, no attributes but xsi:nil -- so a scanner is both safe
    and several times faster.
    """
    zf, rd = open_xml(zip_path, inner)
    open_tag = '<' + tag
    close_tag = '</%s>' % tag
    buf = ''
    pos = 0
    try:
        # step over the inline xsd:schema
        while '</xsd:schema>' not in buf:
            piece = rd.read(CHUNK)
            if not piece:
                break
            buf += piece
        if '</xsd:schema>' in buf:
            buf = buf.split('</xsd:schema>', 1)[1]

        while True:
            end = buf.find(close_tag, pos)
            if end == -1:
                if pos:
                    buf = buf[pos:]
                    pos = 0
                piece = rd.read(CHUNK)
                if not piece:
                    break
                buf += piece
                continue
            start = buf.find(open_tag, pos)
            if start == -1 or start > end:
                pos = end + len(close_tag)
                continue
            rec = buf[start:end]
            pos = end + len(close_tag)
            gt = rec.find('>')
            if gt != -1:
                yield fields_of(rec[gt + 1:])
            if pos > 1 << 20:                    # compact, never grow forever
                buf = buf[pos:]
                pos = 0
    finally:
        zf.close()


def convert(name, zip_name, inner, tag):
    zip_path = os.path.join(DATA, zip_name)
    if not os.path.exists(zip_path):
        print('  %-14s MISSING %s' % (name, zip_name))
        return
    fields = schema(zip_path, inner)
    os.makedirs(OUT, exist_ok=True)
    out_path = os.path.join(OUT, name + '.csv')
    t0 = time.time()
    n = 0
    with open(out_path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        for rec in rows(zip_path, inner, tag):
            w.writerow(rec)
            n += 1
            if n % 250000 == 0:
                print('\r  %-14s %10d rows  %6.0f s' % (name, n, time.time() - t0),
                      end='')
    mb = os.path.getsize(out_path) / 1e6
    print('\r  %-14s %10d rows  %6.0f s  -> %s (%.1f MB)'
          % (name, n, time.time() - t0, os.path.basename(out_path), mb))


class Tee:
    """Echo the console to a log file so the run leaves a trace."""

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
    sys.stdout = Tee(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'nm_extract_log.txt'))
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    wanted = args or NEEDED

    if '--schema' in sys.argv:
        for name in wanted:
            zip_name, inner, _ = TABLES[name]
            p = os.path.join(DATA, zip_name)
            if not os.path.exists(p):
                print('%-14s MISSING' % name)
                continue
            f = schema(p, inner)
            print('%-14s %2d fields: %s' % (name, len(f), ', '.join(f)))
        return

    print('reading from %s' % DATA)
    print('writing to   %s\n' % OUT)
    for name in wanted:
        convert(name, *TABLES[name])


if __name__ == '__main__':
    main()
