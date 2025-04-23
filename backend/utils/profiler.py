import time
import functools
from collections import defaultdict
from functools import wraps
import logging
import inspect
import os
import sys
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

logger = logging.getLogger("profiler")
execution_times = defaultdict(list)

def profile(name=None):
    def decorator(func):
        label = name or func.__name__

        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    duration = (time.perf_counter() - start) * 1000
                    logger.info(f"[PROFILE] {label} → {duration:.2f} ms")
            return async_wrapper

        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = (time.perf_counter() - start) * 1000
                    logger.info(f"[PROFILE] {label} → {duration:.2f} ms")
            return sync_wrapper

    return decorator

def profile_component(component_name):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                end = time.perf_counter()
                elapsed_ms = (end - start) * 1000
                execution_times[component_name].append(elapsed_ms)
        return wrapper
    return decorator

def get_profiling_stats():
    stats = {}
    for component, times in execution_times.items():
        if times:
            stats[component] = round(sum(times) / len(times), 2)
    return stats

def reset_profiling():
    execution_times.clear()

# ========== TRACE TERMINAL VISUEL ==========
current_trace = None

trace_logger = logging.getLogger("trace_terminal")
trace_logger.setLevel(logging.INFO)

console = logging.StreamHandler(sys.stdout)
console.setFormatter(logging.Formatter("%(message)s"))
trace_logger.addHandler(console)

file = logging.FileHandler("./logs/nova_trace.log", mode="a", encoding="utf-8")
file.setFormatter(logging.Formatter("%(message)s"))
trace_logger.addHandler(file)

class TreeTracer:
    def __init__(self, label=None, *, file=None, func=None, level=0, parent=None, prefix="⏳", args=None):
        frame = inspect.stack()[1]
        self.file = file or os.path.basename(frame.filename)
        self.func = func or frame.function
        self.label = label or f"{self.file} > {self.func}()"
        self.level = level
        self.prefix = prefix
        self.parent = parent
        self.args = args or {}
        self.start_time = time.time()
        self.children = []
        self.closed = False
        self._log(Fore.YELLOW + f"{self.prefix} {self.label}")
        if self.args:
            self._log_args()

    def _log_args(self):
        indent = "│   " * (self.level + 1)
        if isinstance(self.args, dict) and self.args:
            trace_logger.info(Fore.CYAN + f"{indent}↳ args:")
            for k, v in self.args.items():
                trace_logger.info(Fore.CYAN + f"{indent}   - {k}: {repr(v)}")

    def step(self, label=None, prefix="│", **kwargs):
        child = TreeTracer(
            label=label,
            level=self.level + 1,
            parent=self,
            prefix=prefix,
            args=kwargs
        )
        self.children.append(child)
        return child

    def condition(self, description, result: bool):
        status = f"{Fore.GREEN}VRAI" if result else f"{Fore.RED}FAUX"
        cond = self.step(f"❓ Condition: {description}")
        cond.done(status)
        return result

    def loop(self, label, iterable):
        loop_root = self.step(f"🔁 Boucle sur {len(iterable)} éléments: {label}")
        return [(i, loop_root.step(f"🌀 {label}[{i}]")) for i in range(len(iterable))]

    def skip(self, reason):
        skip = self.step(f"⚠️ Skip")
        skip.done(Fore.LIGHTBLACK_EX + f"Raison: {reason}")

    def exception(self, error: Exception):
        exc = self.step(Fore.RED + "❌ Exception capturée")
        exc.done(str(error))

    def done(self, result=None):
        if not self.closed:
            elapsed = time.time() - self.start_time
            result_info = f" → {Fore.GREEN}{result}" if result else ""
            self._log(Fore.GREEN + f"✅ {self.label} terminé en {elapsed:.3f}s{result_info}")
            self.closed = True

    def fail(self, error=""):
        if not self.closed:
            elapsed = time.time() - self.start_time
            self._log(Fore.RED + f"❌ {self.label} échoué après {elapsed:.3f}s {error}")
            self.closed = True

    def _log(self, message):
        indent = "│   " * self.level
        trace_logger.info(f"{indent}{message}")

def trace_step(label=None):
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            global current_trace
            parent = current_trace
            if parent:
                tracer = parent.step(label or func.__name__, **kwargs)
            else:
                frame = inspect.stack()[1]
                fname = os.path.basename(frame.filename)
                tracer = TreeTracer(label or func.__name__, file=fname, func=func.__name__, args=kwargs)
            previous_trace = current_trace
            current_trace = tracer
            try:
                result = await func(*args, **kwargs)
                tracer.done(str(result)[:80])
                return result
            except Exception as e:
                tracer.fail(str(e))
                raise
            finally:
                current_trace = previous_trace

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            global current_trace
            parent = current_trace
            if parent:
                tracer = parent.step(label or func.__name__, **kwargs)
            else:
                frame = inspect.stack()[1]
                fname = os.path.basename(frame.filename)
                tracer = TreeTracer(label or func.__name__, file=fname, func=func.__name__, args=kwargs)
            previous_trace = current_trace
            current_trace = tracer
            try:
                result = func(*args, **kwargs)
                tracer.done(str(result)[:80])
                return result
            except Exception as e:
                tracer.fail(str(e))
                raise
            finally:
                current_trace = previous_trace

        return async_wrapper if inspect.iscoroutinefunction(func) else sync_wrapper

    return decorator
