"""finrag — RAG over Apple's FY2025 10-K.

Pipeline, one module per step:
    parse -> chunk -> index -> retrieve -> generate
"""
import warnings

# Carried over from explore.py so behavior is unchanged: silences library warnings.
# Worth narrowing later to the specific warning it was added for.
warnings.filterwarnings("ignore")
