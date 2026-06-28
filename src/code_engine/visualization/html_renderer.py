"""HTML rendering boundary; interactive rendering is not implemented."""


def render_html(*_args, **_kwargs) -> str:
    raise NotImplementedError("Visualization HTML rendering is not implemented in this MVP.")

