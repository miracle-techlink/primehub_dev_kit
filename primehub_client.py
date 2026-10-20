#!/usr/bin/env python3
"""PrimeHub API client - SM4-CBC encrypted transport, reverse-engineered from web bundle.
Usage: primehub_client.py <path> '<json-params>'
"""
import json, urllib.request, urllib.parse, uuid, time, sys
from gmssl.sm4 import CryptSM4, SM4_ENCRYPT, SM4_DECRYPT

IV_S  = '38fed878322f002e58db85fdf0417a0f'
KEY_S = '160a505137ed9d6efbf089ebfec49a93'
def unscramble(s):
    e = list(s); n = [[1,3],[3,8],[2,5],[1,9],[11,15],[11,15],[1,3]]
    for t in reversed(n):
        L = len(e)-(t[1]-t[0]); seg = e[L:]; del e[L:]; e[t[0]:t[0]] = seg
    return ''.join(e)
KEY = bytes.fromhex(unscramble(KEY_S)); IV = bytes.fromhex(unscramble(IV_S))
BASE = 'https://primehub.primebot.com'

def call(path, params, token=None):
    params = dict(params); params['timestamp'] = int(time.time()*1000); params['requestId'] = str(uuid.uuid4())
    t = json.dumps(params, separators=(',',':'))
    inner = urllib.parse.quote(t, safe='')
    c = CryptSM4(); c.set_key(KEY, SM4_ENCRYPT)
    ct = c.crypt_cbc(IV, inner.encode()).hex()
    body = json.dumps({'data': ct}).encode()
    h = {'Content-Type':'application/json','request-t':'true','X-Request-Id':'req-'+uuid.uuid4().hex[:8],
         'Origin':BASE,'Referer':BASE+'/'}
    if token: h['Authorization'] = 'Bearer '+token
    req = urllib.request.Request(BASE+path, data=body, headers=h)
    try:
        r = urllib.request.urlopen(req, timeout=30)
        raw = r.read().decode()
    except urllib.error.HTTPError as ex:
        raw = ex.read().decode()
    d = json.loads(raw)
    if isinstance(d.get('data'), str) and d.get('code') == 1000:
        try:
            c2 = CryptSM4(); c2.set_key(KEY, SM4_DECRYPT)
            pt = c2.crypt_cbc(IV, bytes.fromhex(d['data']))
            d['data'] = json.loads(urllib.parse.unquote(pt.decode()))
        except Exception as e:
            d['_decrypt_error'] = str(e)
    return d

if __name__ == '__main__':
    path = sys.argv[1]; params = json.loads(sys.argv[2]) if len(sys.argv)>2 else {}
    token = sys.argv[3] if len(sys.argv)>3 else None
    print(json.dumps(call(path, params, token), ensure_ascii=False, indent=1)[:4000])
