from __future__ import annotations

import asyncio
from io import BytesIO
import json
import html
import os
import random
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

import httpx
from pypdf import PdfReader
from nonebot import get_bots, get_driver, on_message, on_regex
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.log import logger
from nonebot.rule import to_me
from nonebot_plugin_apscheduler import scheduler

ARK_RESPONSES_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
REFERENCE_LINKS = (
    "https://pytorch.org/blog/",
    "https://huggingface.co/blog",
    "https://deepmind.google/discover/blog/",
    "https://www.deeplearning.ai/the-batch/",
    "https://arxiv.org/",
    "https://rss.arxiv.org/",
)
REFERENCE_DOMAINS = (
    "openai.com",
    "blog.google",
    "microsoft.com",
    "developer.nvidia.com",
    "pytorch.org",
    "huggingface.co",
    "deepmind.google",
    "deeplearning.ai",
    "arxiv.org",
    "rss.arxiv.org",
    "github.com",
    "docs.python.org",
    "python.org",
    "ocw.mit.edu",
    "stanford.edu",
    "berkeley.edu",
    "cmu.edu",
    "d2l.ai",
    "realpython.com",
)
SOURCE_FEEDS = (
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("Google AI", "https://blog.google/technology/ai/rss/"),
    ("Microsoft Research", "https://www.microsoft.com/en-us/research/feed/"),
    ("NVIDIA Technical Blog", "https://developer.nvidia.com/blog/category/artificial-intelligence/feed/"),
    ("Hugging Face", "https://huggingface.co/blog/feed.xml"),
    ("arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI"),
    ("arXiv cs.LG", "https://rss.arxiv.org/rss/cs.LG"),
    ("arXiv cs.CL", "https://rss.arxiv.org/rss/cs.CL"),
    ("通义千问 Qwen", "https://github.com/QwenLM/Qwen3/releases.atom"),
    ("百度飞桨 PaddlePaddle", "https://github.com/PaddlePaddle/Paddle/releases.atom"),
    ("智谱 GLM", "https://github.com/THUDM/GLM-4/releases.atom"),
    ("面壁智能 MiniCPM", "https://github.com/OpenBMB/MiniCPM/releases.atom"),
    ("RAGFlow", "https://github.com/infiniflow/ragflow/releases.atom"),
    ("InternLM", "https://github.com/InternLM/InternLM/releases.atom"),
    ("ModelScope", "https://github.com/modelscope/modelscope/releases.atom"),
)
SOURCE_DOCUMENTS = (
    ("Dive into Deep Learning 教材", "https://d2l.ai/d2l-en.pdf", "教材 PDF"),
    ("Stanford CS229 机器学习讲义", "https://cs229.stanford.edu/notes2021spring/notes2021spring/lecture1.pdf", "课程讲义 PDF"),
    ("MIT 6.100L Python 课程讲义", "https://ocw.mit.edu/courses/6-100l-introduction-to-cs-and-programming-using-python-fall-2022/mit6_100l_f22_lec01.pdf", "课程讲义 PDF"),
    ("MIT 6.100L Python 课程文字讲义", "https://ocw.mit.edu/courses/6-100l-introduction-to-cs-and-programming-using-python-fall-2022/resources/6100l-lecture-2-multi-version-4_1_transcript_pdf/", "课程讲义 PDF"),
    ("Python 官方教程", "https://docs.python.org/3/tutorial/", "官方学习网站"),
    ("Python PEP 8 官方规范", "https://peps.python.org/pep-0008/", "官方学习网站"),
    ("Harvard CS50P Python 课程总览", "https://cs50.harvard.edu/python/courses/", "本科课程网站"),
    ("Harvard CS50P Week 0 函数与变量", "https://cs50.harvard.edu/python/weeks/0/", "本科课程网站"),
    ("Harvard CS50P Week 2 循环", "https://cs50.harvard.edu/python/weeks/2/", "本科课程网站"),
    ("Harvard CS50P Week 6 文件 I/O", "https://cs50.harvard.edu/python/weeks/6/", "本科课程网站"),
    ("Harvard CS50P Week 8 面向对象", "https://cs50.harvard.edu/python/weeks/8/", "本科课程网站"),
    ("scikit-learn 用户指南", "https://scikit-learn.org/stable/user_guide.html", "官方学习网站"),
    ("PyTorch 官方教程", "https://pytorch.org/tutorials/", "官方学习网站"),
    ("Real Python 教程", "https://realpython.com/tutorials/all/", "技术博客"),
)
UNDERGRADUATE_TOPICS = (
    "Python 基础与工程习惯",
    "数据结构与算法",
    "概率统计与机器学习",
    "线性代数与神经网络",
    "深度学习训练与泛化",
    "Transformer 与大语言模型",
    "计算机系统与 AI 算力",
    "软件工程与 AI 项目实践",
)
BLOCKED_TERMS = (
    "制作爆炸物",
    "制造武器步骤",
    "窃取密码",
    "盗取账号",
    "绕过身份验证",
    "毒品交易",
    "身份证号码",
    "银行卡号码",
    "获取他人验证码",
)
ADVANCED_TOPICS = (
    "缩放定律与算力最优训练",
    "Transformer 的残差流与归一化位置",
    "混合专家模型的路由与负载均衡",
    "推理阶段的 KV Cache 与显存复杂度",
    "检索增强生成中的召回率与上下文污染",
    "偏好优化中的 DPO 与奖励模型",
    "模型量化中的误差传播与校准",
    "扩散模型的前向加噪与反向去噪",
    "视觉语言模型的跨模态对齐",
    "强化学习中的离策略估计",
    "对比学习与表示坍塌",
    "长上下文中的位置编码外推",
    "推测解码与大模型推理加速",
    "分布偏移与不确定性校准",
    "LoRA 的低秩假设与可训练参数效率",
    "AI Agent 的工具调用、规划与错误恢复",
    "开源模型生态与模型许可证",
    "AI 芯片、显存带宽与推理成本",
    "具身智能与机器人策略学习",
    "生成式 AI 的版权与数据治理",
    "AI 隐私保护与数据最小化",
    "模型安全评测与红队测试",
    "AI 产品的可靠性、成本与用户体验权衡",
    "AI 对软件工程与职业技能的影响",
    "医疗、教育和科研中的 AI 应用边界",
)
FALLBACK_KNOWLEDGE = (
    "📚 今日深度知识｜KV Cache 的真实代价\n\n"
    "自回归模型生成第 t 个 token 时，需要读取此前所有 token 的 Key 和 Value。KV Cache 避免重复计算，但显存占用会随层数、序列长度、批量大小和 KV 头数线性增长。多查询注意力（MQA）与分组查询注意力（GQA）的核心价值之一，就是让多个查询头共享更少的 KV 头，从而降低长上下文推理的带宽与显存压力。工程上，模型参数装得下并不代表长上下文一定跑得动，KV Cache 往往才是并发能力的瓶颈。",
    "📚 今日深度知识｜DPO 为什么不需要显式奖励模型\n\n"
    "DPO 将偏好数据中的“更好回答”和“较差回答”直接转化为策略模型相对参考模型的对数概率差，并使用分类式目标进行优化。它省去了单独训练奖励模型和在线强化学习的流程，但并不意味着没有偏好建模：偏好信号被隐式写进了损失函数。DPO 的效果仍依赖偏好数据质量、参考模型选择和温度系数，数据存在系统性偏差时，模型也会稳定地学到这种偏差。",
    "📚 今日深度知识｜RAG 的瓶颈通常不在生成\n\n"
    "RAG 系统回答错误时，首先要区分检索失败、排序失败、上下文组织失败和生成失败。如果正确文档根本没有进入候选集，继续优化提示词通常无效；如果候选集包含答案但排序靠后，应优先改进重排；如果上下文里同时存在冲突证据，则需要来源权重、时间过滤或引用约束。评估 RAG 时应拆分 Recall@K、重排质量、忠实度和最终答案正确率，而不是只看一个端到端分数。",
)

