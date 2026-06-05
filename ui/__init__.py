"""UI 模块化拆分（单文件部署，源码分层）。

main.py 里用：
    from ui import HTML_PAGE
"""
from ui._head import HEAD
from ui._styles import STYLES
from ui._body import BODY
from ui._app import APP_JS

HTML_PAGE = HEAD + "<style>" + STYLES + "</style>" + BODY + "<script>" + APP_JS + "</script>\n</body>\n</html>"
