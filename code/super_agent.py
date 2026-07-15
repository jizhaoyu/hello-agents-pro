"""
Unified Super Agent

This module provides the local-only learning assistant used by the shared site.
It deliberately avoids external AI services and executable chapter adapters.
"""

from __future__ import annotations

import ast
import json
import math
import operator
import re
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


@dataclass
class AgentStep:
    title: str
    detail: str
    status: str = "ok"


@dataclass
class Capability:
    id: str
    name: str
    category: str
    description: str
    keywords: List[str]
    origin: str
    version: str = "1.0"
    upgradeable: bool = False
    handler: Optional[Callable[[str, "SuperAgent"], Dict[str, Any]]] = None

    def public_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "keywords": self.keywords,
            "origin": self.origin,
            "version": self.version,
            "upgradeable": self.upgradeable,
        }


class SafeCalculator:
    """Small arithmetic evaluator for learning demos."""

    MAX_EXPRESSION_LENGTH = 100
    MAX_ABSOLUTE_VALUE = 1_000_000_000_000

    OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    @classmethod
    def evaluate(cls, expression: str) -> Any:
        if len(expression) > cls.MAX_EXPRESSION_LENGTH:
            raise ValueError("表达式过长")
        tree = ast.parse(expression, mode="eval")
        return cls._eval(tree.body)

    @classmethod
    def _eval(cls, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            if not math.isfinite(node.value) or abs(node.value) > cls.MAX_ABSOLUTE_VALUE:
                raise ValueError("数字超出允许范围")
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in cls.OPS:
            result = cls.OPS[type(node.op)](cls._eval(node.left), cls._eval(node.right))
            if not isinstance(result, (int, float)) or not math.isfinite(result) or abs(result) > cls.MAX_ABSOLUTE_VALUE:
                raise ValueError("计算结果超出允许范围")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in cls.OPS:
            result = cls.OPS[type(node.op)](cls._eval(node.operand))
            if abs(result) > cls.MAX_ABSOLUTE_VALUE:
                raise ValueError("计算结果超出允许范围")
            return result
        raise ValueError("只支持数字和基础四则运算")


class AgentMemory:
    """In-memory context for the current local server session."""

    def __init__(self):
        self.short_term = deque(maxlen=12)
        self.long_term = {
            "facts": {},
            "preferences": {},
        }

    def remember_turn(self, user_msg: str, agent_msg: str, capability: str) -> None:
        self.short_term.append({
            "user": user_msg,
            "agent": agent_msg,
            "capability": capability,
            "time": datetime.now().isoformat(timespec="seconds"),
        })
        self._extract_profile(user_msg)

    def _extract_profile(self, message: str) -> None:
        name_match = re.search(r"(?:我叫|我是|名字是)\s*([\u4e00-\u9fa5A-Za-z0-9_\-]{1,16})", message)
        if name_match:
            self.long_term["facts"]["user_name"] = name_match.group(1)

        if "我喜欢" in message:
            self.long_term["preferences"]["interest"] = message

    def context(self, query: str) -> str:
        parts = []
        facts = self.long_term.get("facts", {})
        if facts:
            parts.append("用户事实: " + "；".join(f"{k}={v}" for k, v in facts.items()))
        recent = list(self.short_term)[-4:]
        if recent:
            parts.append("最近对话:")
            for turn in recent:
                parts.append(f"- 用户: {turn['user']}")
                parts.append(f"  助手: {turn['agent'][:120]}")
        parts.append(f"当前输入: {query}")
        return "\n".join(parts)


class SuperAgent:
    """One platform agent composed from all available course capabilities."""

    def __init__(self):
        self.memory = AgentMemory()
        self.capabilities: Dict[str, Capability] = {}
        self.metrics = {
            "total_messages": 0,
            "total_time": 0.0,
            "errors": 0,
            "capability_calls": Counter(),
        }
        self._knowledge_base = self._default_knowledge()
        self._register_default_capabilities()

    def _register_default_capabilities(self) -> None:
        self.register(Capability(
            id="foundation",
            name="基础任务智能体",
            category="基础能力",
            description="TAO循环、天气查询、信息检索、简单计算和交互式任务处理。",
            keywords=["你好", "天气", "查询", "搜索", "计算", "tao", "基础"],
            origin="local learning tools",
            handler=_handle_foundation,
        ))
        self.register(Capability(
            id="reasoning_patterns",
            name="推理范式引擎",
            category="推理能力",
            description="自动选择 ReAct、Plan-and-Solve 或 Reflection 处理多步推理、规划和改进任务。",
            keywords=["react", "计划", "规划", "反思", "改进", "推理", "多步"],
            origin="local reasoning patterns",
            handler=_handle_reasoning,
        ))
        self.register(Capability(
            id="memory_tools_context",
            name="记忆工具上下文引擎",
            category="工程能力",
            description="整合长期记忆、短期记忆、工具调用、上下文压缩和性能监控。",
            keywords=["记住", "记忆", "工具", "上下文", "时间", "保存", "状态"],
            origin="local session memory",
            handler=_handle_memory_tools,
        ))
        self.register(Capability(
            id="learning_assistant",
            name="AI学习助手",
            category="学习能力",
            description="面向编程学习的知识解释、代码学习建议和学习进度记录。",
            keywords=["python", "变量", "函数", "列表", "学习", "代码", "智能体", "llm", "agent"],
            origin="local course knowledge",
            handler=_handle_learning,
        ))

    def register(self, capability: Capability) -> None:
        self.capabilities[capability.id] = capability

    def _default_knowledge(self) -> List[Dict[str, str]]:
        return [
            {
                "topic": "智能体",
                "content": "智能体由感知、思考、行动和观察闭环构成，可以通过工具和记忆持续完成任务。",
                "keywords": "智能体 agent tao 感知 思考 行动 观察",
            },
            {
                "topic": "ReAct",
                "content": "ReAct 将推理和行动交替执行，适合需要边查边判断的多步任务。",
                "keywords": "react 推理 行动 多步 工具",
            },
            {
                "topic": "Plan-and-Solve",
                "content": "Plan-and-Solve 先拆解计划，再逐步执行，适合目标清晰、步骤可预期的任务。",
                "keywords": "计划 规划 plan solve 分解",
            },
            {
                "topic": "Reflection",
                "content": "Reflection 会先产出结果，再自评问题并迭代改进，适合质量要求较高的输出。",
                "keywords": "反思 reflection 改进 评估 质量",
            },
            {
                "topic": "记忆系统",
                "content": "生产级智能体通常同时使用工作记忆、短期记忆和长期记忆，并按重要性压缩上下文。",
                "keywords": "记忆 工作记忆 短期记忆 长期记忆 上下文",
            },
            {
                "topic": "工具管理",
                "content": "工具管理负责注册工具、校验参数、重试失败调用并记录执行统计。",
                "keywords": "工具 注册 参数 校验 重试 统计",
            },
            {
                "topic": "上下文优化",
                "content": "上下文优化通过 token 预算、重要性评分和历史摘要，保留当前任务最相关的信息。",
                "keywords": "上下文 token 摘要 重要性 优化",
            },
            {
                "topic": "Python函数",
                "content": "Python 函数使用 def 定义，用参数接收输入，用 return 返回结果。",
                "keywords": "python 函数 def return 参数",
            },
            {
                "topic": "Python变量",
                "content": "变量是对象的引用，用于给数据命名。Python 中变量无需提前声明类型。",
                "keywords": "python 变量 对象 引用 类型",
            },
        ]

    def chat(self, message: str, mode: str = "auto") -> Dict[str, Any]:
        start = time.time()
        query = (message or "").strip()
        if not query:
            return {"success": False, "error": "请输入问题"}

        capability = self._select_capability(query, mode)
        steps = [
            AgentStep("输入归一化", f"收到 {len(query)} 个字符"),
            AgentStep("能力选择", f"{capability.name} ({capability.id})"),
        ]
        try:
            if not capability.handler:
                raise RuntimeError(f"能力 {capability.id} 没有处理器")
            payload = capability.handler(query, self)
            answer = payload.get("answer", "")
            steps.extend(payload.get("steps", []))
            elapsed = time.time() - start
            quality = self._score_answer(answer, query)
            self.memory.remember_turn(query, answer, capability.id)
            self.metrics["total_messages"] += 1
            self.metrics["total_time"] += elapsed
            self.metrics["capability_calls"][capability.id] += 1
            return {
                "success": True,
                "answer": answer,
                "capability": capability.public_dict(),
                "steps": [step.__dict__ if isinstance(step, AgentStep) else step for step in steps],
                "quality": round(quality, 2),
                "elapsed_sec": round(elapsed, 3),
                "mode": mode,
                "used_real_ai": payload.get("used_real_ai", False),
            }
        except Exception as exc:
            elapsed = time.time() - start
            self.metrics["errors"] += 1
            return {
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
                "capability": capability.public_dict(),
                "elapsed_sec": round(elapsed, 3),
                "steps": [step.__dict__ if isinstance(step, AgentStep) else step for step in steps],
            }

    def _select_capability(self, query: str, mode: str) -> Capability:
        if mode and mode != "auto" and mode in self.capabilities:
            return self.capabilities[mode]

        normalized = query.lower()
        if any(word in query for word in ["计划", "规划", "反思", "改进", "质量", "ReAct", "react", "多步"]):
            return self.capabilities["reasoning_patterns"]
        if any(word in query for word in ["记住", "记得", "上下文", "保存", "工具", "现在几点", "时间", "计算"]):
            return self.capabilities["memory_tools_context"]
        if _extract_expression(query):
            return self.capabilities["memory_tools_context"]
        if any(word in normalized for word in ["python", "agent", "llm", "gpt"]) or any(word in query for word in ["变量", "函数", "列表", "学习", "代码", "智能体"]):
            return self.capabilities["learning_assistant"]
        return self.capabilities["foundation"]

    def _score_answer(self, answer: str, query: str) -> float:
        score = 0.55
        if len(answer) > 20:
            score += 0.15
        if any(mark in answer for mark in ["结果", "建议", "步骤", "计划", "记住"]):
            score += 0.15
        if query and any(token in answer for token in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", query)[:3]):
            score += 0.1
        if "抱歉" not in answer and "失败" not in answer:
            score += 0.05
        return min(score, 1.0)

    def status(self) -> Dict[str, Any]:
        total = self.metrics["total_messages"]
        avg_time = self.metrics["total_time"] / total if total else 0.0
        return {
            "name": "超级智能体平台",
            "version": "2.0",
            "capabilities": [cap.public_dict() for cap in self.capabilities.values()],
            "memory": {
                "short_term_turns": len(self.memory.short_term),
                "session_facts": len(self.memory.long_term.get("facts", {})),
                "session_preferences": len(self.memory.long_term.get("preferences", {})),
            },
            "metrics": {
                "total_messages": total,
                "avg_time_sec": round(avg_time, 3),
                "errors": self.metrics["errors"],
                "capability_calls": dict(self.metrics["capability_calls"]),
            },
        }

    def search_knowledge(self, query: str) -> List[Dict[str, str]]:
        entries = list(self._knowledge_base)

        query_words = set(self._keywords_from_text(query))
        ranked = []
        for entry in entries:
            haystack = f"{entry.get('topic', '')} {entry.get('keywords', '')} {entry.get('content', '')}".lower()
            score = sum(1 for word in query_words if word.lower() in haystack)
            if score:
                ranked.append((score, entry))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [entry for _, entry in ranked[:4]]

    @staticmethod
    def _keywords_from_text(text: str) -> List[str]:
        words = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fa5]{2,}", text)
        common = {"这个", "一个", "可以", "进行", "以及", "通过", "使用", "支持"}
        result = []
        for word in words:
            if word not in common and word.lower() not in common:
                result.append(word)
        return list(dict.fromkeys(result))[:16]


def _extract_expression(query: str) -> Optional[str]:
    match = re.search(r"([-+*/().\d\s]+)", query)
    if not match:
        return None
    expr = match.group(1).strip()
    return expr if re.search(r"\d", expr) and re.search(r"[-+*/]", expr) else None


def _handle_foundation(query: str, agent: SuperAgent) -> Dict[str, Any]:
    steps = [AgentStep("TAO 思考", "判断问题是否需要本地工具或知识检索")]
    expression = _extract_expression(query)
    if expression:
        result = SafeCalculator.evaluate(expression)
        steps.append(AgentStep("TAO 行动", f"calculate({expression})"))
        return {"answer": f"计算结果：{expression} = {result}", "steps": steps}

    weather = {
        "北京": "晴天，气温26℃，微风",
        "上海": "多云，气温22℃，东南风",
        "深圳": "晴天，气温28℃，空气质量优",
        "广州": "小雨，气温24℃，湿度较大",
        "杭州": "阴天，气温20℃，西风",
    }
    if "天气" in query:
        city = next((name for name in weather if name in query), None)
        answer = weather[city] if city else "请告诉我想查询哪个城市的示例天气。"
        steps.append(AgentStep("TAO 行动", "查询本地示例天气数据"))
        return {"answer": answer, "steps": steps}

    matches = agent.search_knowledge(query)
    answer = matches[0]["content"] if matches else "我是本地学习助手，可以解释智能体概念、比较推理范式、做基础计算和记录本次会话信息。"
    steps.append(AgentStep("TAO 观察", f"本地知识命中 {len(matches)} 条"))
    return {"answer": answer, "steps": steps}


def _handle_reasoning(query: str, agent: SuperAgent) -> Dict[str, Any]:
    steps = []
    if any(word in query for word in ["计划", "规划", "Plan", "plan"]):
        if "学习" in query or "智能体" in query or "Agent" in query:
            matches = agent.search_knowledge(query)
            knowledge_lines = "\n".join(f"- {item['topic']}：{item['content']}" for item in matches[:3])
            answer = (
                "计划：\n"
                "1. 先跑通基础任务智能体，理解感知-思考-行动-观察闭环。\n"
                "2. 再分别练习 ReAct、Plan-and-Solve、Reflection，比较它们适合的任务形态。\n"
                "3. 把记忆、工具、上下文优化和评估接到同一个运行时中。\n"
                "4. 后续章节用知识包升级，不再新建章节入口。\n\n"
                f"已参考知识：\n{knowledge_lines or '- 当前知识库没有额外命中'}"
            )
            steps.append(AgentStep("Plan-and-Solve", "平台生成统一学习路线"))
            return {"answer": answer, "steps": steps}

        answer = "计划：\n1. 明确目标和完成标准。\n2. 拆成可验证的小步骤。\n3. 逐步执行并记录结果。\n4. 检查偏差并调整计划。"
        steps.append(AgentStep("Plan-and-Solve", "生成本地通用任务计划"))
    elif any(word in query for word in ["反思", "改进", "质量", "Reflection", "reflection"]):
        answer = "反思框架：\n1. 先写出当前方案。\n2. 对照目标检查正确性、完整性和清晰度。\n3. 找出最影响质量的问题。\n4. 只针对关键问题迭代一次，再复核。"
        steps.append(AgentStep("Reflection", "提供本地质量复盘框架"))
    else:
        if "智能体" in query or "Agent" in query or "agent" in query:
            matches = agent.search_knowledge(query)
            answer = "ReAct路径：\nThought: 先检索智能体核心概念。\nAction: search_knowledge(\"智能体\")\nObservation: "
            answer += matches[0]["content"] if matches else "智能体是感知环境并自主行动的系统。"
            answer += "\nThought: 已获得定义，可以给出回答。\nAction: Finish[智能体通过感知、推理、工具行动和记忆持续完成任务。]"
            steps.append(AgentStep("ReAct", "使用平台知识库补足旧示例关键词"))
            return {"answer": answer, "steps": steps}

        answer = "ReAct路径：\nThought: 识别问题目标与缺失信息。\nAction: 检索本地学习知识。\nObservation: 根据检索结果补充上下文。\nAction: Finish[形成简洁、可验证的回答。]"
        steps.append(AgentStep("ReAct", "展示本地推理与行动循环"))

    return {"answer": answer, "steps": steps}


def _handle_memory_tools(query: str, agent: SuperAgent) -> Dict[str, Any]:
    steps = [AgentStep("上下文优化", agent.memory.context(query)[:300])]

    if any(word in query for word in ["记住", "我叫", "我是", "名字"]):
        agent.memory._extract_profile(query)
        facts = agent.memory.long_term.get("facts", {})
        answer = "已更新长期记忆。" + (f" 当前记住的信息：{facts}" if facts else "")
        steps.append(AgentStep("会话记忆", "仅在本次服务运行期间保存用户事实"))
        return {"answer": answer, "steps": steps}

    if any(word in query for word in ["记得", "你知道我", "我的名字"]):
        facts = agent.memory.long_term.get("facts", {})
        answer = f"我当前记住的信息：{facts}" if facts else "目前还没有长期事实记忆。"
        steps.append(AgentStep("记忆检索", "读取长期记忆"))
        return {"answer": answer, "steps": steps}

    expression = _extract_expression(query)
    if expression:
        result = SafeCalculator.evaluate(expression)
        steps.append(AgentStep("工具调用", f"calculate({expression})"))
        return {"answer": f"计算结果：{expression} = {result}", "steps": steps}

    if "时间" in query or "几点" in query:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        steps.append(AgentStep("工具调用", "get_current_time()"))
        return {"answer": f"当前时间：{now}", "steps": steps}

    if "状态" in query or "统计" in query:
        status = agent.status()
        steps.append(AgentStep("性能监控", "读取平台状态与调用统计"))
        return {"answer": json.dumps(status["metrics"], ensure_ascii=False, indent=2), "steps": steps}

    return {
        "answer": "我已经接入记忆、工具、上下文和监控能力。可以让我记住信息、计算、查时间或查看状态。",
        "steps": steps,
    }


def _handle_learning(query: str, agent: SuperAgent) -> Dict[str, Any]:
    matches = agent.search_knowledge(query)
    steps = [AgentStep("知识检索", f"命中 {len(matches)} 条知识")]
    if not matches:
        return {
            "answer": "当前本地知识库没有直接命中。可以换一个更具体的课程关键词再试。",
            "steps": steps,
        }

    lines = ["我把相关知识整合成统一回答："]
    for item in matches:
        lines.append(f"- {item['topic']}：{item['content']}")

    if "怎么" in query or "如何" in query or "学习" in query:
        lines.append("建议路径：先理解概念，再运行一个最小例子，最后让智能体用工具或反思能力检查结果。")
    return {"answer": "\n".join(lines), "steps": steps}


_AGENT_INSTANCE: Optional[SuperAgent] = None


def get_super_agent() -> SuperAgent:
    global _AGENT_INSTANCE
    if _AGENT_INSTANCE is None:
        _AGENT_INSTANCE = SuperAgent()
    return _AGENT_INSTANCE
