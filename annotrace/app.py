"""Annotrace — label agent traces, step by step.

The navigation is declared here rather than left to the pages/ convention, so
the sidebar shows the four steps of the work and not the entry script.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st          # noqa: E402

from core import ui             # noqa: E402

st.set_page_config(page_title="Annotrace", page_icon="◆", layout="wide")
ui.brand()

nav = st.navigation([
    st.Page("views/traces.py", title="Traces", default=True),
    st.Page("views/questions.py", title="Questions"),
    st.Page("views/annotate.py", title="Annotate"),
    st.Page("views/review.py", title="Review"),
    st.Page("views/compare.py", title="Compare"),
])
nav.run()
