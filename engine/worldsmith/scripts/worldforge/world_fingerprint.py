"""Stable fingerprint of the terrain baseline used for editing manifests."""
import hashlib
import numpy as np

def baseline_fingerprint(world):
    digest=hashlib.sha256()
    for key in ('sea','height','elevation'):
        if key not in world: continue
        arr=np.asarray(world[key])
        digest.update(key.encode('ascii')+b'\0')
        digest.update(str(arr.shape).encode('ascii')+b'\0')
        if arr.dtype.kind in 'biuf':
            # Canonicalize numeric byte order and dtype for portability.
            if arr.dtype.kind in 'bi':
                canonical=np.asarray(arr,dtype='<i8')
            else:
                canonical=np.asarray(arr,dtype='<f8')
            digest.update(np.ascontiguousarray(canonical).tobytes())
        else:raise ValueError('unsupported terrain fingerprint dtype')
    return digest.hexdigest()
