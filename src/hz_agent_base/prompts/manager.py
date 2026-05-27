"""PromptManager — 从目录加载 Markdown 文件并组装为最终提示词。"""

from __future__ import annotations

from pathlib import Path


class PromptManager:
    """提示词管理器，负责从文件系统加载提示词和规则。

    目录约定：
        <prompt_dir>/
        ├── base.md           # 基础人设（必须）
        └── rules/            # 规则目录（可选）
            ├── safety.md
            └── format.md

    组装顺序：base.md + rules/*.md（按文件名字母序）

    使用方式：
        # 从目录加载
        pm = PromptManager("./prompts/coordinator/")
        prompt = pm.build()

        # 从单个文件加载
        pm = PromptManager.from_file("./prompts/base.md")
        prompt = pm.build()

        # 叠加共享规则
        pm = PromptManager("./prompts/coordinator/", shared_rules=["./prompts/shared/rules/"])
        prompt = pm.build()
    """

    def __init__(
        self,
        prompt_dir: str | Path,
        *,
        shared_rules: list[str | Path] | None = None,
    ):
        """初始化 PromptManager。

        Args:
            prompt_dir: 提示词目录，包含 base.md 和可选的 rules/ 子目录。
            shared_rules: 共享规则目录列表，追加到 agent 自身规则之后。
        """
        self.prompt_dir = Path(prompt_dir)
        self.shared_rules = [Path(p) for p in (shared_rules or [])]

    @classmethod
    def from_file(cls, file_path: str | Path, **kwargs) -> PromptManager:
        """从单个文件创建 PromptManager。

        自动将文件所在目录作为 prompt_dir，并将文件重命名为 base.md 语义。
        如果文件就在某个目录下，直接用该目录。
        """
        file_path = Path(file_path)
        if file_path.is_file():
            # 创建临时目录结构的 PromptManager，但用文件本身作为 base
            pm = cls.__new__(cls)
            pm.prompt_dir = file_path.parent
            pm._base_file_override = file_path
            pm.shared_rules = [Path(p) for p in (kwargs.get("shared_rules") or [])]
            return pm
        return cls(file_path, **kwargs)

    def build(self) -> str:
        """组装最终提示词。

        Returns:
            拼接后的完整提示词字符串。
        """
        parts: list[str] = []

        # 1. 加载 base 提示词
        base_content = self._load_base()
        if base_content:
            parts.append(base_content)

        # 2. 加载 agent 自身规则
        agent_rules = self._load_rules_from_dir(self.prompt_dir / "rules")
        if agent_rules:
            parts.append(agent_rules)

        # 3. 加载共享规则
        for shared_dir in self.shared_rules:
            shared_rules = self._load_rules_from_dir(shared_dir)
            if shared_rules:
                parts.append(shared_rules)

        return "\n\n".join(parts)

    def _load_base(self) -> str:
        """加载 base.md 基础提示词。"""
        # 如果有文件覆盖（from_file 模式）
        override = getattr(self, "_base_file_override", None)
        if override and override.exists():
            return override.read_text(encoding="utf-8").strip()

        # 正常模式：查找 base.md
        base_file = self.prompt_dir / "base.md"
        if base_file.exists():
            return base_file.read_text(encoding="utf-8").strip()

        return ""

    def _load_rules_from_dir(self, rules_dir: Path) -> str:
        """从规则目录加载所有 .md 文件，按文件名字母序排列。

        Args:
            rules_dir: 规则目录路径。

        Returns:
            拼接后的规则文本。每条规则带文件名作为标题。
        """
        if not rules_dir.exists() or not rules_dir.is_dir():
            return ""

        # 只读取 .md 文件，按文件名排序
        md_files = sorted(rules_dir.glob("*.md"))
        if not md_files:
            return ""

        parts = []
        for f in md_files:
            content = f.read_text(encoding="utf-8").strip()
            if content:
                parts.append(content)

        return "\n\n".join(parts)


def load_prompt(
    source: str | Path | None,
    *,
    shared_rules: list[str | Path] | None = None,
) -> str:
    """便捷函数：加载提示词。

    支持三种输入：
    - None → 返回空字符串
    - 普通字符串（不含路径分隔符）→ 直接返回
    - 文件/目录路径 → 通过 PromptManager 加载

    Args:
        source: 提示词来源（字符串或路径）。
        shared_rules: 共享规则目录列表。

    Returns:
        组装后的提示词。
    """
    if source is None:
        return ""

    source_str = str(source)

    # 判断是否为文件路径：存在文件/目录，或包含路径分隔符且以 .md 结尾
    source_path = Path(source_str)

    if source_path.is_dir():
        return PromptManager(source_path, shared_rules=shared_rules).build()

    if source_path.is_file():
        return PromptManager.from_file(source_path, shared_rules=shared_rules).build()

    # 如果看起来像路径（包含 / 或 \ 且以 .md 结尾），但文件不存在，报警告
    if (("/" in source_str or "\\" in source_str) and source_str.endswith(".md")):
        # 看起来像路径但不存在，返回原字符串
        return source_str

    # 普通字符串，直接返回
    return source_str
