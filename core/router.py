"""Minimal routing table: (method, path) -> handler(request_dict).

v1.3.0:
  - Core routes are PROTECTED — modules cannot override them.
  - `add_core()` registers a protected route.
  - `add()` raises if the route is protected.
"""


class Router:
    def __init__(self):
        self._routes = {}
        self._protected = set()

    def add(self, method, path, handler, protected=False):
        key = (method.upper(), path)
        if key in self._protected:
            raise Exception(
                f"Route {key[0]} {key[1]} is protected (core) — cannot override"
            )
        self._routes[key] = handler
        if protected:
            self._protected.add(key)

    def add_core(self, method, path, handler):
        """Register a core route that modules cannot override."""
        self.add(method, path, handler, protected=True)

    def match(self, method, path):
        return self._routes.get((method.upper(), path))

    def has(self, method, path):
        return (method.upper(), path) in self._routes

    def is_protected(self, method, path):
        return (method.upper(), path) in self._protected

    def keys(self):
        return list(self._routes.keys())

    def core_keys(self):
        return list(self._protected)