conversation_history: dict[tuple[int, int], deque[tuple[str, str]]] = defaultdict(lambda: deque(maxlen=6))
quiz_sessions: dict[int, dict[str, str]] = {}
last_request_at: dict[int, float] = {}
source_cache: tuple[float, str] | None = None
SOURCE_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".source_cache.json")
LOCAL_KB_INDEX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "knowledge_base", "index.json")
LOCAL_KB_STATE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "knowledge_base", "state.json")


def _group_ids() -> list[int]:
    return [int(value) for value in os.getenv("KNOWLEDGE_GROUP_IDS", "").split(",") if value.strip().isdigit()]


def _extract_output_text(response_data: dict[str, Any]) -> str:
    for output_item in response_data.get("output", []):
        if output_item.get("type") != "message":
            continue
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text" and content_item.get("text"):
                return str(content_item["text"]).strip()
    raise ValueError("方舟响应中没有 output_text")


def _validate_text(text: str, allow_links: bool = False) -> None:
    blocked_term = next((term for term in BLOCKED_TERMS if term in text), None)
    if blocked_term:
        raise ValueError(f"内容包含禁止词：{blocked_term}")
    urls = re.findall(r"https?://[^\s）)]+", text)
    if urls and not allow_links:
        raise ValueError("该回复不允许包含链接")
    invalid_url = next(
        (
            url
            for url in urls
            if not any(re.match(r"https?://([^/]*\.)?" + re.escape(domain) + r"(/|$)", url) for domain in REFERENCE_DOMAINS)
        ),
        None,
    )
    if invalid_url:
        raise ValueError(f"内容包含非白名单链接：{invalid_url}")


