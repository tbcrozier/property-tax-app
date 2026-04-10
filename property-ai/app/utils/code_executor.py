import io
import re
from contextlib import redirect_stdout

import numpy as np
import pandas as pd


class SQLSafetyError(Exception):
    pass


_BLOCKED = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE)\b",
    re.IGNORECASE,
)


def validate_sql(query: str) -> str:
    if _BLOCKED.search(query):
        raise SQLSafetyError("Only SELECT/WITH queries are allowed.")
    clean = query.strip().rstrip(";")
    if not re.search(r"\bLIMIT\b", clean, re.IGNORECASE):
        clean = f"{clean}\nLIMIT 1000"
    return clean


def execute_python_on_df(code: str, df: pd.DataFrame) -> tuple[str, str | None]:
    """
    Execute user/LLM python code against a dataframe copy.
    Returns (stdout_output, error_or_none).
    """
    safe_builtins = {
        "print": print,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "sorted": sorted,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "isinstance": isinstance,
        "type": type,
    }

    local_ns = {
        "__builtins__": safe_builtins,
        "pd": pd,
        "np": np,
        "df": df.copy(),
    }

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            exec(compile(code, "<analyst>", "exec"), local_ns)  # noqa: S102
        return buf.getvalue(), None
    except Exception as exc:
        return buf.getvalue(), str(exc)
