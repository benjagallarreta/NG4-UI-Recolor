"""GDeflate decompression via the game's own dstorage.dll (IDStorageCompressionCodec)."""
import ctypes, ctypes.wintypes as wt, uuid, os

# Carpeta del juego: variable de entorno NG4_GAME_DIR (la fija build_mod.py) o la ruta por defecto.
GAME_DIR = os.environ.get("NG4_GAME_DIR", r"E:\Juegos\NINJA GAIDEN 4")
DLL = os.path.join(GAME_DIR, "dstorage.dll")
os.add_dll_directory(GAME_DIR)
os.add_dll_directory(os.path.join(GAME_DIR, "DirectStorage"))
_core = ctypes.WinDLL(os.path.join(GAME_DIR, "DirectStorage", "dstoragecore.dll"))
_d = ctypes.WinDLL(DLL)

class GUID(ctypes.Structure):
    _fields_ = [("b", ctypes.c_ubyte * 16)]
    @classmethod
    def of(cls, s):
        g = cls(); ctypes.memmove(g.b, uuid.UUID(s).bytes_le, 16); return g

IID_CODEC = GUID.of("84ef5121-9b43-4d03-b5c1-cc34606b262d")
_codec = ctypes.c_void_p()
# HRESULT DStorageCreateCompressionCodec(DSTORAGE_COMPRESSION_FORMAT fmt=1 (GDeflate), UINT32 threads, REFIID, void**)
hr = _d.DStorageCreateCompressionCodec(1, 0, ctypes.byref(IID_CODEC), ctypes.byref(_codec))
if hr != 0:
    raise OSError(f"DStorageCreateCompressionCodec hr=0x{hr & 0xffffffff:08x}")
_vt = ctypes.cast(ctypes.cast(_codec, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
# vtable: QI, AddRef, Release, CompressBuffer, DecompressBuffer, CompressBufferBound
_Decompress = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                 ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))(_vt[4])

_Compress = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                               ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))(_vt[3])
_Bound = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t)(_vt[5])

def compress(src: bytes, level: int = 2) -> bytes:
    """level: 0=default, 1=fastest, 2=best ratio (DSTORAGE_COMPRESSION)."""
    cap = _Bound(_codec, len(src))
    sb = ctypes.create_string_buffer(src, len(src))
    db = ctypes.create_string_buffer(cap)
    n = ctypes.c_size_t(0)
    hr = _Compress(_codec, sb, len(src), level, db, cap, ctypes.byref(n))
    if hr != 0:
        raise OSError(f"CompressBuffer hr=0x{hr & 0xffffffff:08x}")
    return db.raw[:n.value]

def decompress(src: bytes, out_size: int) -> bytes:
    sb = ctypes.create_string_buffer(src, len(src))
    db = ctypes.create_string_buffer(out_size)
    n = ctypes.c_size_t(0)
    hr = _Decompress(_codec, sb, len(src), db, out_size, ctypes.byref(n))
    if hr != 0:
        raise OSError(f"DecompressBuffer hr=0x{hr & 0xffffffff:08x}")
    return db.raw[:n.value]

def read_entry(e):
    """Return dict name->bytes for the inline (non-streamed) subfiles of an index entry."""
    with open(os.path.join(GAME_DIR, "Assets", e["arc"]), "rb") as f:
        f.seek(e["off"]); blob = f.read(e["comp"])
    raw = decompress(blob, e["raw"]) if e["comp"] != e["raw"] else blob
    out = {}
    for name, soff, hoff, size, csize in e["files"]:
        if soff == 0 and csize == 0:
            out[name] = raw[hoff:hoff + size]
    return raw, out
