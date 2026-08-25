"""ctypes bindings for ygopro-core's OCG_* C API (core version 11.0).

The API is small and stable by design - it is plain C specifically so that
embedders can bind it. The whole surface is 13 functions; everything
interesting happens through the message/response loop:

    OCG_DuelProcess -> AWAITING  (the engine needs a decision)
    OCG_DuelGetMessage           (read what happened + what's being asked)
    OCG_DuelSetResponse          (answer)

Card data and Lua scripts are supplied by *our* callbacks, which is what lets
us pin a card pool by commit hash.
"""

from __future__ import annotations

import ctypes as C
from pathlib import Path

# ----------------------------------------------------------------- enums

class DuelCreation:
    SUCCESS = 0
    NO_OUTPUT = 1
    NOT_CREATED = 2
    NULL_DATA_READER = 3
    NULL_SCRIPT_READER = 4
    INCOMPATIBLE_LUA_API = 5
    NULL_RNG_SEED = 6


class DuelStatus:
    END = 0
    AWAITING = 1
    CONTINUE = 2


class LogType:
    ERROR = 0
    FROM_SCRIPT = 1
    FOR_DEBUG = 2
    UNDEFINED = 3


# ----------------------------------------------------------------- structs

class OCG_CardData(C.Structure):
    _fields_ = [
        ("code", C.c_uint32),
        ("alias", C.c_uint32),
        ("setcodes", C.POINTER(C.c_uint16)),  # null-terminated
        ("type", C.c_uint32),
        ("level", C.c_uint32),
        ("attribute", C.c_uint32),
        ("race", C.c_uint64),
        ("attack", C.c_int32),
        ("defense", C.c_int32),
        ("lscale", C.c_uint32),
        ("rscale", C.c_uint32),
        ("link_marker", C.c_uint32),
    ]


class OCG_Player(C.Structure):
    _fields_ = [
        ("startingLP", C.c_uint32),
        ("startingDrawCount", C.c_uint32),
        ("drawCountPerTurn", C.c_uint32),
    ]


# Callback signatures. These must be module-level so the types are stable.
OCG_DataReader = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.POINTER(OCG_CardData))
OCG_DataReaderDone = C.CFUNCTYPE(None, C.c_void_p, C.POINTER(OCG_CardData))
OCG_ScriptReader = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_char_p)
OCG_LogHandler = C.CFUNCTYPE(None, C.c_void_p, C.c_char_p, C.c_int)


class OCG_DuelOptions(C.Structure):
    _fields_ = [
        ("seed", C.c_uint64 * 4),  # Xoshiro256 state - the determinism handle
        ("flags", C.c_uint64),
        ("team1", OCG_Player),
        ("team2", OCG_Player),
        ("cardReader", OCG_DataReader),
        ("payload1", C.c_void_p),
        ("scriptReader", OCG_ScriptReader),
        ("payload2", C.c_void_p),
        ("logHandler", OCG_LogHandler),
        ("payload3", C.c_void_p),
        ("cardReaderDone", OCG_DataReaderDone),
        ("payload4", C.c_void_p),
        ("enableUnsafeLibraries", C.c_uint8),
    ]


class OCG_NewCardInfo(C.Structure):
    _fields_ = [
        ("team", C.c_uint8),
        ("duelist", C.c_uint8),
        ("code", C.c_uint32),
        ("con", C.c_uint8),
        ("loc", C.c_uint32),
        ("seq", C.c_uint32),
        ("pos", C.c_uint32),
    ]


class OCG_QueryInfo(C.Structure):
    _fields_ = [
        ("flags", C.c_uint32),
        ("con", C.c_uint8),
        ("loc", C.c_uint32),
        ("seq", C.c_uint32),
        ("overlay_seq", C.c_uint32),
    ]


# ----------------------------------------------------------------- loader

DEFAULT_LIB = Path(__file__).parent / "lib" / "libocgcore.dylib"


def load(path: str | Path = DEFAULT_LIB) -> C.CDLL:
    """Load libocgcore and install argtypes/restypes.

    Setting argtypes is not optional cosmetics here: on arm64 the calling
    convention differs enough that passing a 64-bit pointer as a default
    c_int will silently truncate.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found - run scripts/build_core.sh first"
        )
    lib = C.CDLL(str(path))

    lib.OCG_GetVersion.argtypes = [C.POINTER(C.c_int), C.POINTER(C.c_int)]
    lib.OCG_GetVersion.restype = None

    lib.OCG_CreateDuel.argtypes = [C.POINTER(C.c_void_p), C.POINTER(OCG_DuelOptions)]
    lib.OCG_CreateDuel.restype = C.c_int

    lib.OCG_DestroyDuel.argtypes = [C.c_void_p]
    lib.OCG_DestroyDuel.restype = None

    lib.OCG_DuelNewCard.argtypes = [C.c_void_p, C.POINTER(OCG_NewCardInfo)]
    lib.OCG_DuelNewCard.restype = None

    lib.OCG_StartDuel.argtypes = [C.c_void_p]
    lib.OCG_StartDuel.restype = None

    lib.OCG_DuelProcess.argtypes = [C.c_void_p]
    lib.OCG_DuelProcess.restype = C.c_int

    lib.OCG_DuelGetMessage.argtypes = [C.c_void_p, C.POINTER(C.c_uint32)]
    lib.OCG_DuelGetMessage.restype = C.c_void_p

    lib.OCG_DuelSetResponse.argtypes = [C.c_void_p, C.c_void_p, C.c_uint32]
    lib.OCG_DuelSetResponse.restype = None

    lib.OCG_LoadScript.argtypes = [C.c_void_p, C.c_char_p, C.c_uint32, C.c_char_p]
    lib.OCG_LoadScript.restype = C.c_int

    lib.OCG_DuelQueryCount.argtypes = [C.c_void_p, C.c_uint8, C.c_uint32]
    lib.OCG_DuelQueryCount.restype = C.c_uint32

    for fn in (lib.OCG_DuelQuery, lib.OCG_DuelQueryLocation):
        fn.argtypes = [C.c_void_p, C.POINTER(C.c_uint32), C.POINTER(OCG_QueryInfo)]
        fn.restype = C.c_void_p

    lib.OCG_DuelQueryField.argtypes = [C.c_void_p, C.POINTER(C.c_uint32)]
    lib.OCG_DuelQueryField.restype = C.c_void_p

    return lib


def version(lib: C.CDLL) -> tuple[int, int]:
    major, minor = C.c_int(), C.c_int()
    lib.OCG_GetVersion(C.byref(major), C.byref(minor))
    return major.value, minor.value
