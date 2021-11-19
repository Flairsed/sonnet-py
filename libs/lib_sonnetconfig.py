# Dynamic loader for sonnet configs
# Ultrabear 2021

import importlib

import sonnet_cfg

importlib.reload(sonnet_cfg)

from typing import Any, Type, TypeVar, Union, Optional, Callable

__all__ = [
    "GLOBAL_PREFIX",
    "BLACKLIST_ACTION",
    "STARBOARD_EMOJI",
    "STARBOARD_COUNT",
    "DB_TYPE",
    "SQLITE3_LOCATION",
    "REGEX_VERSION",
    "CLIB_LOAD",
    "GOLIB_LOAD",
    "GOLIB_VERSION",
    "BOT_NAME",
    ]

Typ = TypeVar("Typ")


# Loads a config and checks its type
def _load_cfg(attr: str, default: Typ, typ: Type[Typ], testfunc: Optional[Callable[[Typ], bool]] = None, errmsg: str = "") -> Typ:

    conf: Union[Any, Typ] = getattr(sonnet_cfg, attr, default)

    if not isinstance(conf, typ):
        raise TypeError(f"Sonnet Config {attr} is not type {typ.__name__}")

    if testfunc is not None and not testfunc(conf):
        raise TypeError(f"Sonnet Config {attr}: {errmsg}")

    return conf


GLOBAL_PREFIX = _load_cfg("GLOBAL_PREFIX", "!", str, lambda s: " " not in s, "Prefix contains whitespace")
BLACKLIST_ACTION = _load_cfg("BLACKLIST_ACTION", "warn", str, lambda s: s in {"warn", "kick", "mute", "ban"}, "Blacklist action not valid")
STARBOARD_EMOJI = _load_cfg("STARBOARD_EMOJI", "⭐", str)
STARBOARD_COUNT = _load_cfg("STARBOARD_COUNT", "5", str, lambda s: s.isdigit(), "Starboard Count is not digit")
DB_TYPE = _load_cfg("DB_TYPE", "mariadb", str, lambda s: s in {"mariadb", "sqlite3"}, "Database type not valid")
SQLITE3_LOCATION = _load_cfg("SQLITE3_LOCATION", "datastore/sonnetdb.db", str)
REGEX_VERSION = _load_cfg("REGEX_VERSION", "re2", str, lambda s: s in {"re", "re2"}, "RegEx ver is not re or re2")
CLIB_LOAD = _load_cfg("CLIB_LOAD", True, bool)
GOLIB_LOAD = _load_cfg("GOLIB_LOAD", True, bool)
GOLIB_VERSION = _load_cfg("GOLIB_VERSION", "go", str)
BOT_NAME = _load_cfg("BOT_NAME", "Sonnet", str, lambda s: len(s) < 10, "Name is too large")
