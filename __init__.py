from .ai_clipping_nodes import (
    NODE_CLASS_MAPPINGS as _N,
    NODE_DISPLAY_NAME_MAPPINGS as _D,
)
from .ai_clipping_video_saver import (
    NODE_CLASS_MAPPINGS as _SN,
    NODE_DISPLAY_NAME_MAPPINGS as _SD,
)

NODE_CLASS_MAPPINGS = {**_N, **_SN}
NODE_DISPLAY_NAME_MAPPINGS = {**_D, **_SD}
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
