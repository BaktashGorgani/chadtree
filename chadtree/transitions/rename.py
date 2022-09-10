from os.path import abspath
from pathlib import PurePath
from typing import Optional

from pynvim_pp.nvim import Nvim
from std2 import anext

from ..fs.ops import ancestors, exists, rename
from ..lsp.notify import lsp_moved
from ..registry import rpc
from ..settings.localization import LANG
from ..settings.types import Settings
from ..state.next import forward
from ..state.types import State
from .shared.current import maybe_path_above
from .shared.index import indices
from .shared.refresh import refresh
from .shared.wm import kill_buffers
from .types import Stage


@rpc(blocking=False)
async def _rename(state: State, settings: Settings, is_visual: bool) -> Optional[Stage]:
    """
    rename file / folder
    """

    node = await anext(indices(state, is_visual=is_visual), None)
    if not node:
        return None
    else:

        child = await Nvim.input(question=LANG("pencil"), default=str(node.path.name))
        if not child:
            return None
        else:
            new_path = PurePath(abspath(node.path.parent / child))
            operations = {node.path: new_path}
            if await exists(new_path, follow=False):
                await Nvim.write(LANG("already_exists", name=str(new_path)), error=True)
                return None
            else:
                try:
                    await rename(operations)
                except Exception as e:
                    await Nvim.write(e, error=True)
                    return await refresh(state=state, settings=settings)
                else:
                    new_state = (
                        await maybe_path_above(state, settings=settings, path=new_path)
                        or state
                    )
                    paths = ancestors(new_path)
                    index = state.index | paths
                    next_state = await forward(
                        new_state, settings=settings, index=index, paths=paths
                    )
                    await kill_buffers(
                        last_used=new_state.window_order,
                        paths={node.path},
                        reopen={node.path: new_path},
                    )
                    await lsp_moved(operations)
                    return Stage(next_state, focus=new_path)
