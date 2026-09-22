"""Read only known page assignments; never execute JavaScript or emulate a challenge."""

import ast
import json
import re
from bs4 import BeautifulSoup
from common.exceptions import UnitRequestUnsupported

LITERAL = r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')'''


def unit_request_params(html: str, unit_no: str) -> dict[str, str | int]:
    scripts = "\n".join(tag.get_text() for tag in BeautifulSoup(html, "html.parser").find_all("script")
                        if not tag.get("src"))
    key = re.search(r"api\.apikey\s*=\s*" + LITERAL, scripts)
    token = re.search(r"api\.token\s*=\s*JSON\.parse\(\s*" + LITERAL + r"\s*\)", scripts)
    day = re.search(r"\.show\(\s*['\"]" + re.escape(unit_no) + r"['\"]\s*,\s*['\"](\d{8})['\"]", scripts)
    if not key or not token or not day:
        raise UnitRequestUnsupported("Normal page request configuration not found")
    try:
        api_key = ast.literal_eval(key.group(1))
        decoded = json.loads(ast.literal_eval(token.group(1)))
        if not isinstance(api_key, str) or not api_key or not isinstance(decoded, dict):
            raise ValueError
        for name in ("_i", "_t"):
            if type(decoded.get(name)) not in (str, int) or decoded[name] == "":
                raise ValueError
        return {"cd_dai": unit_no, "YMD_biz": day.group(1), "apikey": api_key,
                "_i": decoded["_i"], "_t": decoded["_t"], "page": 1}
    except (ValueError, SyntaxError, KeyError):
        raise UnitRequestUnsupported("Unsupported normal page request configuration") from None
