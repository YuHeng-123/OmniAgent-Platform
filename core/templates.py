"""
OmniAgent Platform - Jinja2 模板配置模块
"""

import os

from fastapi.templating import Jinja2Templates

from core.config import BASE_DIR

os.makedirs(os.path.join(BASE_DIR, "templates"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)

templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))
