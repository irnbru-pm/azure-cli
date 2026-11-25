"""Private socket inherited from the signed IrnBru launcher."""
import json
import os
import struct
from threading import Lock

os.set_inheritable(3, False)
channel = os.fdopen(3, 'r+b', buffering=0)
lock = Lock()


def read_exact(count):
    data = bytearray()
    while len(data) < count:
        chunk = channel.read(count - len(data))
        if not chunk:
            raise RuntimeError('IrnBru credential service disconnected')
        data.extend(chunk)
    return data


def request(op, value, expected):
    data = json.dumps(dict(op=op, profile='AzureCloud', value=value, expected=expected)).encode()
    with lock:
        channel.write(struct.pack('!I', len(data)) + data)
        size, = struct.unpack('!I', read_exact(4))
        if not 0 < size <= 262144:
            raise RuntimeError('Invalid IrnBru credential response')
        reply = json.loads(read_exact(size))
    if reply.get('ok') is not True:
        raise RuntimeError(reply.get('error', 'IrnBru credential request failed'))
    return reply['value']
