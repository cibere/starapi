from enum import Enum


class Match(Enum):
    NONE = 0
    PARTIAL = 1
    FULL = 2


class WSState(Enum):
    connecting = 0
    connected = 1
    disconnected = 2
