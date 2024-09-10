from typing import Any
import json, javascript

def js_eval_data_reload(code: str, varname: str, setup: str = '') -> Any:
    '''
    调用PyJSBridge解码eamis的奇葩回复。
    注：解码过程可能较慢。
    '''
    return json.loads(javascript.eval_js(f'var window = {{}}; {setup}; {code}; return JSON.stringify({varname});'))
