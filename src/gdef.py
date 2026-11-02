"""Compresion GDeflate con el dstorage.dll del juego, cargado por init(game_dir)."""
import ctypes, uuid, os

GAME_DIR = None
_codec = None
_dll_dirs = []                       # referencias para que los directorios sigan registrados
_Compress = _Decompress = _Bound = None


class GUID(ctypes.Structure):
    _fields_ = [("b", ctypes.c_ubyte * 16)]

    @classmethod
    def of(cls, s):
        g = cls(); ctypes.memmove(g.b, uuid.UUID(s).bytes_le, 16); return g


IID_CODEC = GUID.of("84ef5121-9b43-4d03-b5c1-cc34606b262d")


def init(game_dir):
    global GAME_DIR, _codec, _Compress, _Decompress, _Bound
    game_dir = os.path.abspath(game_dir)
    if _codec is not None and GAME_DIR == game_dir:
        return
    core = os.path.join(game_dir, "DirectStorage", "dstoragecore.dll")
    dll = os.path.join(game_dir, "dstorage.dll")
    for p in (dll, core):
        if not os.path.isfile(p):
            raise FileNotFoundError(f"No se encontro {p}")
    _dll_dirs.append(os.add_dll_directory(game_dir))
    _dll_dirs.append(os.add_dll_directory(os.path.dirname(core)))
    ctypes.WinDLL(core)
    d = ctypes.WinDLL(dll)
    codec = ctypes.c_void_p()
    # HRESULT DStorageCreateCompressionCodec(DSTORAGE_COMPRESSION_FORMAT fmt=1 (GDeflate), UINT32 threads, REFIID, void**)
    hr = d.DStorageCreateCompressionCodec(1, 0, ctypes.byref(IID_CODEC), ctypes.byref(codec))
    if hr != 0:
        raise OSError(f"DStorageCreateCompressionCodec hr=0x{hr & 0xffffffff:08x}")
    vt = ctypes.cast(ctypes.cast(codec, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
    # vtable: QI, AddRef, Release, CompressBuffer, DecompressBuffer, CompressBufferBound
    _Compress = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                                   ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))(vt[3])
    _Decompress = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                     ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t))(vt[4])
    _Bound = ctypes.WINFUNCTYPE(ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t)(vt[5])
    _codec, GAME_DIR = codec, game_dir


def _ensure():
    if _codec is None:
        raise RuntimeError("gdef.init(game_dir) no fue llamado")


def compress(src: bytes, level: int = 0) -> bytes:
    """Comprime src (level 0 = normal, 1 = rapido)."""
    _ensure()
    cap = _Bound(_codec, len(src))
    sb = ctypes.create_string_buffer(src, len(src))
    db = ctypes.create_string_buffer(cap)
    n = ctypes.c_size_t(0)
    hr = _Compress(_codec, sb, len(src), level, db, cap, ctypes.byref(n))
    if hr != 0:
        raise OSError(f"CompressBuffer hr=0x{hr & 0xffffffff:08x}")
    return db.raw[:n.value]


def decompress(src: bytes, out_size: int) -> bytes:
    _ensure()
    sb = ctypes.create_string_buffer(src, len(src))
    db = ctypes.create_string_buffer(out_size)
    n = ctypes.c_size_t(0)
    hr = _Decompress(_codec, sb, len(src), db, out_size, ctypes.byref(n))
    if hr != 0:
        raise OSError(f"DecompressBuffer hr=0x{hr & 0xffffffff:08x}")
    return db.raw[:n.value]
