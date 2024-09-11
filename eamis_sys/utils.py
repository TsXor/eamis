from typing import Any, Callable, TypeVar, Optional
from typing_extensions import ParamSpec
import time, datetime, warnings
from pydantic import TypeAdapter

T = TypeVar('T')
P = ParamSpec('P'); R = TypeVar('R')

def spin_until(t: float, interval: float = 0.5):
    while True:
        if time.time() >= t:
            break
        time.sleep(interval)

def spin_until_date(d: datetime.datetime, interval: float = 0.5):
    spin_until(d.timestamp(), interval=interval)

def supress_warning(wt: Optional[type[Warning]] = None):
    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        def result(*args: P.args, **kwargs: P.kwargs) -> R:
            with warnings.catch_warnings():
                if wt is not None:
                    warnings.filterwarnings("ignore", category=wt)
                else:
                    warnings.simplefilter("ignore")
                return f(*args, **kwargs)
        return result
    return decorator

def with_validate(typ: type[T]):
    validator = TypeAdapter(typ)
    def decorator(f: Callable[P, Any]) -> Callable[P, T]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            return validator.validate_python(f(*args, **kwargs))
        return wrapper
    return decorator
