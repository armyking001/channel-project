import os, sys
_here = os.path.dirname(os.path.abspath(__file__))
for _name in ('site_pkg', '.venv_local_new_pkgs'):
    _p = os.path.join(_here, _name)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.append(_p)