def _format_for_qq(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\\\\", "\\")
    text = re.sub(r"```(?:\w+)?\s*", "", text)
    text = text.replace("```", "")
    text = re.sub(r"(?m)^#{1,6}\s*", "", text)
    text = text.replace("**", "").replace("__", "").replace("`", "")
    text = text.replace("$$", "").replace("$", "")
    text = text.replace(r"\(", "").replace(r"\)", "").replace(r"\[", "").replace(r"\]", "")
    for _ in range(3):
        text = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
        text = re.sub(r"\\sqrt\{([^{}]+)\}", r"sqrt(\1)", text)
        text = re.sub(r"\\(?:text|mathrm|mathbf|operatorname)\{([^{}]+)\}", r"\1", text)
    replacements = {
        r"\left": "",
        r"\right": "",
        r"\cdot": "*",
        r"\times": "×",
        r"\top": "^T",
        r"\leq": "≤",
        r"\le": "≤",
        r"\geq": "≥",
        r"\ge": "≥",
        r"\approx": "≈",
        r"\Theta": "Θ",
        r"\sum": "Σ",
        r"\_": "_",
        r"\^": "^",
        r"\{": "{",
        r"\}": "}",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = re.sub(r"\\([A-Za-z]+)", r"\1", text)
    text = text.replace("^^T", "^T")
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    candidate = text[:max_chars]
    cut_at = max(candidate.rfind(mark) for mark in ("。", "！", "？", "\n"))
    if cut_at >= int(max_chars * 0.6):
        candidate = candidate[: cut_at + 1]
    return candidate.rstrip() + "…"


def _compact_knowledge(text: str, detailed: bool) -> str:
    if detailed:
        return _truncate_at_sentence(text, 1400)
    source_match = re.search(r"(?:\n|^)资料来源：\s*(https?://\S+)", text)
    source = source_match.group(1) if source_match else ""
    body = text[: source_match.start()].rstrip() if source_match else text
    body = _truncate_at_sentence(body, 650)
    return f"{body}\n\n资料来源：{source}" if source else body


def _source_url(source_material: str) -> str:
    source_match = re.search(r"(?:\n|^)来源：(https?://\S+)", source_material)
    if source_match is None:
        raise ValueError("资料输入缺少来源网址")
    return source_match.group(1)


def _evidence_candidates(source_material: str) -> list[str]:
    body_match = re.search(r"摘要：(.*)\n来源：https?://\S+", source_material, re.DOTALL)
    body = body_match.group(1) if body_match else source_material
    sentences = re.split(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+(?=[A-Z0-9])", body)
    candidates = []
    for sentence in sentences:
        sentence = re.sub(r"\s+", " ", sentence).strip(" -•\t")
        if 18 <= len(sentence) <= 90 and sentence not in candidates:
            candidates.append(sentence)
        elif len(sentence) > 90:
            clauses = re.split(r"(?<=[，,:：])\s*", sentence)
            candidates.extend(
                clause for clause in clauses if 18 <= len(clause) <= 90 and clause not in candidates
            )
    if len(candidates) < 2:
        chunks = [body[index : index + 80].strip() for index in range(0, min(len(body), 800), 80)]
        candidates.extend(chunk for chunk in chunks if len(chunk) >= 18 and chunk not in candidates)
    return candidates[:10]


def _validate_grounded_knowledge(text: str, source_material: str, evidence_candidates: list[str]) -> tuple[int, int]:
    if re.search(r"https?://", text):
        raise ValueError("模型输出不应自行填写网址")
    evidence_match = re.search(r"依据编号：\s*(\d+)\s*[,，]\s*(\d+)", text)
    if evidence_match is None:
        raise ValueError("输出缺少依据编号")
    evidence_indexes = tuple(int(value) - 1 for value in evidence_match.groups())
    if evidence_indexes[0] == evidence_indexes[1] or any(
        index < 0 or index >= len(evidence_candidates) for index in evidence_indexes
    ):
        raise ValueError("依据编号无效")

    quantitative_pattern = r"\d+(?:\.\d+)%|\d+\.\d+|\d+(?:\.\d+)?\s*(?:倍|万|亿|GB|MB|KB|ms|秒|分钟|小时|参数|样本|分)"
    source_numbers = set(re.findall(quantitative_pattern, source_material, re.IGNORECASE))
    summary_without_evidence_ids = re.sub(r"依据编号：[^\n]+", "", text)
    summary_without_practice = re.split(r"(?:最小示例|练习题|答案提示)：", summary_without_evidence_ids, maxsplit=1)[0]
    unsupported_numbers = {
        number
        for number in re.findall(quantitative_pattern, summary_without_practice, re.IGNORECASE)
        if number not in source_numbers
    }
    if unsupported_numbers:
        raise ValueError(f"输出包含原文未出现的数字：{', '.join(sorted(unsupported_numbers))}")
    return evidence_indexes


def _render_grounded_knowledge(text: str, source_material: str, evidence_candidates: list[str], detailed: bool) -> str:
    _validate_grounded_knowledge(text, source_material, evidence_candidates)
    body = re.sub(r"\n?依据编号：[^\n]+", "", text).strip()
    body = re.sub(r"(?m)^答案提示：.*$", "", body)
    body = re.sub(r"(?m)^适用边界：.*$", "", body)
    body = re.sub(r"(?m)^依据摘录[一二]：.*$", "", body)
    body = re.sub(
        r"(?m)^(标题|今天学什么|核心讲解|最小示例|常见误区|练习题)\s*[：:]?\s*$",
        r"\1：",
        body,
    )
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    body = _truncate_at_sentence(body, 1400 if detailed else 800)
    return f"{body}\n\n资料来源：{_source_url(source_material)}"


def _wants_detailed(question: str) -> bool:
    return bool(re.search(r"详细|展开|深入|深度|长文|系统讲|完整解释|全面分析", question))


def _input_is_safe(text: str) -> bool:
    return not any(term in text for term in BLOCKED_TERMS)


def _cooldown_remaining(user_id: int) -> int:
    cooldown = int(os.getenv("CHAT_COOLDOWN_SECONDS", "8"))
    remaining = cooldown - int(time.monotonic() - last_request_at.get(user_id, 0))
    if remaining <= 0:
        last_request_at[user_id] = time.monotonic()
        return 0
    return remaining


async def _call_ark(prompt: str, *, allow_links: bool = False, max_output_tokens: int = 700) -> str:
    api_key = os.getenv("ARK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ARK_API_KEY 未配置")
    request_data = {
        "model": os.getenv("ARK_MODEL", "doubao-seed-2-0-mini-260215"),
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "thinking": {"type": "disabled"},
        "max_output_tokens": max_output_tokens,
        "store": False,
    }
    timeout = float(os.getenv("ARK_TIMEOUT_SECONDS", "30"))
    started_at = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            ARK_RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=request_data,
        )
        response.raise_for_status()
        text = _extract_output_text(response.json())
        _validate_text(text, allow_links=allow_links)
        text = _format_for_qq(text)
        logger.info("方舟响应耗时：{:.2f}s，输出字符：{}", time.perf_counter() - started_at, len(text))
        return text


def _clean_feed_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(text))
    return re.sub(r"\s+", " ", text).strip()


def _extract_article_text(page: str) -> str:
    page = re.sub(
        r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>|<noscript\b[^>]*>.*?</noscript>",
        " ",
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    article_match = re.search(
        r"<(?:article|main)\b[^>]*>(.*?)</(?:article|main)>",
        page,
        flags=re.IGNORECASE | re.DOTALL,
    )
    content = article_match.group(1) if article_match else page
    content = re.sub(r"</?(?:p|h[1-6]|li|blockquote|br)\b[^>]*>", "\n", content, flags=re.IGNORECASE)
    return re.sub(r"\n{2,}", "\n", _clean_feed_text(content)).strip()[:6000]


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(BytesIO(content))
    text = "\n".join(page.extract_text() or "" for page in reader.pages[:12])
    return re.sub(r"\n{2,}", "\n", _clean_feed_text(text)).strip()[:12000]


def _first_node(entry: ET.Element, names: tuple[str, ...]) -> ET.Element | None:
    for name in names:
        node = entry.find(name)
        if node is not None:
            return node
    return None


async def _fetch_page_content(client: httpx.AsyncClient, url: str) -> str:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return _extract_article_text(response.text)
    except Exception:
        return ""


async def _fetch_document_material(
    client: httpx.AsyncClient, source_name: str, url: str, source_type: str
) -> list[str]:
    try:
        response = await client.get(url)
        response.raise_for_status()
        if url.lower().split("?", 1)[0].endswith(".pdf") or "application/pdf" in response.headers.get("content-type", ""):
            text = await asyncio.to_thread(_extract_pdf_text, response.content)
        else:
            text = _extract_article_text(response.text)
        if len(text) < 800:
            return []
        title = source_name
        title_match = re.search(r"<title[^>]*>(.*?)</title>", response.text, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = _clean_feed_text(title_match.group(1))[:160] or title
        return [f"资料类型：{source_type}\n来源机构：{source_name}\n标题：{title}\n原文正文：{text}\n来源：{url}"]
    except Exception as exc:
        logger.debug("学习资料不可用：{}（{}）", source_name, type(exc).__name__)
        return []


async def _fetch_feed_materials(client: httpx.AsyncClient, source_name: str, feed_url: str) -> list[str]:
    try:
        response = await client.get(feed_url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        entries = root.findall(".//item") or root.findall(".//{*}entry")
        feed_entries = []
        for entry in entries[:3]:
            title_node = _first_node(entry, ("title", "{*}title"))
            summary_node = _first_node(entry, ("description", "summary", "{*}summary", "{*}content"))
            link_node = _first_node(entry, ("link", "{*}link", "guid"))
            title = _clean_feed_text(title_node.text or "") if title_node is not None else ""
            summary_text = "".join(summary_node.itertext()) if summary_node is not None else ""
            summary = _clean_feed_text(summary_text)[:1200]
            link = (link_node.get("href") or link_node.text or "").strip() if link_node is not None else ""
            if title and link and any(domain in link for domain in REFERENCE_DOMAINS):
                feed_entries.append((title, summary, link))

        pages = await asyncio.gather(*(_fetch_page_content(client, link) for _, _, link in feed_entries))
        materials = []
        for (title, summary, link), article in zip(feed_entries, pages):
            if article:
                summary = f"{summary}\n原文正文：{article}" if summary else article
            if summary:
                materials.append(f"资料类型：技术博客或项目公告\n来源机构：{source_name}\n标题：{title}\n摘要：{summary}\n来源：{link}")
        return materials
    except Exception as exc:
        logger.debug("资料源不可用：{}（{}）", source_name, type(exc).__name__)
        return []


async def _fetch_source_material() -> str:
    global source_cache
    cache_seconds = int(os.getenv("SOURCE_CACHE_SECONDS", "21600"))
    if source_cache and time.monotonic() - source_cache[0] < cache_seconds:
        return source_cache[1]
    if os.getenv("LOCAL_KB_ENABLED", "1").lower() not in {"0", "false", "no"}:
        local_material = _next_local_kb_material()
        if local_material:
            source_cache = (time.monotonic(), local_material)
            return local_material
    try:
        cache_age = time.time() - os.path.getmtime(SOURCE_CACHE_FILE)
        if cache_age < cache_seconds:
            with open(SOURCE_CACHE_FILE, "r", encoding="utf-8") as cache_file:
                material = json.load(cache_file)["material"]
            source_cache = (time.monotonic(), material)
            return material
    except (FileNotFoundError, KeyError, OSError, TypeError, json.JSONDecodeError):
        pass

    timeout_seconds = float(os.getenv("SOURCE_TIMEOUT_SECONDS", "6"))
    started_at = time.perf_counter()
    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 4.0))
    document_limit = max(1, min(int(os.getenv("SOURCE_DOCUMENT_LIMIT", "2")), len(SOURCE_DOCUMENTS)))
    feed_limit = max(1, min(int(os.getenv("SOURCE_FEED_LIMIT", "2")), len(SOURCE_FEEDS)))
    selected_documents = random.sample(SOURCE_DOCUMENTS, document_limit)
    selected_feeds = random.sample(SOURCE_FEEDS, feed_limit)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        feed_results = asyncio.gather(
            *(_fetch_feed_materials(client, source_name, feed_url) for source_name, feed_url in selected_feeds)
        )
        document_results = asyncio.gather(
            *(_fetch_document_material(client, source_name, url, source_type) for source_name, url, source_type in selected_documents)
        )
        results = [*await feed_results, *await document_results]

    materials = [material for source_materials in results for material in source_materials]
    if not materials:
        raise RuntimeError("所有专业资料源暂时不可用")
    substantial_materials = [material for material in materials if len(material) >= 1200]
    if not substantial_materials:
        raise RuntimeError("已连接资料源，但未取得足够完整的文章正文")
    document_materials = [
        material
        for material in substantial_materials
        if not material.startswith("资料类型：技术博客或项目公告")
    ]
    material = random.choice(document_materials or substantial_materials)
    source_cache = (time.monotonic(), material)
    try:
        os.makedirs(os.path.dirname(SOURCE_CACHE_FILE), exist_ok=True)
        with open(SOURCE_CACHE_FILE, "w", encoding="utf-8") as cache_file:
            json.dump({"material": material}, cache_file, ensure_ascii=False)
    except OSError as exc:
        logger.debug("无法写入资料缓存：{}", exc)
    logger.info(
        "资料抓取耗时：{:.2f}s，可用条目：{}，完整文章：{}",
        time.perf_counter() - started_at,
        len(materials),
        len(document_materials),
    )
    return material


def _next_local_kb_material() -> str:
    try:
        with open(LOCAL_KB_INDEX, "r", encoding="utf-8") as index_file:
            chunks = json.load(index_file)["chunks"]
        chunks = [chunk for chunk in chunks if len(chunk.get("text", "")) >= 800]
        if not chunks:
            return ""
        cursor = 0
        try:
            with open(LOCAL_KB_STATE, "r", encoding="utf-8") as state_file:
                cursor = int(json.load(state_file).get("cursor", 0))
        except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            pass
        chunk = chunks[cursor % len(chunks)]
        with open(LOCAL_KB_STATE, "w", encoding="utf-8") as state_file:
            json.dump({"cursor": cursor + 1}, state_file)
        return (
            "资料类型：本地教材章节\n"
            f"来源机构：{chunk['book_title']}\n"
            f"标题：{chunk['book_title']}（第 {chunk['page_start']}-{chunk['page_end']} 页）\n"
            f"原文正文：{chunk['text']}\n"
            f"来源：{chunk['source_url']}"
        )
    except (FileNotFoundError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        logger.debug("本地知识库不可用：{}", exc)
        return ""


def _topic_for_material(source_material: str) -> str:
    material = source_material.lower()
    if any(keyword in material for keyword in ("think python", "python", "pep 8", "cs50p", "6.100l")):
        return "Python 编程基础与工程习惯"
    if any(keyword in material for keyword in ("dive into deep learning", "深度学习", "neural network")):
        return "深度学习基础与实践"
    if any(keyword in material for keyword in ("cs229", "machine learning", "机器学习")):
        return "机器学习基础与数学直觉"
    return "本科生计算机与人工智能基础"


async def _build_advanced_knowledge(detailed: bool = False) -> Message:
    try:
        source_material = await _fetch_source_material()
        evidence_candidates = _evidence_candidates(source_material)
        if len(evidence_candidates) < 2:
            raise ValueError("原文没有足够的可核验证据片段")
    except Exception as exc:
        logger.warning("无法取得足够完整的专业原文，本次不生成：{}", exc)
        return Message("⚠️ 本次没有拿到足够完整且可核验的专业原文，暂不发送，稍后再试。")

    evidence_list = "\n".join(
        f"{index}. {candidate}" for index, candidate in enumerate(evidence_candidates, start=1)
    )
    topic = _topic_for_material(source_material)
    length_instruction = (
        "正文 800 至 1200 个中文字符，可以分成 5 至 7 个短段落，重点讲透概念、执行过程和例子。"
        if detailed
        else "正文 550 至 800 个中文字符，把更多篇幅用于核心讲解和具体例子，适合群聊学习，不要写成泛泛科普。"
    )
    format_instruction = (
        "固定结构为：标题、今天学什么、核心讲解、最小示例、常见误区、练习题、依据编号。"
        "最后一行必须是“依据编号：N,M”，N 和 M 是下方证据候选中的两个不同编号。"
        "不要输出网址、答案提示、适用边界、原文摘录、Markdown 表格或 Markdown 标题。"
    )
    grounding_instruction = (
        "只压缩这一篇原文。每一个事实、数字、比较、因果关系和结论都必须由原文直接支持。"
        "原文没有的公式、数字、实验结果、模型版本、背景知识、评价和工程建议一律不要补写。"
        "只有原文明确给出时才可写公式、复杂度、数字或实验结果。"
        "不要把常识、你的推断或其他文章的信息混入事实部分。"
        "“最小示例”只能使用 Python 标准库和原文明确出现的概念；代码必须短小、可运行，并标注为教学改写，不得声称来自原文。"
        "“核心讲解”至少说明概念是什么、程序执行时发生什么、为什么这样设计，并给出一个具体输入输出过程。"
        "“常见误区”只写与本节概念直接相关、能从原文支持的错误理解。"
        "“练习题”必须围绕今天的一个概念设计，难度控制在本科生 10 分钟内能完成，不要提供答案或提示。"
    )
    source_input = f"{source_material}\n\n可核验的原文证据候选：\n{evidence_list}"
    draft_prompt = (
        "你是一名严谨的本科生课程编辑。请把下面这一篇教材、课程讲义、学习网站或技术文章，改造成一节能学完、能动手的群聊微课。"
        f"本次学习方向是：{topic}。只教一个核心概念，不要泛泛罗列文章目录；正文必须让读者知道今天学完后能写什么、判断什么或避免什么。"
        f"{length_instruction}{format_instruction}{grounding_instruction}"
        f"\n\n原文资料：\n{source_input}"
    )
    try:
        draft = await _call_ark(draft_prompt, allow_links=False, max_output_tokens=1300 if detailed else 700)
        review_prompt = (
            "你是一名本科课程事实审校员。请逐句对照原文审查草稿，删除或改写所有原文未直接支持的内容。"
            "不要保留仅仅合理但原文没有说的机制、数字、因果关系、评价或建议。"
            f"{length_instruction}{format_instruction}{grounding_instruction}"
            f"\n\n原文资料：\n{source_input}\n\n待审校草稿：\n{draft}"
        )
        reviewed = await _call_ark(review_prompt, allow_links=False, max_output_tokens=1300 if detailed else 700)
        try:
            content = _render_grounded_knowledge(reviewed, source_material, evidence_candidates, detailed)
        except ValueError as review_error:
            repair_prompt = (
                "只修复下面审校稿的格式和事实边界，不新增任何知识。必须保留原文支持的内容，"
                "并严格在最后一行输出“依据编号：N,M”；N、M 必须是原文证据候选中的两个不同编号。"
                f"{format_instruction}{grounding_instruction}"
                f"\n\n原文资料：\n{source_input}\n\n审校稿：\n{reviewed}\n\n格式错误：{review_error}"
            )
            repaired = await _call_ark(repair_prompt, allow_links=False, max_output_tokens=1300 if detailed else 700)
            content = _render_grounded_knowledge(repaired, source_material, evidence_candidates, detailed)
        title = "📖 AI 文章精读" if detailed else "📚 今日 AI 文章凝练"
        return Message(f"{title}\n\n{content}")
    except Exception as exc:
        logger.warning("文章凝练未通过原文校验，本次不发送未经证实内容：{}", exc)
        return Message("⚠️ 本次文章凝练未通过事实校验，已停止发送未经证实的内容，请稍后重试。")


def _history_text(group_id: int, user_id: int) -> str:
    history = conversation_history[(group_id, user_id)]
    if not history:
        return "无历史对话"
    return "\n".join(f"{role}：{content}" for role, content in history)


async def _answer_question(group_id: int, user_id: int, question: str) -> Message:
    if not _input_is_safe(question):
        return Message("该主题不在本群 AI 学习助手的讨论范围内。")
    history = _history_text(group_id, user_id)
    detailed = _wants_detailed(question)
    length_instruction = (
        "用户明确要求详细回答，请用 450 至 750 个中文字符，分成若干短段落。"
        if detailed
        else "默认使用群聊短回答：控制在 120 至 280 个中文字符，先给结论，再说明关键原因。"
    )
    prompt = (
        "你是 QQ 群里的人工智能学习助手。可回答机器学习、深度学习、大语言模型、NLP、计算机视觉、"
        "强化学习、AI Agent、机器人、AI 产品与应用、开源生态、芯片算力、行业趋势、教育与职业、"
        "版权、隐私保护、安全、伦理和治理等与 AI 明确相关的问题。回答要严谨、直接、有信息量。"
        "优先解释机制、假设、复杂度、边界条件和工程权衡；需要时可写简短公式或伪代码。"
        "公式只能用 QQ 可显示的纯文本，例如 loss=-log(p)，复杂度写成 O(n^2*d)；"
        "禁止使用 LaTeX、美元符号、反斜杠公式命令和 Markdown 数学块。"
        f"{length_instruction}不输出链接，不编造论文和实验数据。"
        "可客观讨论 AI 带来的社会影响和争议，但不要提供违法危险操作、隐私窃取、医疗诊断或具体投资建议。"
        "与 AI 完全无关的问题才回复：该主题不在本群 AI 学习助手的讨论范围内。\n"
        f"最近对话：\n{history}\n"
        f"用户问题：{question}"
    )
    try:
        answer = await _call_ark(prompt, max_output_tokens=1100 if detailed else 500)
    except Exception:
        logger.exception("AI 问答失败")
        return Message("AI 服务暂时不可用，请稍后再试。")
    conversation_history[(group_id, user_id)].append(("用户", question[:300]))
    answer = _truncate_at_sentence(answer, 900 if detailed else 340)
    conversation_history[(group_id, user_id)].append(("助手", answer[:900]))
    return Message(answer)


def _parse_quiz(text: str) -> dict[str, str]:
    match = re.search(r"<QUIZ>(.*?)</QUIZ>", text, re.DOTALL)
    candidate = match.group(1) if match else text
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("测验响应中没有 JSON 对象")
    data = json.loads(candidate[start : end + 1])
    required = {"question", "A", "B", "C", "D", "answer", "explanation"}
    if not required.issubset(data) or str(data["answer"]).upper() not in {"A", "B", "C", "D"}:
        raise ValueError("测验字段无效")
    return {key: str(data[key]).strip() for key in required}


async def _create_quiz(group_id: int) -> Message:
    topic = random.choice(ADVANCED_TOPICS)
    prompt = (
        f"围绕“{topic}”设计一道有区分度的单选题，面向有 AI 基础的工程师。"
        "不能只考定义，要考机制、复杂度、失败条件或工程权衡。四个选项都要有迷惑性，但只能有一个正确答案。"
        "不得包含违法危险操作、隐私泄露、医疗诊断或投资建议。严格只输出以下 JSON 包裹格式，不要输出其他文字：\n"
        '<QUIZ>{"question":"题目","A":"选项A","B":"选项B","C":"选项C","D":"选项D",'
        '"answer":"A","explanation":"解析，说明正确项以及其他选项错在哪里"}</QUIZ>'
    )
    try:
        quiz = _parse_quiz(await _call_ark(prompt, max_output_tokens=500))
    except Exception as exc:
        logger.warning("生成测验不可用，使用备用题：{}", exc)
        quiz = {
            "question": "在长上下文自回归推理中，GQA 相比标准多头注意力最直接降低了哪部分资源开销？",
            "A": "模型前馈网络的参数量",
            "B": "KV Cache 的容量与读取带宽",
            "C": "词表投影层的计算量",
            "D": "位置编码的长度上限",
            "answer": "B",
            "explanation": "GQA 让多个 Query 头共享较少的 Key/Value 头，因此直接减少 KV Cache 的存储与带宽压力。它不会直接减少 FFN 或词表投影参数，也不决定位置编码上限。",
        }
    quiz_sessions[group_id] = quiz
    return Message(
        "🧠 AI 挑战题\n\n"
        f"{quiz['question']}\n\nA. {quiz['A']}\nB. {quiz['B']}\nC. {quiz['C']}\nD. {quiz['D']}\n\n"
        "回复“答 A/B/C/D”参与；回复“解析”查看答案。"
    )


async def send_daily_knowledge() -> None:
    group_ids = _group_ids()
    bot = next(iter(get_bots().values()), None)
    if not group_ids or bot is None:
        logger.warning("群号未配置或 QQ Bot 不在线，跳过推送")
        return
    message = await _build_advanced_knowledge()
    for group_id in group_ids:
        try:
            await bot.send_group_msg(group_id=group_id, message=message)
        except Exception:
            logger.exception("向群 {} 推送知识失败", group_id)


async def scheduled_daily_knowledge() -> None:
    await send_daily_knowledge()
    _schedule_next_knowledge(force_next_day=True)


def _schedule_next_knowledge(force_next_day: bool = False) -> None:
    now = datetime.now()
    schedule_date = now.date() + timedelta(days=1 if force_next_day or now.hour >= 18 else 0)
    day_start = datetime.combine(schedule_date, datetime.min.time()).replace(hour=8)
    day_end = day_start.replace(hour=18)
    if schedule_date == now.date() and now > day_start:
        day_start = now + timedelta(seconds=5)
    run_at = day_start + timedelta(seconds=random.randint(0, int((day_end - day_start).total_seconds())))
    scheduler.add_job(scheduled_daily_knowledge, "date", run_date=run_at, id="daily_knowledge", replace_existing=True)
    logger.info("下一次知识推送时间：{}", run_at.strftime("%Y-%m-%d %H:%M"))


@get_driver().on_startup
async def register_daily_job() -> None:
    _schedule_next_knowledge()


knowledge_matcher = on_regex(r"^(今日知识|深度知识|知识|daily)$", flags=re.IGNORECASE, priority=10, block=True)
question_matcher = on_regex(r"^(问|详问|追问|AI|ai)[：:\s]+(.+)$", flags=re.IGNORECASE, priority=10, block=True)
quiz_matcher = on_regex(r"^(出题|AI出题|测验)$", priority=10, block=True)
answer_matcher = on_regex(r"^答[：:\s]*([ABCDabcd])$", priority=10, block=True)
explanation_matcher = on_regex(r"^(解析|答案)$", priority=10, block=True)
help_matcher = on_regex(r"^(帮助|菜单|功能)$", priority=10, block=True)
mention_matcher = on_message(rule=to_me(), priority=20, block=True)


@knowledge_matcher.handle()
async def handle_knowledge(event: GroupMessageEvent) -> None:
    await knowledge_matcher.send("📡 正在读取近期 AI 资料并整理，请稍候…")
    detailed = event.get_plaintext().strip() == "深度知识"
    await knowledge_matcher.finish(await _build_advanced_knowledge(detailed=detailed))


@question_matcher.handle()
async def handle_question(event: GroupMessageEvent) -> None:
    remaining = _cooldown_remaining(event.user_id)
    if remaining:
        await question_matcher.finish(f"请稍等 {remaining} 秒后再提问。")
    match = re.match(r"^(问|详问|追问|AI|ai)[：:\s]+(.+)$", event.get_plaintext().strip(), re.IGNORECASE)
    question = match.group(2).strip() if match else ""
    if match and match.group(1) == "详问":
        question = "请详细展开说明：" + question
    await question_matcher.send("🤔 正在分析问题，请稍候…")
    await question_matcher.finish(await _answer_question(event.group_id, event.user_id, question))


@mention_matcher.handle()
async def handle_mention(event: GroupMessageEvent) -> None:
    question = event.get_plaintext().strip()
    if not question:
        await mention_matcher.finish("请在 @我 后面写上 AI 技术问题。发送“功能”查看用法。")
    remaining = _cooldown_remaining(event.user_id)
    if remaining:
        await mention_matcher.finish(f"请稍等 {remaining} 秒后再提问。")
    await mention_matcher.send("🤔 正在分析问题，请稍候…")
    await mention_matcher.finish(await _answer_question(event.group_id, event.user_id, question))


@quiz_matcher.handle()
async def handle_quiz(event: GroupMessageEvent) -> None:
    await quiz_matcher.send("🧠 正在生成进阶题目，请稍候…")
    await quiz_matcher.finish(await _create_quiz(event.group_id))


@answer_matcher.handle()
async def handle_quiz_answer(event: GroupMessageEvent) -> None:
    quiz = quiz_sessions.get(event.group_id)
    if not quiz:
        await answer_matcher.finish("当前没有进行中的题目，发送“出题”开始。")
    match = re.match(r"^答[：:\s]*([ABCDabcd])$", event.get_plaintext().strip())
    choice = match.group(1).upper() if match else ""
    if choice == quiz["answer"].upper():
        await answer_matcher.finish(f"✅ 回答正确！\n\n{quiz['explanation']}")
    await answer_matcher.finish(f"❌ 不正确。你选了 {choice}。可以继续作答，或发送“解析”查看完整答案。")


@explanation_matcher.handle()
async def handle_explanation(event: GroupMessageEvent) -> None:
    quiz = quiz_sessions.get(event.group_id)
    if not quiz:
        await explanation_matcher.finish("当前没有进行中的题目，发送“出题”开始。")
    await explanation_matcher.finish(f"答案：{quiz['answer']}\n\n{quiz['explanation']}")


@help_matcher.handle()
async def handle_help() -> None:
    await help_matcher.finish(
        "🤖 AI 学习助手\n\n"
        "今日知识：适合群聊的 AI 短知识\n"
        "深度知识：生成较完整的长内容\n"
        "问 什么是推测解码：简短技术问答\n"
        "详问 推测解码如何实现：生成详细回答\n"
        "追问 它的瓶颈是什么：结合最近对话追问\n"
        "@机器人 + 问题：直接对话\n"
        "出题：生成一道进阶单选题\n"
        "答 A：提交答案\n"
        "解析：查看当前题目解析"
    )
