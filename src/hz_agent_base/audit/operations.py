"""文件审计 — 类型定义。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FileOperation:
    """单次文件操作记录。

    Attributes:
        timestamp: 操作时间。
        tool_name: 工具名称。
        file_path: 操作的文件路径。
        operation: 操作类型（read / write / edit / delete）。
        thread_id: 线程标识。
        diff: 变更内容（写入/编辑时记录）。
        success: 是否成功。
    """

    timestamp: str
    tool_name: str
    file_path: str
    operation: str
    thread_id: str = ""
    diff: str = ""
    success: bool = True


# 需要审计的文件操作工具名
FILE_TOOLS = {
    "write_file", "edit_file", "read_file",
    "create_file", "delete_file", "rename_file",
    "remove_file", "move_file",
    "write", "edit", "read",
}


def classify_operation(tool_name: str) -> str:
    """根据工具名判断操作类型。"""
    if "write" in tool_name or "create" in tool_name:
        return "write"
    if "edit" in tool_name:
        return "edit"
    if "read" in tool_name:
        return "read"
    if "delete" in tool_name or "remove" in tool_name:
        return "delete"
    if "rename" in tool_name or "move" in tool_name:
        return "rename"
    return "other"
