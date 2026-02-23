from __future__ import annotations

import os
import runpy
import sys
from contextlib import contextmanager
from pathlib import Path

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent


@contextmanager
def _app_exec_context(app_dir: Path):
    prev_cwd = Path.cwd()
    old_sys_path = list(sys.path)
    try:
        os.chdir(app_dir)
        sys.path.insert(0, str(app_dir))
        yield
    finally:
        os.chdir(prev_cwd)
        sys.path[:] = old_sys_path


def run_legacy_app(app_dir_name: str, app_file: str = "app.py") -> None:
    app_dir = ROOT_DIR / app_dir_name
    app_path = app_dir / app_file
    if not app_path.exists():
        st.error(f"Missing app file: {app_path}")
        st.stop()

    with _app_exec_context(app_dir):
        runpy.run_path(str(app_path), run_name="__main__")


def clear_all_state() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.clear()


def switch_to(page_path: str) -> None:
    clear_all_state()
    st.switch_page(page_path)


def render_app_switcher(current_label: str) -> None:
    with st.sidebar:
        st.divider()
        st.subheader("Switch App")
        st.caption(f"Current: {current_label}")
        if st.button("Exit Current App", use_container_width=True, type="primary"):
            switch_to("app.py")
        st.divider()
        if st.button("Go to Hub", use_container_width=True):
            switch_to("app.py")
        if st.button("Go to Chinese", use_container_width=True):
            switch_to("pages/01_Chinese.py")
        if st.button("Go to Spanish", use_container_width=True):
            switch_to("pages/02_Spanish.py")
        if st.button("Go to MVC", use_container_width=True):
            switch_to("pages/03_MVC.py")
