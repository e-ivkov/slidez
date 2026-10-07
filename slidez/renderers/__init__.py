"""Renderer interface. PDF today; other formats/viewers later."""


class Renderer:
    name = "base"

    def render(self, pres, path: str):
        raise NotImplementedError
