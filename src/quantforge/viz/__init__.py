"""Interactive Plotly charts for all quantforge models (``pip install "quantforge[viz]"``).

Use :func:`show` (or ``fig.show(config=PLOTLY_CONFIG)``) for mouse-wheel zoom and drag-to-pan.
"""

from . import theme
from .advanced import *  # noqa: F403
from .advanced import __all__ as _adv_all
from .charts import *  # noqa: F403
from .charts import __all__ as _charts_all
from .pro import *  # noqa: F403
from .pro import __all__ as _pro_all
from .theme import PLOTLY_CONFIG, show

__all__ = ["theme", "show", "PLOTLY_CONFIG", *_charts_all, *_adv_all, *_pro_all]
