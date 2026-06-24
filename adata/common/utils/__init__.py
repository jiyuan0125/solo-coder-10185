# -*- coding: utf-8 -*-
"""
@desc: readme
@author: 1nchaos
@time: 2023/3/29
@log: change log

NOTE: ``requests`` here is adata's own SunRequests wrapper (with retry/wait/proxy support),
not the raw ``requests`` library. Import as::

    from adata.common.utils import requests
    # or
    from adata.common import requests
"""
from .snowflake import worker
from .sunrequests import sun_requests as requests


