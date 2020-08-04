#!/usr/bin/env python3

from datetime import datetime
from json import dump, load
from locale import strxfrm
from os import getcwd, makedirs
from os.path import dirname, join, realpath
from subprocess import run
from typing import Any, Dict
from urllib.request import urlopen

from yaml import safe_load

__dir__ = dirname(dirname(realpath(__file__)))
TEMP = join(__dir__, "temp")
ASSETS = join(__dir__, "assets")
ARTIFACTS = join(__dir__, "artifacts")
DOCKER_PATH = join(__dir__, "ci", "docker")


LANG_COLOURS = """
https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml
"""

LANG_COLOURS_JSON = join(ARTIFACTS, "github_colours.json")
TEMP_JSON = join(TEMP, "icons.json")

SRC_ICONS = ("unicode_icons", "emoji_icons")


def merge(ds1: Any, ds2: Any, replace: bool = False) -> Any:
    if type(ds1) is dict and type(ds2) is dict:
        append = {k: merge(ds1.get(k), v, replace) for k, v in ds2.items()}
        return {**ds1, **append}
    if type(ds1) is list and type(ds2) is list:
        if replace:
            return ds2
        else:
            return [*ds1, *ds2]
    else:
        return ds2


def call(prog: str, *args: str, cwd: str = getcwd()) -> None:
    ret = run([prog, *args], cwd=cwd)
    if ret.returncode != 0:
        exit(ret.returncode)


def fetch(uri: str) -> str:
    with urlopen(uri) as resp:
        ret = resp.read().decode()
        return ret


def recur_sort(data: Any) -> Any:
    if type(data) is dict:
        return {k: recur_sort(data[k]) for k in sorted(data, key=strxfrm)}
    elif type(data) is list:
        return [recur_sort(el) for el in data]
    else:
        return data


def slurp_json(path: str) -> Any:
    with open(path) as fd:
        return load(fd)


def spit_json(path: str, json: Any) -> None:
    sorted_json = recur_sort(json)
    with open(path, "w") as fd:
        dump(sorted_json, fd, ensure_ascii=False, check_circular=False, indent=2)


def process_json(json: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    new = {}
    new["type"] = {f".{k}": v for k, v in json["extensions"].items()}
    new["name_exact"] = json["exact"]
    new["name_glob"] = {
        k.rstrip("$").replace(r"\.", "."): v for k, v in json["glob"].items()
    }
    new["default_icon"] = json["default"]
    new["folder"] = json["folder"]
    return new


def devicons() -> None:
    image = "chad-icons"
    time = format(datetime.now(), "%H-%M-%S")
    container = f"{image}-{time}"
    src = f"{container}:/root/icons.json"

    makedirs(TEMP, exist_ok=True)
    call("docker", "build", "-t", image, "-f", "Dockerfile", ".", cwd=DOCKER_PATH)
    call("docker", "create", "--name", container, image)
    for icon in SRC_ICONS:
        src = f"{container}:/root/{icon}.json"
        call("docker", "cp", src, TEMP_JSON)
        json = slurp_json(TEMP_JSON)
        basic = slurp_json(join(ASSETS, f"{icon}.base.json"))
        parsed = process_json(json)
        merged = merge(parsed, basic)
        dest = join(ARTIFACTS, f"{icon}.json")
        spit_json(dest, merged)
    call("docker", "rm", container)


def github_colours() -> None:
    raw = fetch(LANG_COLOURS)
    yaml = safe_load(raw)
    lookup = {
        ext: colour
        for ext, colour in (
            (ext, val.get("color"))
            for val in yaml.values()
            for ext in val.get("extensions", ())
        )
        if colour
    }

    spit_json(LANG_COLOURS_JSON, lookup)


def main() -> None:
    devicons()
    github_colours()
    call("git", "diff", "--exit-code")


main()
