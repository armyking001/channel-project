"""wrapper: inject backend/site_pkg + .venv_local_new_pkgs into sys.path, then run uvicorn

Resolution order (front-of-path wins):
  1. backend/site_pkg                    (project-provided prebuilt pkgs, requires Python 3.12)
  2. backend/.venv_local_new_pkgs       (临时用 pip --target 安装的新包，适用于 Python 3.11)
  3. backend/                           (源码路径)

如果 site_pkg 中的 C 扩展（pydantic_core 等）版本对不上，import 会失败；
wrapper 会在 import 阶段做兜底：如果 site_pkg 在前导致 import 失败，自动移除并重试。

Usage: 直接由 boot.bat 调用
"""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE_PKG = os.path.join(ROOT, 'site_pkg')
EXTRA_PKGS = os.path.join(ROOT, '.venv_local_new_pkgs')


def _inject(path):
    if os.path.exists(path) and path not in sys.path:
        sys.path.insert(0, path)


# 默认先 site_pkg（项目自带），再 EXTRA_PKGS（兜底），再 ROOT
_inject(SITE_PKG)
_inject(EXTRA_PKGS)
_inject(ROOT)


def _try_import_app():
    """尝试导入 app.main，失败时剥掉 site_pkg 再试一次。"""
    try:
        from app.main import app  # noqa: F401
        return app
    except Exception as exc:
        if SITE_PKG in sys.path:
            print(f"[boot_wrapper] 第一次 import 失败 ({type(exc).__name__}: {exc})，"
                  f"移除 site_pkg 后重试", flush=True)
            traceback.print_exc()
            sys.path.remove(SITE_PKG)
            try:
                from app.main import app  # noqa: F401
                return app
            except Exception as exc2:
                print(f"[boot_wrapper] 第二次 import 也失败: {exc2}", flush=True)
                traceback.print_exc()
                raise
        raise


app = _try_import_app()

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get('PORT', '8765'))
    uvicorn.run(app, host='0.0.0.0', port=port)