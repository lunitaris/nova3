##
# Permet de lancer des tests sur des modules pour monitorer les services
import time
import functools
from collections import defaultdict
from functools import wraps
import logging
import inspect

logger = logging.getLogger("profiler")
# Stockage mémoire simple des temps d'exécution
execution_times = defaultdict(list)


def profile(name=None):
    """
    Décorateur compatible sync et async pour mesurer le temps d'exécution d'une fonction.
    """
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
    """
    Décorateur pour profiler un composant. Stocke les temps d'exécution cumulés en RAM.
    """
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
    """
    Retourne une moyenne simple des temps d'exécution par composant
    """
    stats = {}
    for component, times in execution_times.items():
        if times:
            stats[component] = round(sum(times) / len(times), 2)
    return stats

def reset_profiling():
    """
    Vide les temps mesurés (utile pour les tests ou une UI réactive)
    """
    execution_times.clear()
