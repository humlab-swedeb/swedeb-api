from enum import Enum


class Position(str, Enum):
    LEFT = ("left",)
    RIGHT = "right"
    ANY = "any"
