#!/usr/bin/env python3
"""Generate a stable package manifest and original, neutral PNG tiles."""
import argparse
import re
import shutil
import struct
import uuid
import zlib
from pathlib import Path
from xml.etree import ElementTree as ET

NS = 'http://schemas.microsoft.com/appx/manifest/foundation/windows10'
MP = 'http://schemas.microsoft.com/appx/2014/phone/manifest'
UAP = 'http://schemas.microsoft.com/appx/manifest/uap/windows10'
RESCAP = 'http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities'
for prefix, uri in [('', NS), ('mp', MP), ('uap', UAP), ('rescap', RESCAP)]:
    ET.register_namespace(prefix, uri)
TILES = {'StoreLogo.png': (50, 50), 'Square44x44Logo.png': (44, 44),
         'Square150x150Logo.png': (150, 150), 'Wide310x150Logo.png': (310, 150),
         'SplashScreen.png': (620, 300)}

def version(value):
    parts = value.split('.')
    if len(parts) != 4 or any(not re.fullmatch(r'[0-9]+', x) or int(x) > 65535 for x in parts) or int(parts[0]) == 0:
        raise ValueError('MSIX version requires four integers from 0 to 65535, major > 0')
    return '.'.join(str(int(x)) for x in parts)

def png(path, w, h):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data)&0xffffffff)
    side = max(4, min(w, h)//8)
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            dx, dy = x-w//2, y-h//2
            if abs(dx) < 3*side and abs(dy) < 2*side:
                rgb = (237,240,243) if (dx//side+dy//side)%2 == 0 else (45,58,78)
            else:
                rgb = (20,31,48)
            row.extend(rgb)
        rows.append(bytes(row))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w,h,8,2,0,0,0)) + chunk(b'IDAT', zlib.compress(b''.join(rows),9)) + chunk(b'IEND',b''))

def prepare(template, output, name, publisher, ver, product):
    if not re.fullmatch(r'[A-Za-z0-9.-]{3,50}', name):
        raise ValueError('Invalid package identity')
    if not publisher.startswith('CN=') or 'CHANGE-ME' in publisher:
        raise ValueError('Publisher must equal the certificate subject')
    ver = version(ver)
    tree = ET.parse(template/'Package.appxmanifest')
    root = tree.getroot()
    identity = root.find(f'{{{NS}}}Identity')
    identity.set('Name', name)
    identity.set('Publisher', publisher)
    identity.set('Version', ver)
    root.find(f'{{{MP}}}PhoneIdentity').set('PhoneProductId', str(uuid.uuid5(uuid.NAMESPACE_URL, name+'|'+publisher)))
    props = root.find(f'{{{NS}}}Properties')
    display = 'Retro Rewind Xbox Enhanced' if product == 'retro' else 'Mario Kart Wii Xbox Enhanced'
    props.find(f'{{{NS}}}DisplayName').text = display
    props.find(f'{{{NS}}}PublisherDisplayName').text = publisher[3:].split(',')[0]
    visual = root.find(f'.//{{{UAP}}}VisualElements')
    visual.set('DisplayName', display)
    visual.set('Description', display + ' - personal UWP build')
    output.mkdir(parents=True, exist_ok=False)
    assets = output/'Assets'
    assets.mkdir()
    tree.write(output/'Package.appxmanifest', encoding='utf-8', xml_declaration=True)
    for f, (w,h) in TILES.items():
        png(assets/f,w,h)
    shutil.copy2(template/'Config.toml',output/'Config.toml')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('template',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('--name',required=True)
    p.add_argument('--publisher',required=True)
    p.add_argument('--version',required=True)
    p.add_argument('--product',choices=['base','retro'],default='retro')
    a=p.parse_args()
    try:
        prepare(a.template,a.output,a.name,a.publisher,a.version,a.product)
    except (ValueError,OSError,ET.ParseError) as e:
        p.exit(1,str(e)+'\n')

if __name__=='__main__':
    main()
