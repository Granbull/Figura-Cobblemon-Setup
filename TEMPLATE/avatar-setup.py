import base64
import copy
import functools
import json
import math
import os
import re
import shutil
import struct
import sys
import uuid
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser


def fix_instruction_script(expr):
    if not isinstance(expr, str):
        return expr

    # Clean up non-ASCII, newlines, and backslashes
    expr = re.sub(r'[^\x00-\x7F]+', '', expr)
    expr = expr.replace('\n', ' ').replace('\r', ' ').replace('\\', '')
    expr = expr.strip()
    if not expr:
        return ""

    # Extract statements from Molang conditionals directly
    # e.g. q.has_entity ? { q.sound('wing_flap.medium'); }; -> KeySound('wing_flap.medium');
    # or q.is_gliding ? { q.sound('fly'); }
    expr = re.sub(r'.+?\s*\?\s*{\s*(.+?)\s*;?\s*}\s*;?', r'\1;', expr)

    # Convert q.sound to the avatar's KeySound function
    expr = expr.replace("q.sound", "KeySound")

    # Fix `time` / `life_time` -> `q.anim_time`
    expr = re.sub(r'(?<![a-zA-Z0-9_.])time\b', 'q.anim_time', expr)
    expr = re.sub(r'\b(?:q\.|query\.)?life_time\b', 'q.anim_time', expr, flags=re.IGNORECASE)

    # Fix Molang logical operators -> Lua logical operators
    expr = expr.replace('&&', ' and ')
    expr = expr.replace('||', ' or ')
    expr = expr.replace('!=', ' ~= ')

    # Fix numeric booleans like `!0` (true -> 1) and `!1` (false -> 0) BEFORE general `!` replacement
    expr = re.sub(r'!\s*0\b', '1', expr)
    expr = re.sub(r'!\s*1\b', '0', expr)
    expr = re.sub(r'!(?!=)', ' not ', expr)

    # Fix uppercase Molang variables (e.g., Q.anim_time -> q.anim_time)
    expr = re.sub(r'\bq\.', 'q.', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bquery\.', 'query.', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bv\.', 'v.', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bvariable\.', 'variable.', expr, flags=re.IGNORECASE)

    expr = expr.strip()
    # Ensure statement ends with semicolon if it's a call like KeySound(...)
    if expr and not expr.endswith(';') and not expr.endswith('}'):
        expr += ';'

    return expr


@functools.lru_cache(maxsize=1024)
def fix_math_expr(expr):
    if not isinstance(expr, str): return expr

    stripped = expr.strip()
    try:
        # If the expression is just a simple number (e.g., "-5", "3.14"), 
        # return it as-is to prevent it from being compiled as a math operation
        float(stripped)
        return stripped
    except ValueError:
        pass

    # Strip non-ASCII characters
    expr = re.sub(r'[^\x00-\x7F]+', '', expr)

    # Clean up newlines and backslashes
    expr = expr.replace('\n', ' ').replace('\r', ' ')
    expr = expr.replace('\\', '')
    
    # Fix stray equals signs (truncate them and anything after, as they invalidate math)
    expr = re.sub(r'(?<![=<>!~])=(?!=).*', '', expr)

    # Remove unary plus (invalid in Lua)
    expr = re.sub(r'^\s*\+', '', expr)
    expr = re.sub(r'([+\-*/<>=(,])\s*\+', r'\1', expr)
    
    # Fix unary minus at the start of the expression to avoid block parsing errors
    expr = re.sub(r'^\s*-(?=[a-zA-Z(])', '0-', expr)

    # Fix missing operators causing "unexpected symbol 287 (ğ)" (Token ID 287 is <number>, thanks kcin)
    # E.g. `q.r.pitch(0)30` -> `q.r.pitch(0) + 30`
    expr = re.sub(r'\)\s*(?=[0-9]|q\.|math\.|v\.|query\.)', ') + ', expr)
    expr = re.sub(r'([0-9])\s*(?=q\.|math\.|v\.|query\.)', r'\1 + ', expr)
    # Fix implicit multiplication like `30(-1)` -> `30 * (-1)`
    expr = re.sub(r'([0-9])\s*(?=\()', r'\1 * ', expr)
    
    # Fix hanging operators before closing parenthesis (e.g. `55+)` -> `55)`)
    expr = re.sub(r'([+\-*/])\s*\)', ')', expr)

    # Fix `time` -> `q.anim_time` (Prevents Lua from calling the global time() function)
    expr = re.sub(r'(?<![a-zA-Z0-9_.])time\b', 'q.anim_time', expr)
    # Fix `life_time` (e.g., q.life_time or query.life_time or life_time) -> `q.anim_time`
    expr = re.sub(r'\b(?:q\.|query\.)?life_time\b', 'q.anim_time', expr, flags=re.IGNORECASE)
    
    # Fix Molang logical operators -> Lua logical operators
    expr = expr.replace('&&', ' and ')
    expr = expr.replace('||', ' or ')
    expr = expr.replace('!=', ' ~= ')
    
    # Fix numeric booleans like `!0` (true -> 1) and `!1` (false -> 0) BEFORE general `!` replacement
    expr = re.sub(r'!\s*0\b', '1', expr)
    expr = re.sub(r'!\s*1\b', '0', expr)
    expr = re.sub(r'!(?!=)', ' not ', expr)
    
    # Fix malformed numbers with double decimals like `0.1.5` -> `0.15`
    expr = re.sub(r'([0-9]+\.[0-9]+)\.([0-9]+)', r'\1\2', expr)
    
    # UGLY HARDCODING BLOCK!!!
    # Fixes SPECIFICALLY Vulpix's ground_run tail_left2_3 keyframe.
    expr = re.sub(r'\b30\s+0\b', '30.0', expr)
    # Fixes Bronzong's sleep arm_right3 keyframe.
    expr = re.sub(r'math\.clampq\.r\.input_right\(18\)\s*\+\s*\(q\.r\.velocity_right\(8\),\s*-1,\s*0\)', 'math.clamp(q.r.input_right(18) + q.r.velocity_right(8), -1, 0)', expr)
    # Fixes Cyndaquil line and Blaziken's fire from rotating side to side
    expr = re.sub(r'-\s*1\s*\)\s*\+\s*[0-9.]+\s*\*\s*\([^\n\r]*', '', expr)

    # Fix ternary operators `? :` -> `and` `or` (Prevents Lua syntax errors)
    if '?' in expr and ':' in expr:
        expr = re.sub(r'\s*\?\s*', ' and ', expr)
        expr = re.sub(r'\s*:\s*', ' or ', expr)
        
    # Fix missing parentheses on function calls (e.g. q.r.yaw_change -> q.r.yaw_change())
    expr = re.sub(r'(q\.r\.[a-zA-Z0-9_]+)(?![a-zA-Z0-9_.]|\()', r'\g<1>()', expr)
    expr = re.sub(r'\b(math\.random)(?![a-zA-Z0-9_]|\()', r'\g<1>()', expr, flags=re.IGNORECASE)
    
    # Fix broken clamps with empty arguments like `,-,`
    expr = re.sub(r',\s*-\s*,', ', 0,', expr)
    expr = re.sub(r',\s*\+\s*,', ', 0,', expr)
    
    # Fix missing arguments at the end of functions like `,-,)` or `,)` -> `, 0)`
    expr = re.sub(r',\s*[-+]?\s*\)', ', 0)', expr)
    
    # Fix math typos and case sensitivity (e.g., Math.sin -> math.sin)
    # Note: sin and cos must map to Math.sin and Math.cos for degree conversions
    expr = re.sub(r'\b(?:math|ath|mth|mah|mat)\.(sin|cos|clamp|abs|pi|random|round|ceil|floor|min|max|pow|sqrt|exp|mod|fmod)\b', lambda m: f"Math.{m.group(1).lower()}" if m.group(1).lower() in ['sin', 'cos'] else f"math.{m.group(1).lower()}", expr, flags=re.IGNORECASE)
    
    # Fix missing parens for math functions
    expr = re.sub(r'\b(math\.(?:sin|cos|clamp|abs|pi|random|round|ceil|floor|min|max|pow|sqrt|exp|mod|fmod))(?=q\.|math\.|v\.|query\.)', r'\1(', expr, flags=re.IGNORECASE)

    # Fix uppercase Molang variables (e.g., Q.anim_time -> q.anim_time)
    expr = re.sub(r'\bq\.', 'q.', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bquery\.', 'query.', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bv\.', 'v.', expr, flags=re.IGNORECASE)
    expr = re.sub(r'\bvariable\.', 'variable.', expr, flags=re.IGNORECASE)

    # Balance parentheses (fixes extra/dangling parentheses)
    open_count = 0
    res = []
    for char in expr:
        if char == '(':
            open_count += 1
            res.append(char)
        elif char == ')':
            if open_count > 0:
                open_count -= 1
                res.append(char)
        else:
            res.append(char)
    expr = ''.join(res)
    if open_count > 0:
        expr += ')' * open_count

    # Fix hanging operators at the end of expressions
    expr = re.sub(r'([+\-*/<>=(,]\s*)+$', '', expr)
    
    return expr.strip()


global_fix_math_expr = fix_math_expr


def global_search_outliner(uuid_to_name, nodes, current_path, search_target):
    for node in nodes:
        # Ignore any cubes and meshes (strings), take groups (dicts)
        if isinstance(node, dict):
            name = node.get("name", "")
            if not name and "uuid" in node:
                name = uuid_to_name.get(node["uuid"], "")
                
            name = str(name)
            new_path = current_path + [name]
            if name.strip().lower() == search_target.strip().lower():
                return new_path
            
            children = node.get("children", [])
            if isinstance(children, list) and children:
                result = global_search_outliner(uuid_to_name, children, new_path, search_target)
                if result:
                    return result
    return None


def format_anim_ref(name):
    if not name:
        return ""
    name = str(name).strip()
    if not name or name == "nil":
        return ""
    if name.startswith("animations[") or name.startswith("animations.") or name.startswith("{"):
        return name
    return f"animations[config.modelname].{name}"


def extract_anim_name(expr):
    if not expr:
        return ""
    expr = str(expr).strip()
    if expr == "nil":
        return ""
    m = re.match(r'^animations(?:\[[^\]]+\]|\.[a-zA-Z0-9_]+)\.(.+)$', expr)
    if m:
        return m.group(1)
    return expr


def split_lua_args(arg_str):
    args = []
    curr = []
    depth = 0
    in_quote = False
    quote_char = ''
    for char in arg_str:
        if in_quote:
            curr.append(char)
            if char == quote_char:
                in_quote = False
        elif char in ('"', "'"):
            in_quote = True
            quote_char = char
            curr.append(char)
        elif char in ('(', '[', '{'):
            depth += 1
            curr.append(char)
        elif char in (')', ']', '}'):
            depth -= 1
            curr.append(char)
        elif char == ',' and depth == 0:
            args.append("".join(curr).strip())
            curr = []
        else:
            curr.append(char)
    if curr:
        args.append("".join(curr).strip())
    return args


def fmt_num(val):
    try:
        f = float(val)
        return str(int(f)) if f.is_integer() else str(f)
    except Exception:
        return str(val)


def get_unique_quirk_name(base_name, existing_names):
    if not base_name:
        return "quirk1"
    existing_lower = {name.lower() for name in existing_names if name}
    if base_name.lower() not in existing_lower:
        return base_name
    
    m = re.search(r'^(.*?)(\d+)$', base_name)
    if m:
        stem = m.group(1)
        start_num = int(m.group(2)) + 1
    else:
        stem = base_name
        start_num = 2
        
    num = start_num
    while f"{stem}{num}".lower() in existing_lower:
        num += 1
    return f"{stem}{num}"


class MockVar(float):
    def __new__(cls, val=0.0):
        return super().__new__(cls, val)
    def __getattr__(self, name):
        return self
    def __getitem__(self, name):
        return self
    def __call__(self, *args, **kwargs):
        return self


class QObj:
    def __init__(self, t):
        self.anim_time = t
        self.life_time = t
        self.r = MockVar()
    def __getattr__(self, name):
        return MockVar()
    def __call__(self, *args, **kwargs):
        return MockVar()


class MolangContext:
    def __init__(self, t):
        self.q = QObj(t)
        self.query = self.q
        self.Math = self
        self.math = self
        self.v = MockVar()
        self.variable = self.v
        self.pi = math.pi

    def sin(self, a): return math.sin(math.radians(a))
    def cos(self, a): return math.cos(math.radians(a))
    def tan(self, a): return math.tan(math.radians(a))
    def asin(self, a): return math.degrees(math.asin(max(-1.0, min(1.0, a))))
    def acos(self, a): return math.degrees(math.acos(max(-1.0, min(1.0, a))))
    def atan2(self, y, x): return math.degrees(math.atan2(y, x))
    def abs(self, a): return abs(a)
    def clamp(self, v, mn, mx): return max(mn, min(mx, v))
    def min(self, a, b): return min(a, b)
    def max(self, a, b): return max(a, b)
    def floor(self, a): return math.floor(a)
    def ceil(self, a): return math.ceil(a)
    def round(self, a): return round(a)
    def pow(self, a, b): return math.pow(a, b)
    def mod(self, a, b): return a % b
    def fmod(self, a, b): return math.fmod(a, b)
    def sqrt(self, a): return math.sqrt(max(0.0, a))
    def exp(self, a): return math.exp(a)
    def lerp(self, a, b, t): return a + (b - a) * t
    def sign(self, a): return 1.0 if a > 0 else (-1.0 if a < 0 else 0.0)
    def trunc(self, a): return float(int(a))
    def random(self, *args): return 0.0
    def KeySound(self, *args, **kwargs): return 0.0


def eval_molang_val(val, t, default_val=0.0):
    if not isinstance(val, str):
        return float(val) if val is not None else default_val
    try:
        return float(val)
    except ValueError:
        pass

    clean_expr = global_fix_math_expr(val)
    ctx = MolangContext(t)
    safe_globals = {
        '__builtins__': None,
        'Math': ctx,
        'math': ctx,
        'q': ctx.q,
        'query': ctx.query,
        'v': ctx.v,
        'variable': ctx.variable,
        'KeySound': ctx.KeySound
    }
    try:
        res = eval(clean_expr, safe_globals)
        return float(res)
    except Exception:
        try:
            fallback = re.sub(r'KeySound\([^)]*\)', '0', clean_expr)
            res = eval(fallback, safe_globals)
            return float(res)
        except Exception:
            return default_val


def has_math_expr(val):
    if not isinstance(val, str):
        return False
    try:
        float(val)
        return False
    except ValueError:
        return any(c in val for c in ('+', '*', '/', '(', ')', '?')) or any(k in val.lower() for k in ('math', 'query', 'q.', 'v.', 'sin', 'cos', 'clamp', 'anim_time', 'time'))


def extract_trig_args(expr):
    args = []
    matches = re.finditer(r'\b(?:Math|math)?\.?(?:sin|cos)\s*\(', expr, re.IGNORECASE)
    for m in matches:
        start_idx = m.end()
        depth = 1
        i = start_idx
        while i < len(expr) and depth > 0:
            if expr[i] == '(': depth += 1
            elif expr[i] == ')': depth -= 1
            i += 1
        if depth == 0:
            arg = expr[start_idx:i-1].strip()
            args.append(arg)
    return args


def get_expr_frequencies(expr):
    freqs = []
    # Fast regex matches for standard Cobblemon patterns
    m1 = re.findall(r'(?:q|query)\.anim_time\s*\*\s*90\s*\*\s*([0-9.]+)', expr)
    for f in m1: freqs.append(float(f))
    m2 = re.findall(r'90\s*\*\s*([0-9.]+)\s*\*\s*(?:q|query)\.anim_time', expr)
    for f in m2: freqs.append(float(f))
    m3 = re.findall(r'(?:q|query)\.anim_time\s*\*\s*([0-9.]+)', expr)
    for f in m3:
        val = float(f)
        if val != 90.0:
            freqs.append(val / 90.0)

    # Numerical derivative for arbitrary nested Molang trigonometric formulas
    for arg in extract_trig_args(expr):
        try:
            v1 = eval_molang_val(arg, 1.0)
            v0 = eval_molang_val(arg, 0.0)
            deg_per_sec = abs(v1 - v0)
            if deg_per_sec > 1e-4:
                freqs.append(deg_per_sec / 90.0)
        except Exception:
            pass

    return freqs


def calculate_loop_length(anim):
    existing_len = anim.get('length', 0)
    all_freqs = []
    animators = anim.get('animators', {})
    items = list(animators.values()) if isinstance(animators, dict) else (animators or [])

    max_non_math_t = 0
    has_math = False
    for a in items:
        for kf in a.get('keyframes', []):
            t = kf.get('time', 0)
            kf_has_math = False
            for dp in kf.get('data_points', []):
                for v in dp.values():
                    if has_math_expr(v):
                        has_math = True
                        kf_has_math = True
                        all_freqs.extend(get_expr_frequencies(v))
            if not kf_has_math:
                max_non_math_t = max(max_non_math_t, t)

    # Non-math animations keep their existing length
    if not has_math:
        return existing_len

    # Filter out near-zero drift frequencies (< 0.05) if primary frequencies exist
    significant_freqs = [f for f in all_freqs if f >= 0.05]
    freqs_to_use = significant_freqs if significant_freqs else all_freqs

    if not freqs_to_use:
        return existing_len if existing_len > 0.05 else 4.0

    candidates = [0.5, 1.0, 4/3, 1.5, 2.0, 8/3, 3.0, 4.0, 5.0, 6.0, 8.0, 12.0, 16.0]
    math_T = None
    for T in candidates:
        all_int = True
        for f in freqs_to_use:
            cycles = T * f / 4.0
            if abs(cycles - round(cycles)) > 0.02:
                all_int = False
                break
        if all_int:
            math_T = round(T, 5)
            break
    if math_T is None:
        math_T = 4.0

    # Never truncate manual non-math keyframes
    if max_non_math_t > math_T:
        return existing_len if existing_len > 0.05 else max_non_math_t

    is_loop = anim.get('loop') == 'loop' or anim.get('name', '').endswith(('_idle', '_walk', '_run', '_fly', '_swim', '_dive')) or anim.get('name', '') == 'sleep'

    if is_loop and existing_len > 0.05:
        # Check if existing_len is an integer multiple of math_T (e.g. 8s vs 2s)
        multiple = existing_len / math_T
        if abs(multiple - round(multiple)) < 0.02 and round(multiple) > 1:
            return math_T
        # If existing_len is smaller than math_T, never expand an existing defined length
        if math_T >= existing_len:
            return existing_len
        # Pure math with arbitrary existing length
        if max_non_math_t <= 0.01:
            return math_T

    return math_T if math_T else (existing_len if existing_len > 0.05 else 4.0)


def eval_keyframe_dp(kf, t):
    ch = kf.get('channel', '')
    def_val = 1.0 if ch == 'scale' else 0.0
    dps = kf.get('data_points', [{}])
    dp = dps[0] if dps else {}
    return {
        'x': eval_molang_val(dp.get('x', def_val), t, def_val),
        'y': eval_molang_val(dp.get('y', def_val), t, def_val),
        'z': eval_molang_val(dp.get('z', def_val), t, def_val)
    }


def eval_channel_at_time(keyframes, t):
    ch = keyframes[0].get('channel', '') if keyframes else ''
    def_val = 1.0 if ch == 'scale' else 0.0
    if not keyframes:
        return {'x': def_val, 'y': def_val, 'z': def_val}
    if len(keyframes) == 1:
        return eval_keyframe_dp(keyframes[0], t)

    kfs = sorted(keyframes, key=lambda k: k.get('time', 0))
    if t <= kfs[0].get('time', 0):
        return eval_keyframe_dp(kfs[0], t)
    if t >= kfs[-1].get('time', 0):
        return eval_keyframe_dp(kfs[-1], t)

    for i in range(len(kfs) - 1):
        t0 = kfs[i].get('time', 0)
        t1 = kfs[i+1].get('time', 0)
        if t0 <= t <= t1:
            if abs(t1 - t0) < 1e-6:
                return eval_keyframe_dp(kfs[i], t)
            alpha = (t - t0) / (t1 - t0)
            v0 = eval_keyframe_dp(kfs[i], t)
            v1 = eval_keyframe_dp(kfs[i+1], t)
            return {
                'x': (1 - alpha) * v0['x'] + alpha * v1['x'],
                'y': (1 - alpha) * v0['y'] + alpha * v1['y'],
                'z': (1 - alpha) * v0['z'] + alpha * v1['z']
            }
    return eval_keyframe_dp(kfs[-1], t)


INTERPOLATION_MAP = {
    "linear": "linear",
    "smooth": "catmullrom",
    "catmullrom": "catmullrom",
    "bézier": "bezier",
    "bezier": "bezier",
    "step": "step"
}


# idk if I'll keep this, didn't have as much of an effect as I expected
# Changes the precision of the keyframes, leaves 2 houses by default (e.g. 3.14159 -> 3.14)
COORD_PRECISION = 2

def clean_coord(val, precision=COORD_PRECISION):
    if val is None:
        return '0'
    try:
        f = float(val)
        if abs(f) < 1e-6:
            return '0'
        if precision is not None:
            f = round(f, precision)
        if f == int(f):
            return str(int(f))
        prec = precision if precision is not None else 4
        r = round(f, prec)
        if r == int(r):
            return str(int(r))
        s = f'{r:.{prec}f}'.rstrip('0').rstrip('.')
        return s if s and s != '-0' else '0'
    except (ValueError, TypeError):
        return str(val)


def dps_equal(dp1, dp2):
    if len(dp1) != len(dp2):
        return False
    for p1, p2 in zip(dp1, dp2):
        if not (isinstance(p1, dict) and isinstance(p2, dict)):
            if p1 != p2:
                return False
            continue
        all_keys = set(p1.keys()) | set(p2.keys())
        for k in all_keys:
            if k in ('x', 'y', 'z'):
                if clean_coord(p1.get(k, '0')) != clean_coord(p2.get(k, '0')):
                    return False
            else:
                if str(p1.get(k, '')).strip() != str(p2.get(k, '')).strip():
                    return False
    return True


def prune_consecutive_keyframes(kfs):
    if len(kfs) < 3:
        return kfs
    pruned = []
    n = len(kfs)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and dps_equal(kfs[i].get('data_points', []), kfs[j + 1].get('data_points', [])):
            j += 1
        run_len = j - i + 1
        if run_len >= 3:
            first_kf = kfs[i]
            if first_kf.get('interpolation') in ('catmullrom', 'smooth', 'bezier'):
                first_kf = copy.deepcopy(first_kf)
                first_kf['interpolation'] = 'linear'
            pruned.append(first_kf)
            last_kf = kfs[j]
            pruned.append(last_kf)
        else:
            for k in range(i, j + 1):
                pruned.append(kfs[k])
        i = j + 1
    return pruned


def bake_animation_math(anim, rate=6, interpolation="linear"):
    anim_name = anim.get("name", "")
    if anim_name.endswith(('_idle', '_walk', '_run', '_fly', '_swim', '_dive')) or anim_name == "sleep":
        anim["loop"] = "loop"

    animators = anim.get('animators', {})
    if isinstance(animators, dict):
        animator_list = list(animators.values())
    else:
        animator_list = animators or []

    has_math = False
    for a in animator_list:
        for kf in a.get('keyframes', []):
            if kf.get('channel') in ['rotation', 'position', 'scale']:
                for dp in kf.get('data_points', []):
                    for v in dp.values():
                        if has_math_expr(v):
                            has_math = True
                            break
            if has_math: break
        if has_math: break

    if not has_math:
        return False, 0, 0

    duration = calculate_loop_length(anim)
    try:
        fps = float(rate)
        if fps <= 0: fps = 6.0
    except (ValueError, TypeError):
        fps = 6.0

    interp_clean = str(interpolation).strip().lower()
    interp_val = INTERPOLATION_MAP.get(interp_clean, "linear")

    num_frames = int(round(duration * fps))
    if num_frames < 1:
        num_frames = 1

    sample_times = [round(i / fps, 5) for i in range(num_frames + 1)]
    sample_times[-1] = round(duration, 5)

    anim['length'] = round(duration, 5)
    is_loop = anim.get('loop') == 'loop'

    total_baked_kfs = 0
    total_baked_channels = 0

    for animator in animator_list:
        keyframes = animator.get('keyframes', [])
        channel_kfs = {'rotation': [], 'position': [], 'scale': [], 'other': []}
        for kf in keyframes:
            ch = kf.get('channel')
            if ch in channel_kfs:
                channel_kfs[ch].append(kf)
            else:
                channel_kfs['other'].append(kf)

        new_kfs = list(channel_kfs['other'])

        for ch in ['rotation', 'position', 'scale']:
            kfs = channel_kfs[ch]
            if not kfs:
                continue

            ch_has_math = any(has_math_expr(v) for kf in kfs for dp in kf.get('data_points', []) for v in dp.values())

            if ch_has_math:
                # Pre-clean math expressions on this channel's keyframes once before sampling
                for kf in kfs:
                    for dp in kf.get('data_points', []):
                        if isinstance(dp, dict):
                            for coord in ('x', 'y', 'z'):
                                v = dp.get(coord)
                                if isinstance(v, str) and has_math_expr(v):
                                    dp[coord] = fix_math_expr(v)

                baked_channel_kfs = []
                for st in sample_times:
                    val = eval_channel_at_time(kfs, st)
                    baked_channel_kfs.append({
                        'channel': ch,
                        'time': st,
                        'interpolation': interp_val,
                        'data_points': [{
                            'x': clean_coord(val['x']),
                            'y': clean_coord(val['y']),
                            'z': clean_coord(val['z'])
                        }],
                        'uuid': str(uuid.uuid4())
                    })

                # If looping animation, guarantee exact seam match between start and end
                if is_loop and len(baked_channel_kfs) > 1:
                    baked_channel_kfs[-1]['data_points'] = copy.deepcopy(baked_channel_kfs[0]['data_points'])

                # Prune consecutive identical keyframes (3+ in a row -> delete middle ones)
                baked_channel_kfs = prune_consecutive_keyframes(baked_channel_kfs)

                new_kfs.extend(baked_channel_kfs)
                total_baked_kfs += len(baked_channel_kfs)
                total_baked_channels += 1
            else:
                new_kfs.extend(kfs)

        animator['keyframes'] = sorted(new_kfs, key=lambda k: (k.get('time', 0), k.get('channel', '')))

    return True, total_baked_channels, total_baked_kfs


def bake_model_animations(model_data, rate=6, interpolation="linear"):
    animations = model_data.get('animations', [])
    report = []
    for anim in animations:
        changed, ch_count, kf_count = bake_animation_math(anim, rate=rate, interpolation=interpolation)
        if changed:
            report.append({
                'name': anim.get('name', 'unnamed'),
                'length': anim.get('length', 0),
                'channels': ch_count,
                'keyframes': kf_count
            })
    return report


def model_has_math_animations(model_data):
    if not isinstance(model_data, dict):
        return False
    animations = model_data.get('animations', [])
    if not isinstance(animations, list):
        return False
    for anim in animations:
        if not isinstance(anim, dict):
            continue
        animators = anim.get('animators', {})
        if isinstance(animators, dict):
            animator_list = list(animators.values())
        elif isinstance(animators, list):
            animator_list = animators
        else:
            animator_list = []
        for a in animator_list:
            if not isinstance(a, dict):
                continue
            for kf in a.get('keyframes', []):
                if not isinstance(kf, dict):
                    continue
                if kf.get('channel') in ['rotation', 'position', 'scale']:
                    for dp in kf.get('data_points', []):
                        if isinstance(dp, dict):
                            for v in dp.values():
                                if has_math_expr(v):
                                    return True
    return False


def file_has_math_animations(file_path):
    if not file_path or not os.path.exists(file_path):
        return False
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            model_data = json.load(f)
        return model_has_math_animations(model_data)
    except Exception:
        return False


def is_identity_coord(val, ch):
    try:
        f = float(val)
        exp = 1.0 if ch == 'scale' else 0.0
        return abs(f - exp) < 1e-4
    except (ValueError, TypeError):
        return False


def is_channel_identity(kfs, ch):
    if not kfs: return True
    for kf in kfs:
        for dp in kf.get('data_points', []):
            if not isinstance(dp, dict): return False
            for ax in ('x', 'y', 'z'):
                if not is_identity_coord(dp.get(ax, '0' if ch != 'scale' else '1'), ch):
                    return False
    return True


def optimize_model_data(model_data):
    total_kfs_pruned = 0
    empty_animators_pruned = 0
    channels_pruned = 0

    for anim in model_data.get('animations', []):
        animators = anim.get('animators', {})
        if isinstance(animators, dict):
            to_del = []
            for anim_id, animator in animators.items():
                kfs = animator.get('keyframes', [])
                if not kfs:
                    to_del.append(anim_id)
                    continue

                for kf in kfs:
                    if kf.get('color') == -1:
                        del kf['color']
                    if kf.get('uniform') is False:
                        del kf['uniform']
                    for dp in kf.get('data_points', []):
                        if isinstance(dp, dict):
                            for ax in ('x', 'y', 'z'):
                                if ax in dp:
                                    dp[ax] = clean_coord(dp[ax])

                by_channel = {}
                other = []
                for kf in kfs:
                    ch = kf.get('channel')
                    if ch:
                        by_channel.setdefault(ch, []).append(kf)
                    else:
                        other.append(kf)

                new_all = list(other)
                for ch, ch_kfs in by_channel.items():
                    ch_kfs.sort(key=lambda k: k.get('time', 0))
                    if ch in ('rotation', 'position', 'scale'):
                        pruned = prune_consecutive_keyframes(ch_kfs)
                        total_kfs_pruned += (len(ch_kfs) - len(pruned))

                        # Lossless identity channel pruning (channels that only equal rest pose)
                        if is_channel_identity(pruned, ch):
                            total_kfs_pruned += len(pruned)
                            channels_pruned += 1
                            continue

                        new_all.extend(pruned)
                    else:
                        new_all.extend(ch_kfs)

                new_all.sort(key=lambda k: (k.get('time', 0), k.get('channel', '')))
                animator['keyframes'] = new_all
                if not new_all:
                    to_del.append(anim_id)

            for anim_id in to_del:
                del animators[anim_id]
                empty_animators_pruned += 1

        elif isinstance(animators, list):
            new_list = []
            for animator in animators:
                kfs = animator.get('keyframes', [])
                if not kfs:
                    empty_animators_pruned += 1
                    continue

                for kf in kfs:
                    if kf.get('color') == -1:
                        del kf['color']
                    if kf.get('uniform') is False:
                        del kf['uniform']
                    for dp in kf.get('data_points', []):
                        if isinstance(dp, dict):
                            for ax in ('x', 'y', 'z'):
                                if ax in dp:
                                    dp[ax] = clean_coord(dp[ax])

                by_channel = {}
                other = []
                for kf in kfs:
                    ch = kf.get('channel')
                    if ch:
                        by_channel.setdefault(ch, []).append(kf)
                    else:
                        other.append(kf)

                new_all = list(other)
                for ch, ch_kfs in by_channel.items():
                    ch_kfs.sort(key=lambda k: k.get('time', 0))
                    if ch in ('rotation', 'position', 'scale'):
                        pruned = prune_consecutive_keyframes(ch_kfs)
                        total_kfs_pruned += (len(ch_kfs) - len(pruned))

                        # Lossless identity channel pruning
                        if is_channel_identity(pruned, ch):
                            total_kfs_pruned += len(pruned)
                            channels_pruned += 1
                            continue

                        new_all.extend(pruned)
                    else:
                        new_all.extend(ch_kfs)

                new_all.sort(key=lambda k: (k.get('time', 0), k.get('channel', '')))
                animator['keyframes'] = new_all
                if new_all:
                    new_list.append(animator)
                else:
                    empty_animators_pruned += 1
            anim['animators'] = new_list

    return total_kfs_pruned, empty_animators_pruned, channels_pruned


class Tooltip:
    def __init__(self, widget, text, delay_ms=500, allow_disabled=False):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.allow_disabled = allow_disabled
        self.tip_window = None
        self.after_id = None
        
        self.widget.bind("<Enter>", self.schedule_tip, add="+")
        self.widget.bind("<Leave>", self.hide_tip, add="+")
        self.widget.bind("<ButtonPress>", self.hide_tip, add="+")

        if self.allow_disabled:
            try:
                top = self.widget.winfo_toplevel()
                top.bind("<Motion>", self._on_global_motion, add="+")
                top.bind("<Leave>", self.hide_tip, add="+")
            except Exception:
                pass

    def _on_global_motion(self, event=None):
        if not self.text:
            self.hide_tip()
            return
        if not self.widget.winfo_exists():
            return
        try:
            if not self.widget.winfo_ismapped():
                self.hide_tip()
                return
            if str(self.widget.cget("state")).lower() == "disabled":
                x, y = event.x_root, event.y_root
                if self.widget.winfo_containing(x, y) == self.widget:
                    if not self.tip_window and not self.after_id:
                        self.schedule_tip()
                else:
                    self.hide_tip()
        except Exception:
            pass

    def schedule_tip(self, event=None):
        if not self.text:
            return
        self.cancel_scheduled()
        self.after_id = self.widget.after(self.delay_ms, self.show_tip)

    def cancel_scheduled(self):
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def show_tip(self):
        if self.tip_window or not self.text:
            return
        try:
            if not self.widget.winfo_exists():
                return
                
            x = self.widget.winfo_pointerx() + 10
            y = self.widget.winfo_pointery() + 15
            
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.attributes("-topmost", True)
            
            border_frame = tk.Frame(tw, bg="#767676", padx=1, pady=1)
            border_frame.pack()
            
            label = tk.Label(
                border_frame,
                text=self.text,
                justify=tk.LEFT,
                bg="#fbfbfb",
                fg="#1f1f1f",
                relief=tk.FLAT,
                padx=7,
                pady=4,
                font=("Segoe UI", 9),
                wraplength=270
            )
            label.pack()
            
            tw.update_idletasks()
            w = tw.winfo_reqwidth()
            h = tw.winfo_reqheight()
            sw = tw.winfo_screenwidth()
            sh = tw.winfo_screenheight()
            if x + w > sw - 8:
                x = sw - w - 8
            if y + h > sh - 8:
                y = self.widget.winfo_pointery() - h - 6
            tw.wm_geometry(f"+{x}+{y}")
        except Exception:
            pass

    def hide_tip(self, event=None):
        self.cancel_scheduled()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


class AvatarBuilderApp:
    def __init__(self, root, base_path=None):
        self.root = root
        self.root.title("Cobblemon Avatar Setup")
        self.root.config(padx=20, pady=10)
        self.root.minsize(400, 380)
        
        # cute little icon
        if base_path:
            self.base_path = os.path.abspath(base_path)
            self.icon_path = os.path.join(self.base_path, "icon.ico")
        elif getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
            self.icon_path = os.path.join(sys._MEIPASS, "icon.ico")
        else:
            self.base_path = os.path.dirname(os.path.realpath(__file__))
            self.icon_path = os.path.join(self.base_path, "icon.ico")
            
        # linux/macos users hate cute little icons
        if sys.platform == 'win32' and os.path.exists(self.icon_path):
            self.root.iconbitmap(default=self.icon_path)
            
        # Avatar metadata
        self.avatar_name_var = tk.StringVar(value="")
        self.icon_color_var = tk.StringVar(value="#ffffff")
        self.player_icon_var = tk.StringVar(value="")

        # Default values for advanced settings
        self.scale_var = tk.StringVar(value="1")
        self.camheight_var = tk.StringVar(value="1")
        self.nameplatepivot_var = tk.StringVar(value="1")
        self.pdollscale_var = tk.StringVar(value="1")
        self.speedscale_var = tk.BooleanVar(value=False)
        self.movespeed_var = tk.StringVar(value="0.35")
        self.customcry_var = tk.BooleanVar(value=False)
        self.cryfile_var = tk.StringVar(value="")
        self.crosshair_var = tk.BooleanVar(value=True)
        self.extra_anims_var = tk.BooleanVar(value=False)
        self.bake_math_var = tk.BooleanVar(value=False)
        self.bake_rate_var = tk.StringVar(value="6")
        self.bake_interp_var = tk.StringVar(value="Linear")
        self.anim_textures_data = []
        self.quirks_data = []
        self.status_timer = None

        # Modular Fixes Variables
        self.fixes_vars = {
            "bake_math": self.bake_math_var,
            "fix_math_expr": tk.BooleanVar(value=True),
            "sound_instruction_keyframes": tk.BooleanVar(value=True),
            "auto_loop_anims": tk.BooleanVar(value=True),
            "strip_anim_prefix": tk.BooleanVar(value=True),
            "convert_generic": tk.BooleanVar(value=True),
            "reserved_names": tk.BooleanVar(value=True),
            "mesh_conflicts": tk.BooleanVar(value=True),
            "prune_empty": tk.BooleanVar(value=True),
            "base_texture_mapping": tk.BooleanVar(value=True),
            "clean_dedup_textures": tk.BooleanVar(value=True),
            "emissive_name": tk.BooleanVar(value=True),
        }
        
        # Checking if there's a valid avatar
        def is_valid_avatar_dir(path):
            return os.path.exists(os.path.join(path, "avatar.json")) and os.path.exists(os.path.join(path, "config.lua"))

        if not is_valid_avatar_dir(self.base_path):
            messagebox.showinfo("Select Folder", "No valid avatar found in the current folder.\n\nPlease select your avatar folder.")
            selected_dir = filedialog.askdirectory(title="Select Avatar Folder")
            if not selected_dir:
                self.root.destroy()
                return
            self.base_path = selected_dir
            if not is_valid_avatar_dir(self.base_path):
                messagebox.showerror("Error", "The selected folder does not contain an avatar.json and config.lua. Closing.")
                self.root.destroy()
                return
            
        self.setup_ui()
        self.load_posers()
        self.refresh_models()
        
    def setup_ui(self):
        main_input_frame = tk.Frame(self.root)
        main_input_frame.pack(pady=(15, 5))
        
        # Model Selection
        lbl_model = tk.Label(main_input_frame, text="Select .bbmodel:")
        lbl_model.grid(row=0, column=0, columnspan=2, pady=(0, 2))
        
        self.model_var = tk.StringVar()
        self.model_cb = ttk.Combobox(main_input_frame, textvariable=self.model_var, state="readonly", width=30)
        self.model_cb.grid(row=1, column=0, sticky="w", padx=(0, 5))
        self.model_cb.bind("<<ComboboxSelected>>", self.on_model_select)
        btn_refresh = tk.Button(main_input_frame, text="Refresh", command=self.refresh_models, width=8)
        btn_refresh.grid(row=1, column=1)

        tip_model = "Select the main .bbmodel containing your Pokémon's 3D model and animations."
        Tooltip(lbl_model, tip_model)
        
        # Name Field
        lbl_name = tk.Label(main_input_frame, text="Name:")
        lbl_name.grid(row=2, column=0, columnspan=2, pady=(8, 2))
        self.name_entry = tk.Entry(main_input_frame, textvariable=self.avatar_name_var, width=33, font=("Segoe UI", 9))
        self.name_entry.grid(row=3, column=0, columnspan=2, sticky="ew")

        tip_name = "The display name of your avatar in the Figura wardrobe menu."
        Tooltip(lbl_name, tip_name)

        # Description Field
        lbl_desc = tk.Label(main_input_frame, text="Description:")
        lbl_desc.grid(row=4, column=0, columnspan=2, pady=(8, 2))
        self.desc_text = tk.Text(main_input_frame, width=33, height=2, wrap=tk.WORD, font=("Segoe UI", 9))
        self.desc_text.grid(row=5, column=0, columnspan=2, sticky="ew")
        self.desc_text.bind("<KeyRelease>", self.on_desc_modified)
        self.desc_text.bind("<<Modified>>", self.on_desc_modified)

        tip_desc = "The description shown for your avatar in the Figura wardrobe menu."
        Tooltip(lbl_desc, tip_desc)

        # Poser Selection
        lbl_poser = tk.Label(main_input_frame, text="Select Poser:")
        lbl_poser.grid(row=6, column=0, columnspan=2, pady=(8, 2))
        
        self.poser_var = tk.StringVar()
        self.poser_cb = ttk.Combobox(main_input_frame, textvariable=self.poser_var, state="readonly", width=30)
        self.poser_cb.grid(row=7, column=0, sticky="w", padx=(0, 5))
        btn_poser_auto = tk.Button(main_input_frame, text="Auto", command=self.auto_detect_poser, width=8)
        btn_poser_auto.grid(row=7, column=1)

        tip_poser = "Determines which animation poser script to use based on the current animation set."
        Tooltip(lbl_poser, tip_poser)
        
        # Head Path
        lbl_head = tk.Label(main_input_frame, text="Head Group Path:")
        lbl_head.grid(row=8, column=0, columnspan=2, pady=(8, 2))
        
        head_inner_frame = tk.Frame(main_input_frame)
        head_inner_frame.grid(row=9, column=0, sticky="w", padx=(0, 5))
        
        self.head_prefix_var = tk.StringVar()
        tk.Label(head_inner_frame, textvariable=self.head_prefix_var, fg="gray").pack(side=tk.LEFT)
        self.head_var = tk.StringVar()
        head_entry = tk.Entry(head_inner_frame, textvariable=self.head_var, width=18)
        head_entry.pack(side=tk.LEFT)
        
        btn_head_auto = tk.Button(main_input_frame, text="Auto", command=self.auto_find_head_path, width=8)
        btn_head_auto.grid(row=9, column=1)

        tip_head = "Path to the head bone/group in the model, allowing head tracking to look where the player looks."
        Tooltip(lbl_head, tip_head)
        
        # Advanced Settings Button
        self.adv_toggle_btn = tk.Button(self.root, text="Advanced Settings ▼", command=self.toggle_advanced_settings)
        self.adv_toggle_btn.pack(pady=(15, 5))
        
        self.adv_frame = tk.Frame(self.root)

        # Scale
        lbl_scale = tk.Label(self.adv_frame, text="Pokémon Scale:")
        lbl_scale.grid(row=0, column=0, sticky="e", pady=2)
        entry_scale = tk.Entry(self.adv_frame, textvariable=self.scale_var, width=10)
        entry_scale.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        tip_scale = "Changes the scale of the model in-game."
        Tooltip(lbl_scale, tip_scale)

        # Camera Height
        lbl_cam = tk.Label(self.adv_frame, text="Camera Height:")
        lbl_cam.grid(row=1, column=0, sticky="e", pady=2)
        entry_cam = tk.Entry(self.adv_frame, textvariable=self.camheight_var, width=10)
        entry_cam.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        tip_cam = "Adjusts first-person and third-person camera eye height to match your model's height."
        Tooltip(lbl_cam, tip_cam)

        # Nameplate Pivot
        lbl_np = tk.Label(self.adv_frame, text="Nameplate Pivot:")
        lbl_np.grid(row=2, column=0, sticky="e", pady=2)
        entry_np = tk.Entry(self.adv_frame, textvariable=self.nameplatepivot_var, width=10)
        entry_np.grid(row=2, column=1, sticky="w", padx=5, pady=2)
        tip_np = "Vertical height offset for the player nameplate above your model."
        Tooltip(lbl_np, tip_np)

        # Paperdoll Scale
        lbl_pdoll = tk.Label(self.adv_frame, text="Paperdoll Scale:")
        lbl_pdoll.grid(row=3, column=0, sticky="e", pady=2)
        entry_pdoll = tk.Entry(self.adv_frame, textvariable=self.pdollscale_var, width=10)
        entry_pdoll.grid(row=3, column=1, sticky="w", padx=5, pady=2)
        tip_pdoll = "Changes the scale of your avatar in the inventory menu and the Figura paperdoll feature."
        Tooltip(lbl_pdoll, tip_pdoll)

        # Player Icon
        self.player_icon_label = tk.Label(self.adv_frame, text="Player Icon:")
        self.player_icon_label.grid(row=4, column=0, sticky="e", pady=2)
        self.player_icon_btn = tk.Button(self.adv_frame, text="Browse...", command=self.browse_player_icon)
        self.player_icon_btn.grid(row=4, column=1, sticky="w", padx=5, pady=2)
        tip_icon = "Select a custom image (.png, .jpg, etc.) to display as your avatar icon in the Figura menu and player list (TAB). Automatically squared and optimized."
        Tooltip(self.player_icon_label, tip_icon)

        # Figura Icon Color
        lbl_color = tk.Label(self.adv_frame, text="Figura Icon Color:")
        lbl_color.grid(row=5, column=0, sticky="e", pady=2)
        color_frame = tk.Frame(self.adv_frame)
        color_frame.grid(row=5, column=1, sticky="w", padx=5, pady=2)
        self.color_entry = tk.Entry(color_frame, textvariable=self.icon_color_var, width=9)
        self.color_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.color_entry.bind("<KeyRelease>", self.on_color_text_change)
        self.color_preview_btn = tk.Button(
            color_frame,
            text="       ",
            relief=tk.RAISED,
            bg=self.icon_color_var.get(),
            activebackground=self.icon_color_var.get(),
            command=self.pick_icon_color,
            cursor="hand2"
        )
        self.color_preview_btn.pack(side=tk.LEFT)
        tip_col = "Changes the color of the Figura triangle next to your name and the color of the text in the Figura menu while your avatar is selected."
        Tooltip(lbl_color, tip_col)

        # Speed Scale
        lbl_speedscale = tk.Label(self.adv_frame, text="Speed Scale:")
        lbl_speedscale.grid(row=6, column=0, sticky="e", pady=2)
        speed_frame = tk.Frame(self.adv_frame)
        speed_frame.grid(row=6, column=1, sticky="w", padx=5, pady=2)
        chk_speed = tk.Checkbutton(speed_frame, variable=self.speedscale_var, command=lambda: toggle_speed())
        chk_speed.pack(side=tk.LEFT)
        speed_opt = tk.Frame(speed_frame)
        lbl_spd_val = tk.Label(speed_opt, text="Speed:")
        lbl_spd_val.pack(side=tk.LEFT, padx=(5, 2))
        entry_spd_val = tk.Entry(speed_opt, textvariable=self.movespeed_var, width=6)
        entry_spd_val.pack(side=tk.LEFT)
        
        tip_spdscale = "Scales walk/run animation speed based on your Pokémon's movement speed."
        Tooltip(lbl_speedscale, tip_spdscale)

        def toggle_speed():
            if self.speedscale_var.get():
                speed_opt.pack(side=tk.LEFT)
            else:
                speed_opt.pack_forget()
        self.toggle_speed_fn = toggle_speed
        toggle_speed()

        # Custom Cry
        lbl_cry = tk.Label(self.adv_frame, text="Custom Cry:")
        lbl_cry.grid(row=7, column=0, sticky="e", pady=2)
        cry_frame = tk.Frame(self.adv_frame)
        cry_frame.grid(row=7, column=1, sticky="w", padx=5, pady=2)
        chk_cry = tk.Checkbutton(cry_frame, variable=self.customcry_var, command=lambda: toggle_cry())
        chk_cry.pack(side=tk.LEFT)
        cry_opt = tk.Frame(cry_frame)
        cry_btn = tk.Button(cry_opt, text="Browse...", command=lambda: select_cry())
        cry_btn.pack(side=tk.LEFT, padx=(5, 2))

        tip_cry = "Enable a custom sound effect (.ogg) when your avatar plays its cry animation."
        Tooltip(lbl_cry, tip_cry)

        def select_cry():
            filepath = filedialog.askopenfilename(parent=self.root, filetypes=[("OGG Audio Files", "*.ogg")])
            if filepath:
                self.cryfile_var.set(filepath)
                self.show_status(f"Custom cry selected ({os.path.basename(filepath)})!", "green")
        
        def toggle_cry():
            if self.customcry_var.get():
                cry_opt.pack(side=tk.LEFT)
            else:
                cry_opt.pack_forget()
        self.toggle_cry_fn = toggle_cry
        self.cry_btn = cry_btn
        toggle_cry()

        # Extra Animations
        lbl_extra = tk.Label(self.adv_frame, text="Extra Animations:")
        lbl_extra.grid(row=8, column=0, sticky="e", pady=2)
        chk_extra = tk.Checkbutton(self.adv_frame, variable=self.extra_anims_var)
        chk_extra.grid(row=8, column=1, sticky="w", padx=5, pady=2)
        tip_extra = "Enables the 'Extras' poser, which adds the 'riding', 'ground_idle_sneak' and 'ground_walk_sneak' animations."
        Tooltip(lbl_extra, tip_extra)

        # Action Buttons
        btn_fixes = tk.Button(self.adv_frame, text="Fixes...", command=self.open_fixes_dialog, width=28)
        btn_fixes.grid(row=9, column=0, columnspan=2, pady=(8, 2))

        btn_anim_tex = tk.Button(self.adv_frame, text="Animated Textures...", command=self.open_animated_textures_dialog, width=28)
        btn_anim_tex.grid(row=10, column=0, columnspan=2, pady=(2, 2))
        self.btn_anim_tex = btn_anim_tex
        self.anim_tex_tooltip = Tooltip(self.btn_anim_tex, "", allow_disabled=True)

        btn_quirks = tk.Button(self.adv_frame, text="Quirks...", command=self.open_quirks_dialog, width=28)
        btn_quirks.grid(row=11, column=0, columnspan=2, pady=(2, 5))

        self.adv_frame.grid_columnconfigure(0, minsize=150)
        self.adv_frame.grid_columnconfigure(1, minsize=190)
        self.adv_expanded = False
        
        # Run Button
        self.run_btn = tk.Button(self.root, text="Run Setup", command=self.run_setup, width=15)
        self.run_btn.pack(pady=(20, 5))
        
        # Status Label
        self.status_label = tk.Label(self.root, text="", fg="green", wraplength=300)
        self.status_label.pack(pady=(0, 5))

        # Footer
        footer_text = "Based on the work of kcin2001\nMade with ♥ by Granbull"
        tk.Label(self.root, text=footer_text, fg="grey", font=("Segoe UI", 8)).pack(side=tk.BOTTOM, pady=(0, 5))

        self.update_portrait_ui_state()
        self.update_animated_textures_ui_state()
        self.update_window_minsize()

    def update_window_minsize(self):
        desc_h = int(self.desc_text.cget("height")) if hasattr(self, 'desc_text') else 2
        extra_h = max(0, (desc_h - 2) * 18)
        if getattr(self, 'adv_expanded', False):
            self.root.minsize(420, 620 + extra_h)
        else:
            self.root.minsize(420, 440 + extra_h)

    def on_desc_modified(self, event=None):
        if not hasattr(self, 'desc_text'):
            return
        if self.desc_text.edit_modified():
            self.desc_text.edit_modified(False)
        content = self.desc_text.get("1.0", tk.END).rstrip("\r\n")
        lines = content.count("\n") + 1
        new_height = max(2, min(lines, 8))
        curr_height = int(self.desc_text.cget("height"))
        if new_height != curr_height:
            self.desc_text.config(height=new_height)
            self.update_window_minsize()

    def find_all_portrait_bbmodels(self):
        found = []
        for sub in ("Extra", "extra"):
            extra_dir = os.path.join(self.base_path, sub)
            if os.path.isdir(extra_dir):
                for f in os.listdir(extra_dir):
                    if f.lower() == "portrait.bbmodel":
                        p = os.path.join(extra_dir, f)
                        if p not in found:
                            found.append(p)
        if os.path.isdir(self.base_path):
            for f in os.listdir(self.base_path):
                if f.lower() == "portrait.bbmodel":
                    p = os.path.join(self.base_path, f)
                    if p not in found:
                        found.append(p)
        return found

    def find_portrait_bbmodel(self):
        models = self.find_all_portrait_bbmodels()
        return models[0] if models else None

    def get_portrait_target_path(self):
        existing = self.find_portrait_bbmodel()
        if existing:
            return existing
        dest_dir = self.base_path
        for sub in ("Extra", "extra"):
            extra_dir = os.path.join(self.base_path, sub)
            if os.path.isdir(extra_dir):
                dest_dir = extra_dir
                break
        return os.path.join(dest_dir, "PORTRAIT.bbmodel")

    def update_portrait_ui_state(self):
        if hasattr(self, 'player_icon_label'):
            self.player_icon_label.config(state="normal")
        if hasattr(self, 'player_icon_btn'):
            self.player_icon_btn.config(state="normal")

    def update_animated_textures_ui_state(self):
        config_path = os.path.join(self.base_path, "config.lua") if getattr(self, "base_path", None) else ""
        has_animated_parts = False
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Check for "animatedParts" (not animatedPart)
                if re.search(r'\banimatedParts\b', content):
                    has_animated_parts = True
            except Exception:
                pass

        if hasattr(self, 'btn_anim_tex'):
            if has_animated_parts:
                self.btn_anim_tex.config(state="normal")
                if hasattr(self, 'anim_tex_tooltip'):
                    self.anim_tex_tooltip.text = ""
                    self.anim_tex_tooltip.hide_tip()
            else:
                self.btn_anim_tex.config(state="disabled")
                if hasattr(self, 'anim_tex_tooltip'):
                    self.anim_tex_tooltip.text = "This feature is not compatible with the old kcin2001 template."

    def create_portrait_model_data(self, avatar_png_path, portrait_path, width, height):
        portrait_dir = os.path.dirname(portrait_path)
        rel_path = os.path.relpath(avatar_png_path, portrait_dir).replace("\\", "/")

        cube_uuid = "bf32508f-56de-e263-31f1-f208d8c9f3fd"
        group_uuid = "3b48086b-35d8-3bf3-36df-d587fb492ae4"
        tex_uuid = "51567ef7-2ebd-9c75-e86e-c49e3c4b3b6c"

        return {
            "meta": {"format_version": "5.0", "model_format": "free", "box_uv": False},
            "name": "PORTRAIT",
            "model_identifier": "PORTRAIT",
            "visible_box": [1, 1, 0],
            "resolution": {"width": 16, "height": 16},
            "elements": [
                {
                    "name": "image",
                    "box_uv": False,
                    "from": [-4, 0, -1],
                    "to": [4, 8, 0],
                    "origin": [0, 0, 0],
                    "faces": {
                        "north": {"uv": [0, 0, width, height], "texture": 0},
                        "east": {"uv": [0, 0, 0, 0], "texture": None},
                        "south": {"uv": [0, 0, 0, 0], "texture": None},
                        "west": {"uv": [0, 0, 0, 0], "texture": None},
                        "up": {"uv": [0, 0, 0, 0], "texture": None},
                        "down": {"uv": [0, 0, 0, 0], "texture": None}
                    },
                    "type": "cube",
                    "uuid": cube_uuid
                }
            ],
            "groups": [
                {
                    "name": "PORTRAIT",
                    "origin": [0, 0, 0],
                    "rotation": [0, 0, 0],
                    "color": 0,
                    "uuid": group_uuid,
                    "export": True,
                    "isOpen": True,
                    "visibility": True
                }
            ],
            "outliner": [
                {
                    "uuid": group_uuid,
                    "isOpen": True,
                    "children": [cube_uuid]
                }
            ],
            "textures": [
                {
                    "name": "avatar.png",
                    "relative_path": rel_path,
                    "id": "0",
                    "width": width,
                    "height": height,
                    "uv_width": width,
                    "uv_height": height,
                    "particle": False,
                    "render_mode": "default",
                    "visible": True,
                    "internal": True,
                    "saved": True,
                    "uuid": tex_uuid,
                    "source": ""
                }
            ]
        }

    def apply_player_icon_to_portrait(self, portrait_path, avatar_png_path, width, height):
        if not os.path.exists(portrait_path):
            portrait_data = self.create_portrait_model_data(avatar_png_path, portrait_path, width, height)
        else:
            try:
                with open(portrait_path, "r", encoding="utf-8") as f:
                    portrait_data = json.load(f)
            except Exception:
                portrait_data = self.create_portrait_model_data(avatar_png_path, portrait_path, width, height)

            portrait_dir = os.path.dirname(portrait_path)
            rel_path = os.path.relpath(avatar_png_path, portrait_dir).replace("\\", "/")

            existing_textures = portrait_data.get("textures", [])
            if existing_textures and isinstance(existing_textures, list) and isinstance(existing_textures[0], dict):
                tex = existing_textures[0]
            else:
                tex = {}

            tex["name"] = "avatar.png"
            tex["relative_path"] = rel_path
            tex["folder"] = ""
            tex["namespace"] = ""
            tex["id"] = "0"
            tex["width"] = width
            tex["height"] = height
            tex["uv_width"] = width
            tex["uv_height"] = height
            tex["source"] = ""
            if "uuid" not in tex:
                tex["uuid"] = "51567ef7-2ebd-9c75-e86e-c49e3c4b3b6c"

            # Overwrite textures array so multiple copies don't accumulate
            portrait_data["textures"] = [tex]

            # Update north face of the "image" cube
            elements = portrait_data.get("elements", [])
            target_cube = None
            for el in elements:
                if isinstance(el, dict) and el.get("name") == "image":
                    target_cube = el
                    break
            if not target_cube and elements and isinstance(elements[0], dict):
                target_cube = elements[0]

            if target_cube:
                faces = target_cube.setdefault("faces", {})
                north = faces.setdefault("north", {})
                north["uv"] = [0, 0, width, height]
                north["texture"] = 0

        os.makedirs(os.path.dirname(portrait_path), exist_ok=True)
        with open(portrait_path, "w", encoding="utf-8") as f:
            json.dump(portrait_data, f, separators=(',', ':'), ensure_ascii=False)

    def process_and_save_player_icon(self, selected_path, target_png_path):
        # Try PIL/Pillow
        try:
            import importlib
            pil_image = importlib.import_module("PIL.Image")
            with pil_image.open(selected_path) as img:
                img = img.convert("RGBA")
                orig_w, orig_h = img.size
                max_side = max(orig_w, orig_h)
                
                # Fit centered onto a transparent square canvas if non-square
                if orig_w != orig_h:
                    square_img = pil_image.new("RGBA", (max_side, max_side), (0, 0, 0, 0))
                    offset = ((max_side - orig_w) // 2, (max_side - orig_h) // 2)
                    square_img.paste(img, offset)
                else:
                    square_img = img

                # Downscale to 128x128 only if it exceeds 128
                if max_side > 128:
                    resample = getattr(pil_image, "Resampling", pil_image).LANCZOS
                    square_img = square_img.resize((128, 128), resample)
                    final_size = 128
                else:
                    final_size = max_side

                square_img.save(target_png_path, format="PNG", optimize=True)
                return final_size, final_size
        except Exception:
            pass

        # Tkinter PhotoImage fallback
        try:
            tk_src = tk.PhotoImage(file=selected_path, master=self.root)
            orig_w = tk_src.width()
            orig_h = tk_src.height()
            max_side = max(orig_w, orig_h)

            if orig_w != orig_h:
                tk_square = tk.PhotoImage(width=max_side, height=max_side, master=self.root)
                offset_x = (max_side - orig_w) // 2
                offset_y = (max_side - orig_h) // 2
                tk_square.tk.call(tk_square, "copy", tk_src, "-to", offset_x, offset_y)
            else:
                tk_square = tk_src

            if max_side > 128:
                ratio = max(1, round(max_side / 128))
                tk_down = tk_square.subsample(ratio, ratio)
                final_size = tk_down.width()
                tk_down.write(target_png_path, format="png")
            else:
                final_size = max_side
                tk_square.write(target_png_path, format="png")

            return final_size, final_size
        except Exception:
            pass

        # Direct copy fallback
        shutil.copy2(selected_path, target_png_path)
        try:
            with open(target_png_path, "rb") as f:
                hdr = f.read(32)
            if hdr.startswith(b'\x89PNG\r\n\x1a\n'):
                pw, ph = struct.unpack(">II", hdr[16:24])
                return pw, ph
        except Exception:
            pass
        return 128, 128

    def browse_player_icon(self):
        filetypes = [
            ("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.webp"),
            ("PNG Images", "*.png"),
            ("All Files", "*.*")
        ]
        selected_path = filedialog.askopenfilename(
            parent=self.root,
            title="Select Player Icon Image",
            filetypes=filetypes
        )
        if not selected_path:
            return

        avatar_png_path = os.path.join(self.base_path, "avatar.png")
        try:
            img_width, img_height = self.process_and_save_player_icon(selected_path, avatar_png_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save avatar.png:\n{str(e)}", parent=self.root)
            return

        portrait_paths = self.find_all_portrait_bbmodels()
        if not portrait_paths:
            portrait_paths = [self.get_portrait_target_path()]

        try:
            for p in portrait_paths:
                self.apply_player_icon_to_portrait(p, avatar_png_path, img_width, img_height)
            self.player_icon_var.set("avatar.png")
            self.show_status(f"Player icon updated ({img_width}x{img_height})!", "green")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save PORTRAIT.bbmodel:\n{str(e)}", parent=self.root)

    def pick_icon_color(self):
        curr = self.icon_color_var.get().strip()
        if not curr.startswith("#"):
            curr = "#ffffff"
        chosen = colorchooser.askcolor(color=curr, parent=self.root, title="Select Icon Color")
        if chosen and chosen[1]:
            hex_col = chosen[1]
            self.icon_color_var.set(hex_col)
            self.update_color_preview(hex_col)

    def on_color_text_change(self, event=None):
        val = self.icon_color_var.get().strip()
        if not val.startswith("#"):
            val = "#" + val
        if re.match(r'^#[0-9a-fA-F]{6}$', val) or re.match(r'^#[0-9a-fA-F]{3}$', val):
            self.update_color_preview(val)

    def update_color_preview(self, hex_col):
        try:
            self.color_preview_btn.config(bg=hex_col, activebackground=hex_col)
        except Exception:
            pass

    def set_all_fixes(self, val):
        for k, v in self.fixes_vars.items():
            v.set(val)

    def open_fixes_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Configure Model Fixes")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text="Select which fixes and optimizations to apply:", font=("Segoe UI", 9, "bold")).pack(pady=(10, 5), padx=15, anchor="w")

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 6))
        btn_sel_all = tk.Button(btn_frame, text="Select All", width=12, command=lambda: self.set_all_fixes(True))
        btn_sel_all.pack(side=tk.LEFT, padx=(0, 5))
        btn_desel_all = tk.Button(btn_frame, text="Deselect All", width=12, command=lambda: self.set_all_fixes(False))
        btn_desel_all.pack(side=tk.LEFT)

        content_frame = tk.Frame(dlg, padx=15, pady=5)
        content_frame.pack(fill=tk.BOTH, expand=True)

        fix_groups = [
            ("Math & Animation Fixes", [
                ("bake_math", "Bake Math Animations", "Solves math curves and bakes them into numeric keyframes. Fixes the 'Script overran resource limits!' error on 'Default' and 'High' permissions, but adds a few kb to the avatar."),
                ("fix_math_expr", "Fix Math Syntax Errors", "Resolves operators, missing operands (e.g. *-10), NaN values, and more. Fixes many 'syntax error' keyframes."),
                ("sound_instruction_keyframes", "Fix Sound & Instruction Keyframes", "Converts Bedrock sound effect channels and translates Molang instruction scripts into valid Figura Lua KeySound calls. Fixes crashes when using models with sound effects, like flying Pokémon's wing flaps."),
                ("auto_loop_anims", "Auto-Loop Standard Animations", "Sets standard animation cycles (idle, walk, run, fly, swim, sleep) to loop continuously. Fixes some t-posing problems."),
                ("strip_anim_prefix", "Strip Animation Prefixes", "Removes prefixes (e.g. 'animation.pokemon.') from animation names. Fixes some t-posing problems."),
            ]),
            ("Model & Structure Fixes", [
                ("convert_generic", "Convert to Generic Model", "Converts the model format to Generic."),
                ("reserved_names", "Sanitize Reserved Group Names", "Lowercases reserved group names (Head, Body, LeftArm, etc.). Fixes certain invisible body parts or parts following vanilla movement."),
                ("mesh_conflicts", "Resolve Mesh Name Collisions", "Renames cubes/meshes that share the exact same name as their parent group. Fixes certain cases of animation/script target ambiguity."),
                ("prune_empty", "Optimize Model Structure", "Prunes redundant keyframes, zero-valued identity channels and empty bone animators. Slightly reduces file size."),
            ]),
            ("Texture Fixes", [
                ("base_texture_mapping", "Fix Base Texture & Face Mapping", "Sorts the base texture to slot 0 and standardizes cube faces to use it. Fixes accidental shiny or texture-swapped faces."),
                ("clean_dedup_textures", "Clean & Deduplicate Textures", "Synchronizes UV dimensions with texture resolution to fix stretching, and merges duplicate texture slots. Fixes wrong UVs after Bedrock -> Generic conversion."),
                ("emissive_name", "Normalize Emissive Names", "Renames '_emissive.png' to '_e.png' to conform to Figura's naming standard."),
            ])
        ]

        trace_id = None
        for cat_title, items in fix_groups:
            lf = tk.LabelFrame(content_frame, text=cat_title, font=("Segoe UI", 9, "bold"), padx=10, pady=5)
            lf.pack(fill=tk.X, pady=4)
            for var_key, label_text, tip_text in items:
                var = self.fixes_vars[var_key]
                if var_key == "bake_math":
                    bake_cb = tk.Checkbutton(lf, text=label_text, variable=var, anchor="w", command=lambda: update_bake_opt_ui())
                    bake_cb.pack(fill=tk.X, pady=1)
                    Tooltip(bake_cb, tip_text)

                    bake_opt_frame = tk.Frame(lf)
                    lbl_rate = tk.Label(bake_opt_frame, text="Rate:")
                    lbl_rate.pack(side=tk.LEFT, padx=(0, 2))
                    entry_rate = tk.Entry(bake_opt_frame, textvariable=self.bake_rate_var, width=3)
                    entry_rate.pack(side=tk.LEFT, padx=(0, 8))
                    tip_rate = "Sample rate in keyframes per second. Higher rates make complex curves smoother at the cost of file size."
                    Tooltip(lbl_rate, tip_rate)

                    lbl_interp = tk.Label(bake_opt_frame, text="Interp:")
                    lbl_interp.pack(side=tk.LEFT, padx=(0, 2))
                    cb_interp = ttk.Combobox(
                        bake_opt_frame,
                        textvariable=self.bake_interp_var,
                        values=["Linear", "Smooth", "Bézier", "Step"],
                        state="readonly",
                        width=7
                    )
                    cb_interp.pack(side=tk.LEFT)
                    tip_interp = "Keyframe curve interpolation mode (Linear, Smooth, Bézier, Step). Linear is recommended."
                    Tooltip(lbl_interp, tip_interp)

                    def update_bake_opt_ui(*args):
                        try:
                            if not dlg.winfo_exists():
                                return
                            if self.bake_math_var.get():
                                bake_opt_frame.pack(after=bake_cb, anchor="w", padx=(20, 0), pady=(0, 3))
                            else:
                                bake_opt_frame.pack_forget()
                        except Exception as e:
                            print(f"Error in update_bake_opt_ui: {e}")

                    update_bake_opt_ui()
                    trace_id = self.bake_math_var.trace_add("write", update_bake_opt_ui)
                else:
                    cb = tk.Checkbutton(lf, text=label_text, variable=var, anchor="w")
                    cb.pack(fill=tk.X, pady=1)
                    Tooltip(cb, tip_text)

        def on_dialog_close():
            if trace_id:
                try:
                    self.bake_math_var.trace_remove("write", trace_id)
                except Exception:
                    pass
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", on_dialog_close)
        btn_done = tk.Button(dlg, text="Done", width=12, command=on_dialog_close)
        btn_done.pack(pady=(8, 12))

    def toggle_advanced_settings(self):
        if self.adv_expanded:
            self.adv_frame.pack_forget()
            self.adv_toggle_btn.config(text="Advanced Settings ▼")
            self.adv_expanded = False
            self.update_window_minsize()
        else:
            self.adv_frame.pack(before=self.run_btn, pady=5)
            self.adv_toggle_btn.config(text="Advanced Settings ▲")
            self.adv_expanded = True
            self.update_window_minsize()
        
    def show_status(self, text, color="green"):
        self.status_label.config(text=text, fg=color)
        if self.status_timer:
            self.root.after_cancel(self.status_timer)
        if text:
            timeout = 5000 if color == "red" else 3000
            self.status_timer = self.root.after(timeout, lambda: self.status_label.config(text=""))

    def refresh_models(self):
        models = [f for f in os.listdir(self.base_path) if f.endswith(".bbmodel") and f.lower() != "portrait.bbmodel"]
        self.model_cb['values'] = models
        if models:
            self.model_cb.current(0)
            self.on_model_select()
        else:
            self.model_cb.set('')
            self.on_model_select()
            self.show_status("Place a .bbmodel file in this folder and click Refresh.", "red")
        self.update_portrait_ui_state()

    def on_model_select(self, event=None):
        model_file = self.model_var.get()
        if model_file:
            modelname = model_file.rsplit(".bbmodel", 1)[0]
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', modelname):
                self.head_prefix_var.set(f"models.{modelname}.")
            else:
                escaped_modelname = modelname.replace("'", "\\'")
                self.head_prefix_var.set(f"models['{escaped_modelname}'].")
        else:
            self.head_prefix_var.set("models.")
        self.load_avatar_config()

    def load_avatar_config(self):
        avatar_path = os.path.join(self.base_path, "avatar.json")
        config_path = os.path.join(self.base_path, "config.lua")

        # 1. Read avatar.json for Name, Description, Color, Poser, and Extra Animations
        if os.path.exists(avatar_path):
            try:
                with open(avatar_path, "r", encoding="utf-8-sig") as f:
                    meta = json.load(f)

                # Fresh boot detection: blank name or "Blankmon"
                current_name = str(meta.get("name", "")).strip()
                is_fresh_boot = current_name.lower() in ("", "blankmon")

                if is_fresh_boot:
                    self.avatar_name_var.set("")
                    self.desc_text.delete("1.0", tk.END)
                    self.set_all_fixes(True)
                    self.bake_math_var.set(False)
                else:
                    self.avatar_name_var.set(current_name)
                    desc_val = str(meta.get("description", ""))
                    self.desc_text.delete("1.0", tk.END)
                    self.desc_text.insert("1.0", desc_val)
                    self.set_all_fixes(False)

                self.on_desc_modified()

                # Icon Color
                icon_col = str(meta.get("color", "#ffffff")).strip()
                if not icon_col.startswith("#"):
                    icon_col = "#" + icon_col
                self.icon_color_var.set(icon_col)
                self.update_color_preview(icon_col)
                
                auto_scripts = []
                for k, v in meta.items():
                    if k.lower() in ("autoscripts", "auto_scripts") and isinstance(v, list):
                        auto_scripts = [s.replace("\\", "/").strip() for s in v if isinstance(s, str)]
                        break

                self.extra_anims_var.set(any(s.lower() in ("poser/extras", "poser/extras.lua") for s in auto_scripts))
                
                for script in reversed(auto_scripts):
                    if not script or "extras" in script.lower() or "priority" in script.lower():
                        continue
                    filename = re.split(r'[/\\]', script)[-1]
                    raw = re.sub(r'[^a-z0-9]', '', re.sub(r'\.lua$', '', filename, flags=re.I).lower())
                    if not raw:
                        continue
                    
                    matched = False
                    for idx, val in enumerate(self.poser_cb['values']):
                        norm_val = re.sub(r'[^a-z0-9]', '', val.lower())
                        norm_map = re.sub(r'[^a-z0-9]', '', self.poser_mapping.get(val, "").lower())
                        if raw in (norm_val, norm_map):
                            self.poser_var.set(val)
                            self.poser_cb.set(val)
                            self.poser_cb.current(idx)
                            matched = True
                            break
                    if matched:
                        break
            except Exception:
                pass

        # Check avatar icon (avatar.png) and update UI state
        if os.path.exists(os.path.join(self.base_path, "avatar.png")):
            self.player_icon_var.set("avatar.png")
        else:
            self.player_icon_var.set("")
        self.update_portrait_ui_state()
        self.update_animated_textures_ui_state()

        # Read config.lua for Head Path and Advanced Options
        if not os.path.exists(config_path):
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_content = f.read()
        except Exception:
            return

        # Check if head path is uninitialized template placeholder
        head_match = re.search(r'\["head"\]\s*=\s*([^,\n\r]+)', config_content)
        if head_match:
            head_val = head_match.group(1).strip()
            if "NAME_HERE" not in head_val and "PATH.TO.HEAD" not in head_val:
                # Extract head group suffix
                prefix = self.head_prefix_var.get()
                prefix_no_dot = prefix[:-1] if prefix.endswith(".") else prefix
                if head_val.startswith(prefix):
                    self.head_var.set(head_val[len(prefix):])
                elif head_val.startswith(prefix_no_dot):
                    self.head_var.set(head_val[len(prefix_no_dot):])
                else:
                    stripped = re.sub(r'^models(?:\[["\'].*?["\']\]|\.[a-zA-Z0-9_-]+)\.?', '', head_val)
                    self.head_var.set(stripped)

        # Parse Advanced Options from config.lua
        def set_str_var(var, pattern):
            m = re.search(pattern, config_content)
            if m:
                var.set(m.group(1).strip())

        def set_bool_var(var, pattern, toggle_fn=None):
            m = re.search(pattern, config_content)
            if m:
                val = m.group(1).strip().lower() == "true"
                var.set(val)
                if toggle_fn:
                    toggle_fn()

        set_str_var(self.scale_var, r'pokescale\s*=\s*([0-9.-]+)')
        set_str_var(self.camheight_var, r'camheight\s*=\s*([0-9.-]+)')
        set_str_var(self.nameplatepivot_var, r'nameplatepivot\s*=\s*([0-9.-]+)')
        set_str_var(self.pdollscale_var, r'pdollscale\s*=\s*([0-9.-]+)')
        set_str_var(self.movespeed_var, r'movespeed\s*=\s*([0-9.-]+)')

        set_bool_var(self.speedscale_var, r'speedscale\s*=\s*(true|false)', lambda: getattr(self, 'toggle_speed_fn', lambda: None)())
        set_bool_var(self.customcry_var, r'customcry\s*=\s*(true|false)', lambda: getattr(self, 'toggle_cry_fn', lambda: None)())
        set_bool_var(self.crosshair_var, r'crosshairAdjust\s*=\s*(true|false)')

        if self.customcry_var.get():
            model_file = self.model_var.get()
            if model_file:
                modelname = model_file.rsplit(".bbmodel", 1)[0]
                expected_cry = os.path.join(self.base_path, f"{modelname}_cry.ogg")
                if os.path.exists(expected_cry):
                    self.cryfile_var.set(expected_cry)

        # Parse Animated Textures (only if template supports animatedParts)
        self.anim_textures_data.clear()
        if re.search(r'\banimatedParts\b', config_content):
            parts_match = re.findall(r'\{\s*part\s*=\s*([^,\n\r]+),\s*animtexname\s*=\s*["\']([^"\']+)["\'],\s*framenumber\s*=\s*([0-9]+),\s*animfps\s*=\s*([0-9.]+),\s*animemissive\s*=\s*(true|false)\s*\}', config_content)
            if parts_match:
                for p, name, fnum, fps, em in parts_match:
                    if int(fnum) > 0:
                        p_clean = p.strip()
                        self.anim_textures_data.append({
                            'part': "" if p_clean == "nil" else p_clean,
                            'animtexname': name.strip(),
                            'framenumber': int(fnum), 'animfps': float(fps),
                            'animemissive': em.lower() == 'true'
                        })
        self.update_animated_textures_ui_state()

        # Parse Quirks
        self.quirks_data.clear()
        for line in config_content.splitlines():
            line_str = line.strip()
            if line_str.startswith("--"):
                continue
            m = re.search(r'addquirk\s*\(([^)]+)\)', line_str)
            if not m:
                continue
            args_str = m.group(1).strip()
            args = split_lua_args(args_str)
            if len(args) >= 2:
                q_name = args[0].strip(' "\'')
                q_anim = args[1].strip()
                q_min = 8.0
                q_max = 30.0
                q_pose = ""
                
                if len(args) >= 3 and args[2].strip():
                    try:
                        q_min = float(args[2].strip())
                    except ValueError:
                        pass
                if len(args) >= 4 and args[3].strip():
                    try:
                        q_max = float(args[3].strip())
                    except ValueError:
                        pass
                if len(args) >= 5 and args[4].strip():
                    raw_pose = args[4].strip()
                    if raw_pose != "nil":
                        q_pose = raw_pose
                    
                self.quirks_data.append({
                    'name': q_name,
                    'anim': q_anim,
                    'min': q_min,
                    'max': q_max,
                    'pose': q_pose
                })

    def get_available_animation_names(self):
        model_file = self.model_var.get()
        if not model_file:
            return []
        model_path = os.path.join(self.base_path, model_file)
        if not os.path.exists(model_path):
            return []
        try:
            with open(model_path, "r", encoding="utf-8") as f:
                model_text = f.read()
            model_text = re.sub(r'-?\bNaN\b', "0", model_text)
            model_data = json.loads(model_text)
            anims = []
            for a in model_data.get("animations", []):
                if isinstance(a, dict) and "name" in a:
                    raw_n = a["name"]
                    clean_n = re.sub(r'^animations?\.[^.]+\.', '', raw_n)
                    if clean_n not in anims:
                        anims.append(clean_n)
            return sorted(anims)
        except Exception:
            return []

    def auto_detect_poser(self):
        model_file = self.model_var.get()
        if not model_file:
            self.show_status("Error: Please select a .bbmodel file first.", "red")
            return

        model_path = os.path.join(self.base_path, model_file)
        try:
            with open(model_path, "r", encoding="utf-8") as f:
                model_text = f.read()
        except Exception as e:
            self.show_status(f"Error: Failed to read .bbmodel: {str(e)}", "red")
            return
            
        prefix = r'(?:animations?\.[^.\"]+\.)?'
        has_ground = bool(re.search(rf'"name"\s*:\s*"{prefix}(?:ground_idle|ground_walk|ground_run)"', model_text))
        has_water = bool(re.search(rf'"name"\s*:\s*"{prefix}(?:water_idle|water_swim)"', model_text))
        has_surface = bool(re.search(rf'"name"\s*:\s*"{prefix}(?:surfacewater_idle|surfacewater_swim)"', model_text))
        has_air = bool(re.search(rf'"name"\s*:\s*"{prefix}(?:air_idle|air_fly)"', model_text))
        
        # Automatic poser checks, I think the logic is right?
        poser_key = "standard"
        if has_ground and has_air and (has_water or has_surface):
            poser_key = "complete"
        elif has_water and has_surface:
            poser_key = "water"
        elif has_air and not has_water and not has_surface:
            poser_key = "flying"
        elif has_water and not has_surface:
            poser_key = "water_no_surface"
        elif has_surface and not has_water:
            poser_key = "water_only_surface"
            
        target_display_name = next(
            (display for display, raw in self.poser_mapping.items() if raw.lower() == poser_key), 
            None
        )
        
        if target_display_name and target_display_name in self.poser_cb['values']:
            self.poser_var.set(target_display_name)
            self.show_status(f"Poser '{target_display_name}' detected!", "green")
        else:
            standard_key = next((name for name in self.poser_cb['values'] if name.lower() == "standard"), None)
            if standard_key:
                self.poser_var.set(standard_key)
                self.show_status("Defaulted to standard Poser.", "green")

    def auto_find_head_path(self):
        try:
            model_file = self.model_var.get()
            if not model_file:
                self.show_status("Error: Please select a .bbmodel file first.", "red")
                return

            target_input = self.head_var.get().strip()
            original_target = target_input if target_input else "head"

            display_target = original_target
            if display_target.endswith("]"):
                match = re.search(r"\[['\"]([^'\"]+)['\"]\]$", display_target)
                if match:
                    display_target = match.group(1)
            elif "." in display_target:
                display_target = display_target.split(".")[-1]

            model_path = os.path.join(self.base_path, model_file)
            with open(model_path, "r", encoding="utf-8") as f:
                model_text = f.read()
            # Fix NaN and -NaN errors
            model_text = re.sub(r'-?\bNaN\b', "0", model_text)
            model_data = json.loads(model_text)
            
            uuid_to_name = {}
            for group in model_data.get("groups", []):
                if "uuid" in group and "name" in group:
                    uuid_to_name[group["uuid"]] = group["name"]
            
            outliner = model_data.get("outliner", [])
            
            def search_outliner(nodes, current_path, search_target):
                for node in nodes:
                    # Ignore any cubes and meshes (strings), take groups (dicts)
                    if isinstance(node, dict):
                        name = node.get("name", "")
                        if not name and "uuid" in node:
                            name = uuid_to_name.get(node["uuid"], "")
                            
                        name = str(name)
                        new_path = current_path + [name]
                        if name.strip().lower() == search_target.strip().lower():
                            return new_path
                        
                        children = node.get("children", [])
                        if isinstance(children, list) and children:
                            result = search_outliner(children, new_path, search_target)
                            if result:
                                return result
                return None
                
            # Try to find exactly what was typed (important for groups with dots like "arm.L")
            found_path = global_search_outliner(uuid_to_name, outliner, [], original_target)
            
            # If not found, check if it's a previously formatted path and extract the base name
            if not found_path and display_target != original_target:
                found_path = global_search_outliner(uuid_to_name, outliner, [], display_target)
            
            if found_path:
                formatted_suffix = ""
                for p in found_path:
                    # Standard lua dot notation if alphanumeric, otherwise use bracket indexing (models.granbull. vs models["granbull"].)
                    if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', p):
                        if formatted_suffix:
                            formatted_suffix += f".{p}"
                        else:
                            formatted_suffix = p
                    else:
                        formatted_suffix += f"['{p}']"
                        
                self.head_var.set(formatted_suffix)
                self.show_status(f"Head group '{found_path[-1]}' detected!", "green")
            else:
                self.show_status(f"Could not find any group named '{display_target}'.", "red")
                
        except Exception as e:
            self.show_status(f"Error: Failed to run Auto Find: {str(e)}", "red")

    def load_posers(self):
        # Unnecessary, but I wanted it to match the order of the original script
        display_names = []
        self.poser_mapping = {}
        poser_dir = os.path.join(self.base_path, "Poser")
        if os.path.exists(poser_dir):
            for file in os.listdir(poser_dir):
                if file.endswith(".lua") and not (file.startswith("priority") or file.startswith("Extras")):
                    raw_name = file.rsplit(".", 1)[0]
                    
                    if raw_name.lower() == "water_no_surface":
                        display_name = "Water (No surface)"
                    elif raw_name.lower() == "water_only_surface":
                        display_name = "Water (Only surface)"
                    else:
                        display_name = raw_name
                        
                    display_names.append(display_name)
                    self.poser_mapping[display_name] = raw_name
        
        preferred_order = [
            "standard",
            "water",
            "water (no surface)",
            "water (only surface)",
            "flying",
            "complete"
        ]
        display_names.sort(key=lambda x: preferred_order.index(x.lower()) if x.lower() in preferred_order else 999)
        
        self.poser_cb['values'] = display_names
        standard_key = next((name for name in display_names if name.lower() == "standard"), None)
        if standard_key:
            self.poser_var.set(standard_key)
        elif display_names:
            self.poser_cb.current(0)

    def open_animated_textures_dialog(self):
        if hasattr(self, "btn_anim_tex") and str(self.btn_anim_tex.cget("state")).lower() == "disabled":
            messagebox.showinfo("Incompatible Template", "This feature is not compatible with the old template.", parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Configure Animated Textures")
        dlg.grab_set()
        dlg.geometry("500x420")
        dlg.minsize(500, 420)
        dlg.config(padx=15, pady=15)

        tk.Label(dlg, text="Animated Textures Configuration", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))

        def get_short_part_name(path):
            if not path or path == "nil":
                return ""
            if path.endswith("]"):
                m = re.search(r"\[['\"]([^'\"]+)['\"]\]$", path)
                if m:
                    return m.group(1)
            if "." in path:
                return path.split(".")[-1]
            return path

        list_frame = tk.Frame(dlg)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("part", "name", "frames", "fps", "emissive")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        tree.heading("part", text="Model Part Path")
        tree.heading("name", text="Texture Name")
        tree.heading("frames", text="Frames")
        tree.heading("fps", text="FPS")
        tree.heading("emissive", text="Emissive")
        
        tree.column("part", width=110)
        tree.column("name", width=150)
        tree.column("frames", width=55, anchor="center")
        tree.column("fps", width=55, anchor="center")
        tree.column("emissive", width=65, anchor="center")
        
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def refresh_list():
            for row in tree.get_children():
                tree.delete(row)
            for item in self.anim_textures_data:
                short_part = get_short_part_name(item.get('part', ''))
                tree.insert("", tk.END, values=(
                    short_part, item.get('animtexname', ''),
                    item.get('framenumber', 0), item.get('animfps', 10),
                    "Yes" if item.get('animemissive') else "No"
                ))

        refresh_list()

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill=tk.X, pady=10)

        def edit_part(index=None):
            is_new = index is None
            item = self.anim_textures_data[index] if not is_new else {'part': '', 'animtexname': '', 'framenumber': 4, 'animfps': 10.0, 'animemissive': False}
            
            edit_win = tk.Toplevel(dlg)
            edit_win.title("Add Part" if is_new else "Edit Part")
            edit_win.grab_set()
            edit_win.config(padx=15, pady=15)
            edit_win.minsize(480, 240)
            
            lbl_part = tk.Label(edit_win, text="Model Part Path:")
            lbl_part.grid(row=0, column=0, sticky="e", pady=5)
            part_frame = tk.Frame(edit_win)
            part_frame.grid(row=0, column=1, sticky="w", pady=5)
            part_var = tk.StringVar(value=item['part'])
            part_entry = tk.Entry(part_frame, textvariable=part_var, width=35)
            part_entry.pack(side=tk.LEFT, padx=(0, 5))
            tip_part = "Hierarchy path to the model bone or group to animate (e.g. models.ponyta.tail)."
            Tooltip(lbl_part, tip_part)

            def auto_find_part():
                target_input = part_var.get().strip()
                if not target_input:
                    messagebox.showerror("Error", "Please type the name of the group that should be animated first.", parent=edit_win)
                    return
                
                model_file = self.model_var.get()
                if not model_file:
                    messagebox.showerror("Error", "Please select a .bbmodel file on the main window first.", parent=edit_win)
                    return
                try:
                    display_target = target_input
                    if display_target.endswith("]"):
                        m = re.search(r"\[['\"]([^'\"]+)['\"]\]$", display_target)
                        if m:
                            display_target = m.group(1)
                    elif "." in display_target:
                        display_target = display_target.split(".")[-1]
                        
                    model_path = os.path.join(self.base_path, model_file)
                    with open(model_path, "r", encoding="utf-8") as f:
                        model_text = f.read()
                    model_text = re.sub(r'-?\bNaN\b', "0", model_text)
                    model_data = json.loads(model_text)
                    
                    uuid_to_name = {}
                    for group in model_data.get("groups", []):
                        if "uuid" in group and "name" in group:
                            uuid_to_name[group["uuid"]] = group["name"]
                    
                    outliner = model_data.get("outliner", [])
                    found_path = global_search_outliner(uuid_to_name, outliner, [], display_target)
                    if not found_path and display_target != target_input:
                        found_path = global_search_outliner(uuid_to_name, outliner, [], target_input)
                        
                    if found_path:
                        prefix = self.head_prefix_var.get() if hasattr(self, 'head_prefix_var') and self.head_prefix_var.get() else "models."
                        if not prefix:
                            m_name = os.path.splitext(model_file)[0]
                            prefix = f"models.{m_name}." if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', m_name) else f"models['{m_name}']."
                            
                        formatted_suffix = ""
                        for p in found_path:
                            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', p):
                                if formatted_suffix:
                                    formatted_suffix += f".{p}"
                                else:
                                    formatted_suffix = p
                            else:
                                formatted_suffix += f"['{p}']"
                                
                        if formatted_suffix.startswith("[") and prefix.endswith("."):
                            full_path = f"{prefix[:-1]}{formatted_suffix}"
                        else:
                            full_path = f"{prefix}{formatted_suffix}"
                        part_var.set(full_path)
                    else:
                        messagebox.showerror("Not Found", f"Could not find any group named '{display_target}' in the .bbmodel.", parent=edit_win)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to search .bbmodel: {str(e)}", parent=edit_win)

            btn_auto_part = tk.Button(part_frame, text="Auto", command=auto_find_part, width=6)
            btn_auto_part.pack(side=tk.LEFT)

            lbl_tex_name = tk.Label(edit_win, text="Texture Base Name:")
            lbl_tex_name.grid(row=1, column=0, sticky="e", pady=5)
            name_var = tk.StringVar(value=item['animtexname'])
            name_entry = tk.Entry(edit_win, textvariable=name_var, width=25)
            name_entry.grid(row=1, column=1, sticky="w", pady=5)
            tip_tex_name = "Prefix name of the animation frame image files without numbers (e.g. 'flame_' for flame_0.png, flame_1.png)."
            Tooltip(lbl_tex_name, tip_tex_name)

            lbl_frames = tk.Label(edit_win, text="Frame Count:")
            lbl_frames.grid(row=2, column=0, sticky="e", pady=5)
            frame_var = tk.StringVar(value=str(item['framenumber']))
            frame_entry = tk.Entry(edit_win, textvariable=frame_var, width=10)
            frame_entry.grid(row=2, column=1, sticky="w", pady=5)
            tip_frames = "Total number of sequential texture frames in the animation sequence."
            Tooltip(lbl_frames, tip_frames)

            lbl_fps = tk.Label(edit_win, text="Animation FPS:")
            lbl_fps.grid(row=3, column=0, sticky="e", pady=5)
            fps_var = tk.StringVar(value=str(item['animfps']))
            fps_entry = tk.Entry(edit_win, textvariable=fps_var, width=10)
            fps_entry.grid(row=3, column=1, sticky="w", pady=5)
            tip_fps = "Playback speed in frames per second for the texture animation cycle."
            Tooltip(lbl_fps, tip_fps)

            lbl_em = tk.Label(edit_win, text="Emissive Texture:")
            lbl_em.grid(row=4, column=0, sticky="e", pady=5)
            em_var = tk.BooleanVar(value=item['animemissive'])
            em_cb = tk.Checkbutton(edit_win, variable=em_var)
            em_cb.grid(row=4, column=1, sticky="w", pady=5)
            tip_em = "When enabled, renders the texture as an emissive/glow layer that stays bright in the dark."
            Tooltip(lbl_em, tip_em)

            def save_part():
                try:
                    new_item = {
                        'part': part_var.get().strip(),
                        'animtexname': name_var.get().strip(),
                        'framenumber': int(frame_var.get()),
                        'animfps': float(fps_var.get()),
                        'animemissive': em_var.get()
                    }
                    if is_new:
                        self.anim_textures_data.append(new_item)
                    else:
                        self.anim_textures_data[index] = new_item
                    edit_win.destroy()
                    refresh_list()
                except ValueError:
                    messagebox.showerror("Invalid Input", "Frame Count and FPS must be valid numbers.", parent=edit_win)

            btn_save_part = tk.Button(edit_win, text="Save", command=save_part, width=15)
            btn_save_part.grid(row=5, column=0, columnspan=2, pady=(15, 0))

        def on_add():
            edit_part()

        def on_edit():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            edit_part(idx)

        def on_clone():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            cloned = dict(self.anim_textures_data[idx])
            self.anim_textures_data.append(cloned)
            refresh_list()

        def on_del():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            del self.anim_textures_data[idx]
            refresh_list()

        def on_clear():
            if not self.anim_textures_data:
                return
            if messagebox.askyesno("Clear All", "Are you sure you want to clear all animated textures?", parent=dlg):
                self.anim_textures_data.clear()
                refresh_list()

        btn_add_part = tk.Button(btn_frame, text="Add Part...", command=on_add, width=12)
        btn_add_part.pack(side=tk.LEFT, padx=2)
        btn_edit_part = tk.Button(btn_frame, text="Edit Part...", command=on_edit, width=12)
        btn_edit_part.pack(side=tk.LEFT, padx=2)
        btn_clone_part = tk.Button(btn_frame, text="Clone Part", command=on_clone, width=12)
        btn_clone_part.pack(side=tk.LEFT, padx=2)
        btn_del_part = tk.Button(btn_frame, text="Delete", command=on_del, width=10)
        btn_del_part.pack(side=tk.LEFT, padx=2)
        btn_clear_part = tk.Button(btn_frame, text="Clear All", command=on_clear, width=10)
        btn_clear_part.pack(side=tk.LEFT, padx=2)

        menu_blank = tk.Menu(dlg, tearoff=0)
        menu_blank.add_command(label="Add new part", command=on_add)
        menu_blank.add_command(label="Clear", command=on_clear)

        menu_item = tk.Menu(dlg, tearoff=0)
        menu_item.add_command(label="Edit part", command=on_edit)
        menu_item.add_command(label="Clone part", command=on_clone)
        menu_item.add_command(label="Delete part", command=on_del)

        def on_tree_right_click(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                menu_item.post(event.x_root, event.y_root)
            else:
                menu_blank.post(event.x_root, event.y_root)

        tree.bind("<Button-3>", on_tree_right_click)
        tree.bind("<Button-2>", on_tree_right_click)
        tree.bind("<Double-1>", lambda e: on_edit() if tree.selection() else None)

        btn_save_close_anim = tk.Button(dlg, text="Save & Close", command=dlg.destroy, width=15)
        btn_save_close_anim.pack(side=tk.BOTTOM, pady=(10, 0))

    def open_quirks_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Configure Quirks")
        dlg.grab_set()
        dlg.geometry("580x420")
        dlg.minsize(560, 420)
        dlg.config(padx=15, pady=15)

        tk.Label(dlg, text="Quirks Configuration", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 10))

        list_frame = tk.Frame(dlg)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ("name", "anim", "min", "max", "pose")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        tree.heading("name", text="Quirk Name")
        tree.heading("anim", text="Animation")
        tree.heading("min", text="Min (s)")
        tree.heading("max", text="Max (s)")
        tree.heading("pose", text="Base Animation")
        
        tree.column("name", width=110)
        tree.column("anim", width=125)
        tree.column("min", width=65, anchor="center")
        tree.column("max", width=65, anchor="center")
        tree.column("pose", width=125)
        
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def refresh_list():
            for row in tree.get_children():
                tree.delete(row)
            for item in self.quirks_data:
                q_name = item.get('name', '')
                raw_anim = item.get('anim', '')
                anim_disp = extract_anim_name(raw_anim) or q_name
                raw_pose = item.get('pose', '')
                pose_disp = extract_anim_name(raw_pose) if raw_pose else "-"
                tree.insert("", tk.END, values=(
                    q_name,
                    anim_disp,
                    fmt_num(item.get('min', 8.0)),
                    fmt_num(item.get('max', 30.0)),
                    pose_disp
                ))

        refresh_list()

        btn_frame = tk.Frame(dlg)
        btn_frame.pack(fill=tk.X, pady=10)

        def edit_quirk(index=None):
            is_new = index is None
            item = self.quirks_data[index] if not is_new else {
                'name': '',
                'anim': '',
                'min': 8.0,
                'max': 30.0,
                'pose': ''
            }
            
            edit_win = tk.Toplevel(dlg)
            edit_win.title("Add Quirk" if is_new else "Edit Quirk")
            edit_win.grab_set()
            edit_win.config(padx=15, pady=15)
            edit_win.minsize(420, 200)

            anim_choices = self.get_available_animation_names()
            
            lbl_name = tk.Label(edit_win, text="Quirk Name:")
            lbl_name.grid(row=0, column=0, sticky="e", pady=5)
            Tooltip(lbl_name, "Unique identifier for this quirk (e.g. 'blink', 'sleep1'). Matches Bedrock/Cobblemon quirk definitions.")
            name_var = tk.StringVar(value=item.get('name', ''))
            name_entry = tk.Entry(edit_win, textvariable=name_var, width=28)
            name_entry.grid(row=0, column=1, sticky="w", pady=5)

            lbl_anim = tk.Label(edit_win, text="Quirk Animation:")
            lbl_anim.grid(row=1, column=0, sticky="e", pady=5)
            Tooltip(lbl_anim, "The animation that plays when this quirk triggers (e.g. 'sleep_quirk'). If left blank, defaults to the Quirk Name.")
            anim_var = tk.StringVar(value=extract_anim_name(item.get('anim', '')))
            anim_cb = ttk.Combobox(edit_win, textvariable=anim_var, values=anim_choices, width=26)
            anim_cb.grid(row=1, column=1, sticky="w", pady=5)

            lbl_pose = tk.Label(edit_win, text="Base Animation:")
            lbl_pose.grid(row=2, column=0, sticky="e", pady=5)
            Tooltip(lbl_pose, "The base/pose animation that must currently be active for this quirk to trigger (e.g. 'sleep'). Leave blank to allow triggering at any time.")
            pose_var = tk.StringVar(value=extract_anim_name(item.get('pose', '')))
            pose_cb = ttk.Combobox(edit_win, textvariable=pose_var, values=anim_choices, width=26)
            pose_cb.grid(row=2, column=1, sticky="w", pady=5)

            lbl_min = tk.Label(edit_win, text="Min Interval (sec):")
            lbl_min.grid(row=3, column=0, sticky="e", pady=5)
            Tooltip(lbl_min, "Minimum cooldown time in seconds before this quirk can trigger again.")
            min_var = tk.StringVar(value=fmt_num(item.get('min', 8.0)))
            min_entry = tk.Entry(edit_win, textvariable=min_var, width=10)
            min_entry.grid(row=3, column=1, sticky="w", pady=5)

            lbl_max = tk.Label(edit_win, text="Max Interval (sec):")
            lbl_max.grid(row=4, column=0, sticky="e", pady=5)
            Tooltip(lbl_max, "Maximum wait time in seconds before this quirk triggers again.")
            max_var = tk.StringVar(value=fmt_num(item.get('max', 30.0)))
            max_entry = tk.Entry(edit_win, textvariable=max_var, width=10)
            max_entry.grid(row=4, column=1, sticky="w", pady=5)

            def save_quirk():
                n = name_var.get().strip()
                if not n:
                    messagebox.showerror("Invalid Input", "Quirk Name cannot be empty.", parent=edit_win)
                    return
                try:
                    mn = float(min_var.get())
                    mx = float(max_var.get())
                except ValueError:
                    messagebox.showerror("Invalid Input", "Min and Max intervals must be valid numbers.", parent=edit_win)
                    return
                
                if is_new:
                    existing = [q['name'] for q in self.quirks_data]
                else:
                    existing = [q['name'] for i, q in enumerate(self.quirks_data) if i != index]
                n = get_unique_quirk_name(n, existing)
                
                raw_anim = anim_var.get().strip()
                anim_saved = format_anim_ref(raw_anim) if raw_anim else format_anim_ref(n)
                
                raw_pose = pose_var.get().strip()
                pose_saved = format_anim_ref(raw_pose) if raw_pose else ""
                
                new_item = {
                    'name': n,
                    'anim': anim_saved,
                    'min': mn,
                    'max': mx,
                    'pose': pose_saved
                }
                if is_new:
                    self.quirks_data.append(new_item)
                else:
                    self.quirks_data[index] = new_item
                edit_win.destroy()
                refresh_list()

            btn_save_quirk = tk.Button(edit_win, text="Save", command=save_quirk, width=15)
            btn_save_quirk.grid(row=6, column=0, columnspan=2, pady=(15, 0))

        def on_add():
            edit_quirk()

        def on_edit():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            edit_quirk(idx)

        def on_clone():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            cloned = dict(self.quirks_data[idx])
            existing = [q['name'] for q in self.quirks_data]
            cloned['name'] = get_unique_quirk_name(cloned.get('name', ''), existing)
            self.quirks_data.append(cloned)
            refresh_list()

        def on_del():
            sel = tree.selection()
            if not sel:
                return
            idx = tree.index(sel[0])
            del self.quirks_data[idx]
            refresh_list()

        def on_clear():
            if not self.quirks_data:
                return
            if messagebox.askyesno("Clear All", "Are you sure you want to clear all quirks?", parent=dlg):
                self.quirks_data.clear()
                refresh_list()

        btn_add_q = tk.Button(btn_frame, text="Add Quirk...", command=on_add, width=12)
        btn_add_q.pack(side=tk.LEFT, padx=2)
        btn_edit_q = tk.Button(btn_frame, text="Edit Quirk...", command=on_edit, width=12)
        btn_edit_q.pack(side=tk.LEFT, padx=2)
        btn_clone_q = tk.Button(btn_frame, text="Clone Quirk", command=on_clone, width=12)
        btn_clone_q.pack(side=tk.LEFT, padx=2)
        btn_del_q = tk.Button(btn_frame, text="Delete", command=on_del, width=10)
        btn_del_q.pack(side=tk.LEFT, padx=2)
        btn_clear_q = tk.Button(btn_frame, text="Clear All", command=on_clear, width=10)
        btn_clear_q.pack(side=tk.LEFT, padx=2)

        menu_blank = tk.Menu(dlg, tearoff=0)
        menu_blank.add_command(label="Add new quirk", command=on_add)
        menu_blank.add_command(label="Clear", command=on_clear)

        menu_item = tk.Menu(dlg, tearoff=0)
        menu_item.add_command(label="Edit quirk", command=on_edit)
        menu_item.add_command(label="Clone quirk", command=on_clone)
        menu_item.add_command(label="Delete quirk", command=on_del)

        def on_tree_right_click(event):
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                menu_item.post(event.x_root, event.y_root)
            else:
                menu_blank.post(event.x_root, event.y_root)

        tree.bind("<Button-3>", on_tree_right_click)
        tree.bind("<Button-2>", on_tree_right_click)
        tree.bind("<Double-1>", lambda e: on_edit() if tree.selection() else None)

        btn_save_close_q = tk.Button(dlg, text="Save & Close", command=dlg.destroy, width=15)
        btn_save_close_q.pack(side=tk.BOTTOM, pady=(10, 0))

    def run_setup(self):
        self.show_status("")
        model_file = self.model_var.get()
        if not model_file:
            self.show_status("Error: Please select a .bbmodel file first.", "red")
            return
            
        poser_display = self.poser_var.get()
        if not poser_display:
            self.show_status("Error: Please select a Poser.", "red")
            return
            
        poser = self.poser_mapping.get(poser_display, poser_display)
        
        modelname = model_file.rsplit(".bbmodel", 1)[0]
        # Parser for stuff like "mr_mime" -> "Mr Mime", less useful now that the user can type their own name but keeping it for fallback
        pokename = modelname.replace("_", " ").title()
        
        head_suffix = self.head_var.get().strip()
        if not head_suffix:
            headpath = '"NONE"'
        else:
            prefix = self.head_prefix_var.get()
            # Clean up double dots if a bracket path follows a dot (e.g. models.granbull.['body'])
            if head_suffix.startswith("[") and prefix.endswith("."):
                prefix = prefix[:-1]
                
            # Fixes groups with protected group names (Fixes Gallade's head)
            headpath = f"{prefix}{head_suffix}"
            for res in ["Head", "Body", "RightArm", "LeftArm", "RightLeg", "LeftLeg", "RightPants", "LeftPants", "Jacket", "Hat"]:
                headpath = headpath.replace(f".{res}", f".{res.lower()}").replace(f"['{res}']", f"['{res.lower()}']")

        scale = self.scale_var.get().strip() or "1"
        camheight = self.camheight_var.get().strip() or "1"
        nameplatepivot = self.nameplatepivot_var.get().strip() or "0"
        pdollscale = self.pdollscale_var.get().strip() or "1"
        speedscale_val = "true" if self.speedscale_var.get() else "false"
        movespeed = self.movespeed_var.get().strip() or "0.35"
        customcry_val = "true" if self.customcry_var.get() else "false"
        crosshair_val = "true" if self.crosshair_var.get() else "false"
            
        try:
            # 1. Update avatar.json
            avatar_path = os.path.join(self.base_path, "avatar.json")
            with open(avatar_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            user_name = self.avatar_name_var.get().strip()
            meta["name"] = user_name if user_name else pokename.capitalize()
            
            user_desc = self.desc_text.get("1.0", tk.END).rstrip("\r\n")
            if user_desc.strip():
                meta["description"] = user_desc
            else:
                meta["description"] = f"{meta['name']} from Cobblemon.   \nUses the GS animblend library and Katt keybind config"
            
            color_val = self.icon_color_var.get().strip()
            if color_val:
                if not color_val.startswith("#"):
                    color_val = "#" + color_val
                meta["color"] = color_val
            else:
                meta["color"] = "#ffffff"

            meta.setdefault("autoScripts", [])
            while len(meta["autoScripts"]) < 3:
                meta["autoScripts"].append("")
            meta["autoScripts"][2] = f"Poser/{poser}"
            if self.extra_anims_var.get():
                if "Poser/Extras" not in meta["autoScripts"]:
                    meta["autoScripts"].append("Poser/Extras")
            else:
                meta["autoScripts"] = [s for s in meta["autoScripts"] if s != "Poser/Extras"]

            with open(avatar_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=4)
                
            # 2. Convert .bbmodel
            model_path = os.path.join(self.base_path, model_file)
            with open(model_path, "r", encoding="utf-8") as model_f:
                fixedmodel = model_f.read()

            is_non_generic_model = not bool(re.search(r'"model_format"\s*:\s*"(?:free|generic)"', fixedmodel))

            if self.fixes_vars["fix_math_expr"].get():
                fixedmodel = fixedmodel.replace("Math.", "math.")
                fixedmodel = re.sub(r"(?i)math\.sin", "Math.sin", fixedmodel)
                fixedmodel = re.sub(r"(?i)math\.cos", "Math.cos", fixedmodel)
                fixedmodel = re.sub(r'-?\bNaN\b', "0", fixedmodel)

            if self.fixes_vars["sound_instruction_keyframes"].get():
                fixedmodel = re.sub(r'"channel"\s*:\s*"sound"\s*,\s*"data_points"\s*:\s*\[\s*\{\s*"effect"\s*:\s*"([a-zA-Z0-9_.]+)"', r'"channel":"timeline","data_points":[{"script":"KeySound(\\"\g<1>\\")"', fixedmodel, flags=re.IGNORECASE)

            if self.fixes_vars["strip_anim_prefix"].get():
                fixedmodel = re.sub(r"animations?\.[^.\"]+\.", "", fixedmodel)
            
            # Converting to a Generic model
            if self.fixes_vars["convert_generic"].get():
                fixedmodel = re.sub(r'"model_format":\s*"[^"]+"', '"model_format":"free"', fixedmodel)
            
            # THE GREAT MATH PURGE. lord have mercy
            if self.fixes_vars["fix_math_expr"].get():
                # 1. Fix leading signs in strings
                fixedmodel = re.sub(r'("[xyz]"\s*:\s*"\s*)-(?=[a-zA-Z(])', r'\g<1>0-', fixedmodel)
                fixedmodel = re.sub(r'("[xyz]"\s*:\s*"\s*)\+(?=[a-zA-Z(])', r'\g<1>0+', fixedmodel)
                # 2. Fix missing operands in *- (or /-, +-, --). E.g. `* -10` -> `*(0-10)`
                fixedmodel = re.sub(r'([+\-*/])\s*-\s*([a-zA-Z_][a-zA-Z0-9_.]*|[0-9.]+)(?![a-zA-Z0-9_.]|\()', r'\g<1>(0-\g<2>)', fixedmodel)
                # 3. Prevent crashes from unary minus/plus directly inside parentheses. E.g. `(-2)` -> `(0-2)`
                fixedmodel = re.sub(r'\(\s*-\s*(math\.|q\.|query\.|v\.|[0-9])', r'(0-\g<1>', fixedmodel, flags=re.IGNORECASE)
                fixedmodel = re.sub(r'\(\s*\+\s*(math\.|q\.|query\.|v\.|[0-9])', r'(\g<1>', fixedmodel, flags=re.IGNORECASE)

            if self.fixes_vars["emissive_name"].get():
                fixedmodel = fixedmodel.replace("_emissive.png", "_e.png")

            # Fix duplicate names between groups and cubes in the same parent (fixes Mienshao, Charizard)
            try:
                model_data = json.loads(fixedmodel)
                uuid_to_element = {el.get("uuid"): el for el in model_data.get("elements", []) if isinstance(el, dict) and "uuid" in el}
                
                modified_json = False
                
                # Fix face texture mappings for non-generic models that cause texture swapping in Generic format
                if self.fixes_vars["base_texture_mapping"].get() and is_non_generic_model:
                    # Push shiny and pattern textures to the bottom so the base texture is (hopefully) at index 0 (Fixes Porygon, Arbok)
                    if "textures" in model_data and len(model_data["textures"]) > 0:
                        def tex_sort(t):
                            name = t.get("name", "").lower() if isinstance(t, dict) else ""
                            return 1 if any(x in name for x in ["_shiny", "_pattern", "_alpha", "_e."]) else 0
                        
                        model_data["textures"].sort(key=tex_sort)
                        modified_json = True

                    if "elements" in model_data:
                        for el in model_data.get("elements", []):
                            if isinstance(el, dict) and "faces" in el:
                                for face in el["faces"].values():
                                    if isinstance(face, dict) and face.get("texture") != 0:
                                        face["texture"] = 0
                                        modified_json = True

                uuid_to_group_name = {}
                renamed_elements = {}
                reserved_names = {"Head", "Body", "RightArm", "LeftArm", "RightLeg", "LeftLeg", "RightPants", "LeftPants", "Jacket", "Hat"}
                
                for group in model_data.get("groups", []):
                    if isinstance(group, dict) and "uuid" in group and "name" in group:
                        if self.fixes_vars["reserved_names"].get() and group["name"] in reserved_names:
                            group["name"] = group["name"].lower()
                            renamed_elements[group["uuid"]] = group["name"]
                            modified_json = True
                        uuid_to_group_name[group["uuid"]] = group["name"]

                # Sync texture UV size and deduplicate textures with same name (keeping lowest index number)
                if self.fixes_vars["clean_dedup_textures"].get() and "textures" in model_data and isinstance(model_data["textures"], list):
                    proj_w = model_data.get("resolution", {}).get("width", 64)
                    proj_h = model_data.get("resolution", {}).get("height", 64)
                    seen_names = {}
                    new_textures = []
                    old_to_new_idx = {}
                    
                    anim_tex_names = {
                        item.get("animtexname", "").strip().lower()
                        for item in getattr(self, "anim_textures_data", [])
                        if isinstance(item, dict) and item.get("animtexname")
                    }
                    
                    for old_idx, texture in enumerate(model_data["textures"]):
                        if isinstance(texture, dict):
                            tex_w = texture.get("width")
                            tex_h = texture.get("height")
                            
                            # If width or height are missing, extract from base64 PNG header or image file
                            if not tex_w or not tex_h:
                                src = texture.get("source", "")
                                if isinstance(src, str):
                                    hdr = None
                                    if src.startswith("data:image/png;base64,"):
                                        try:
                                            hdr = base64.b64decode(src.split(",", 1)[1][:64])
                                        except Exception:
                                            pass
                                    elif os.path.isfile(src):
                                        try:
                                            with open(src, "rb") as img_f:
                                                hdr = img_f.read(32)
                                        except Exception:
                                            pass
                                    elif os.path.isfile(os.path.join(self.base_path, src)):
                                        try:
                                            with open(os.path.join(self.base_path, src), "rb") as img_f:
                                                hdr = img_f.read(32)
                                        except Exception:
                                            pass
                                    if hdr and hdr.startswith(b"\x89PNG\r\n\x1a\n") and len(hdr) >= 24:
                                        pw, ph = struct.unpack(">II", hdr[16:24])
                                        tex_w = tex_w or pw
                                        tex_h = tex_h or ph
                                        
                            tex_w = tex_w or proj_w
                            tex_h = tex_h or proj_h
                            uv_w = texture.get("uv_width", tex_w)
                            uv_h = texture.get("uv_height", tex_h)
                            tex_name_clean = texture.get("name", "").strip().lower()

                            is_declared_animated = tex_name_clean in anim_tex_names
                            is_subframe_uv = (uv_h < tex_h) or (uv_w < tex_w)

                            if not is_declared_animated and not is_subframe_uv:
                                if (tex_w != tex_h and uv_w == uv_h and uv_h >= tex_h and uv_w >= tex_w) or (uv_h > tex_h) or (uv_w > tex_w):
                                    if texture.get("uv_width") != tex_w or texture.get("uv_height") != tex_h:
                                        texture["uv_width"] = tex_w
                                        texture["uv_height"] = tex_h
                                        modified_json = True
                                
                            tex_name = texture.get("name", "").strip().lower()
                            if tex_name and tex_name in seen_names:
                                # Duplicate texture name!!!! Delete this higher slot and map to existing lower slot
                                old_to_new_idx[old_idx] = seen_names[tex_name]
                                modified_json = True
                            else:
                                new_idx = len(new_textures)
                                if tex_name:
                                    seen_names[tex_name] = new_idx
                                old_to_new_idx[old_idx] = new_idx
                                new_textures.append(texture)
                        else:
                            old_to_new_idx[old_idx] = len(new_textures)
                            new_textures.append(texture)
                            
                    if len(new_textures) < len(model_data["textures"]):
                        model_data["textures"] = new_textures
                        for el in model_data.get("elements", []):
                            if isinstance(el, dict) and "faces" in el:
                                for face in el["faces"].values():
                                    if isinstance(face, dict) and "texture" in face:
                                        t_val = face["texture"]
                                        if isinstance(t_val, int) and t_val in old_to_new_idx:
                                            if face["texture"] != old_to_new_idx[t_val]:
                                                face["texture"] = old_to_new_idx[t_val]
                                                modified_json = True

                def rename_conflicts(nodes):
                    nonlocal modified_json
                    child_groups = set()
                    
                    for node in nodes:
                        if isinstance(node, dict):
                            name = node.get("name", "")
                            if self.fixes_vars["reserved_names"].get() and name in reserved_names:
                                node["name"] = name.lower()
                                renamed_elements[node.get("uuid")] = node["name"]
                                modified_json = True
                                name = node["name"]
                                
                            if not name and "uuid" in node:
                                name = uuid_to_group_name.get(node["uuid"], "")
                            if name:
                                child_groups.add(name)
                    
                    for node in nodes:
                        if isinstance(node, str):
                            element = uuid_to_element.get(node)
                            if element and element.get("name") in child_groups:
                                element["name"] = f"{element['name']}_mesh"
                                renamed_elements[element.get("uuid")] = element["name"]
                                modified_json = True
                        elif isinstance(node, dict):
                            children = node.get("children", [])
                            if children:
                                rename_conflicts(children)
                                
                if self.fixes_vars["mesh_conflicts"].get() and "outliner" in model_data:
                    rename_conflicts(model_data["outliner"])

                if "animations" in model_data:
                    baking_enabled = self.fixes_vars["bake_math"].get()
                    do_auto_loop = self.fixes_vars["auto_loop_anims"].get()
                    do_inst_scripts = self.fixes_vars["sound_instruction_keyframes"].get()
                    do_math_fix = self.fixes_vars["fix_math_expr"].get()

                    for anim in model_data["animations"]:
                        if do_auto_loop:
                            anim_name = anim.get("name", "")
                            if anim_name.endswith(('_idle', '_walk', '_run', '_fly', '_swim', '_dive')) or anim_name == "sleep":
                                if anim.get("loop") != "loop":
                                    anim["loop"] = "loop"
                                    modified_json = True
                                
                        animators = anim.get("animators")
                        
                        animator_list = []
                        if isinstance(animators, dict):
                            animator_list = animators.values()
                        elif isinstance(animators, list):
                            animator_list = animators
                            
                        for animator in animator_list:
                            if not isinstance(animator, dict):
                                continue
                                
                            # Update animation names targeting renamed meshes
                            anim_uuid = animator.get("uuid")
                            if anim_uuid and anim_uuid in renamed_elements:
                                animator["name"] = renamed_elements[anim_uuid]
                                modified_json = True
                                
                            # ALWAYS convert Molang instruction scripts (in timeline/script/sound channels) to valid Lua
                            # If baking is OFF, fix math expressions on transform channels (skipping plain numbers)
                            # If baking is ON, skip transform math fixes so the baker will evaluate and overwrite them with clean numbers!
                            for kf in animator.get("keyframes", []):
                                if not isinstance(kf, dict):
                                    continue
                                ch = kf.get("channel")

                                if do_inst_scripts and ch in ("timeline", "script", "sound"):
                                    for dp in kf.get("data_points", []):
                                        if isinstance(dp, dict):
                                            if "script" in dp:
                                                s = dp["script"]
                                                if isinstance(s, str):
                                                    new_s = fix_instruction_script(s)
                                                    if new_s != s:
                                                        dp["script"] = new_s
                                                        modified_json = True
                                            elif "effect" in dp:
                                                kf["channel"] = "timeline"
                                                dp["script"] = f'KeySound("{dp["effect"]}");'
                                                del dp["effect"]
                                                modified_json = True
                                elif not baking_enabled and do_math_fix and ch in ("rotation", "position", "scale"):
                                    for dp in kf.get("data_points", []):
                                        if isinstance(dp, dict):
                                            for coord in ("x", "y", "z"):
                                                val = dp.get(coord)
                                                if isinstance(val, str) and has_math_expr(val):
                                                    new_val = fix_math_expr(val)
                                                    if new_val != val:
                                                        dp[coord] = new_val
                                                        modified_json = True

                    if baking_enabled:
                        bake_rate = self.bake_rate_var.get()
                        bake_interp = self.bake_interp_var.get()
                        bake_report = bake_model_animations(model_data, rate=bake_rate, interpolation=bake_interp)
                        if bake_report:
                            modified_json = True

                    # Model optimization (identity channel pruning, dead keyframe pruning, empty animator removal, metadata cleanup)
                    if self.fixes_vars["prune_empty"].get():
                        kfs_pruned, anims_pruned, ch_pruned = optimize_model_data(model_data)
                        if kfs_pruned > 0 or anims_pruned > 0 or ch_pruned > 0:
                            modified_json = True
                    
                fixedmodel = json.dumps(model_data, separators=(',', ':'), ensure_ascii=False)
            except Exception as e:
                print(f"Could not resolve mesh name conflicts: {e}")

            with open(model_path, "w", encoding="utf-8") as model_f:
                model_f.write(fixedmodel)

            # 3. Write config.lua
            config_path = os.path.join(self.base_path, "config.lua")
            if not os.path.exists(config_path):
                self.show_status("Error: config.lua not found in avatar folder.", "red")
                return

            with open(config_path, 'r', encoding="utf-8") as f:
                config_content = f.read()

            config_content = re.sub(r'modelname\s*=\s*".*?"', f'modelname = "{modelname}"', config_content)
            config_content = re.sub(r'\["head"\]\s*=\s*[^,\n\r]+', f'["head"] = {headpath}', config_content)
            config_content = re.sub(r'pokescale\s*=\s*[0-9.-]+', f'pokescale = {scale}', config_content)
            config_content = re.sub(r'camheight\s*=\s*[0-9.-]+', f'camheight = {camheight}', config_content)
            config_content = re.sub(r'nameplatepivot\s*=\s*[0-9.-]+', f'nameplatepivot = {nameplatepivot}', config_content)
            config_content = re.sub(r'pdollscale\s*=\s*[0-9.-]+', f'pdollscale = {pdollscale}', config_content)
            config_content = re.sub(r'speedscale\s*=\s*(true|false)', f'speedscale = {speedscale_val}', config_content)
            config_content = re.sub(r'movespeed\s*=\s*[0-9.-]+', f'movespeed = {movespeed}', config_content)
            config_content = re.sub(r'customcry\s*=\s*(true|false)', f'customcry = {customcry_val}', config_content)
            config_content = re.sub(r'crosshairAdjust\s*=\s*(true|false)', f'crosshairAdjust = {crosshair_val}', config_content)

            # Helper for replacing Lua variables, especially tables with nested braces
            def replace_lua_var(content, var_name, new_val_str):
                m = re.search(r'(' + re.escape(var_name) + r'\s*=\s*)', content)
                if not m:
                    return content, False
                start_idx = m.end()
                val_start = content[start_idx:].lstrip()
                offset = len(content[start_idx:]) - len(val_start)
                actual_start = start_idx + offset
                if val_start.startswith('{'):
                    depth = 0
                    end_idx = actual_start
                    for i in range(actual_start, len(content)):
                        if content[i] == '{':
                            depth += 1
                        elif content[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end_idx = i + 1
                                break
                    return content[:m.start()] + f"{var_name} = " + new_val_str + content[end_idx:], True
                else:
                    end_m = re.search(r'[,;\n\r]', content[actual_start:])
                    end_idx = (actual_start + end_m.start()) if end_m else len(content)
                    return content[:m.start()] + f"{var_name} = " + new_val_str + content[end_idx:], True

            # Format and inject Animated Textures (only if supported by template)
            if re.search(r'\banimatedParts\b', config_content):
                parts_lua = "nil"
                if self.anim_textures_data:
                    parts_lua = "{\n"
                    for item in self.anim_textures_data:
                        ip = item['part'] if item['part'] else "nil"
                        it = item['animtexname'] if item['animtexname'] else ""
                        ifm = item['framenumber']
                        ifps = item['animfps']
                        iem = "true" if item['animemissive'] else "false"
                        parts_lua += f'\t\t\t{{\n\t\t\t\tpart = {ip},\n\t\t\t\tanimtexname = "{it}",\n\t\t\t\tframenumber = {ifm},\n\t\t\t\tanimfps = {ifps},\n\t\t\t\tanimemissive = {iem}\n\t\t\t}},\n'
                    parts_lua += "\t\t}"

                # If older legacy standalone variables exist alongside animatedParts, clean them out
                if "animatedPart =" in config_content:
                    config_content = re.sub(r'(\s*--[^\n\r]*\n)*\s*animatedPart\s*=[^\n\r]*\n', '', config_content)
                    config_content = re.sub(r'(\s*--[^\n\r]*\n)*\s*animtexname\s*=[^\n\r]*\n', '', config_content)
                    config_content = re.sub(r'(\s*--[^\n\r]*\n)*\s*framenumber\s*=[^\n\r]*\n', '', config_content)
                    config_content = re.sub(r'(\s*--[^\n\r]*\n)*\s*animfps\s*=[^\n\r]*\n', '', config_content)
                    config_content = re.sub(r'(\s*--[^\n\r]*\n)*\s*animemissive\s*=[^\n\r]*\n', '', config_content)

                config_content, _ = replace_lua_var(config_content, "animatedParts", parts_lua)

            # Format and inject Quirks
            if "require(\"Pokemon.quirks\")[1]" in config_content or "require('Pokemon.quirks')[1]" in config_content:
                parts = re.split(r'(local\s+addquirk\s*=\s*require\(["\']Pokemon\.quirks["\']\)\[1\])', config_content)
                if len(parts) >= 3:
                    before_quirks = parts[0] + parts[1]
                    after_quirks_sec = parts[2]
                    ret_split = re.split(r'(return\s+config)', after_quirks_sec)
                    if len(ret_split) >= 2:
                        new_quirks_str = "\n\t--quirk info can be found at common/src/main/kotlin/com/cobblemon/mod/common/client/render/models/blockbench/pokemon/genX/[Pokemon]Model.kt\n\t--how to translate that info into what addquirk wants can be found in quirk.png\n\t--addquirk(name, animation, min, max, pose)\n"
                        for q in self.quirks_data:
                            q_name = q['name']
                            raw_anim = q.get('anim') or q_name
                            q_anim = format_anim_ref(raw_anim)
                            q_min = q.get('min', 8.0)
                            q_max = q.get('max', 30.0)
                            raw_pose = q.get('pose', '') or ''
                            q_pose = format_anim_ref(raw_pose) if raw_pose.strip() else ""

                            min_s = fmt_num(q_min)
                            max_s = fmt_num(q_max)

                            if q_pose:
                                new_quirks_str += f'\taddquirk("{q_name}", {q_anim}, {min_s}, {max_s}, {q_pose})\n'
                            elif q_min != 8.0 or q_max != 30.0:
                                new_quirks_str += f'\taddquirk("{q_name}", {q_anim}, {min_s}, {max_s})\n'
                            else:
                                new_quirks_str += f'\taddquirk("{q_name}", {q_anim})\n'
                        config_content = before_quirks + new_quirks_str + "\n" + ret_split[-2] + (ret_split[-1] if len(ret_split) > 2 else "")

            with open(config_path, 'w', encoding="utf-8") as f:
                f.write(config_content)
                
            if self.customcry_var.get() and self.cryfile_var.get():
                cry_src = self.cryfile_var.get()
                if os.path.exists(cry_src):
                    cry_dst = os.path.join(self.base_path, f"{modelname}_cry.ogg")
                    try:
                        if os.path.abspath(cry_src) != os.path.abspath(cry_dst):
                            shutil.copy2(cry_src, cry_dst)
                    except shutil.SameFileError:
                        pass

            self.show_status("Setup complete!", "green")
            
        except Exception as e:
            self.show_status(f"Error: {str(e)}", "red")

if __name__ == "__main__":
    root = tk.Tk()
    app = AvatarBuilderApp(root)
    root.mainloop()