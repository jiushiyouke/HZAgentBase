"""Knowledge base protocol - 定义检索接口，不绑定具体实现。"""

from .protocol import Retriever, RetrievalResult

__all__ = ["Retriever", "RetrievalResult"]
