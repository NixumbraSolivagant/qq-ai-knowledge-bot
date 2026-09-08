from __future__ import annotations

import asyncio
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
        return _truncate_at_sentence(text, 850)
    source_match = re.search(r"(?:\n|^)资料来源：\s*(https?://\S+)", text)
    source = source_match.group(1) if source_match else ""
    body = text[: source_match.start()].rstrip() if source_match else text
    body = _truncate_at_sentence(body, 280)
    return f"{body}\n\n资料来源：{source}" if source else body


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


def _first_node(entry: ET.Element, names: tuple[str, ...]) -> ET.Element | None:
    for name in names:
        node = entry.find(name)
        if node is not None:
            return node
    return None


async def _fetch_page_summary(client: httpx.AsyncClient, url: str) -> str:
    response = await client.get(url)
    response.raise_for_status()
    page = response.text
    patterns = (
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, page, re.IGNORECASE)
        if match:
            return _clean_feed_text(match.group(1))[:900]
    return ""


async def _fetch_feed_materials(client: httpx.AsyncClient, source_name: str, feed_url: str) -> list[str]:
    try:
        response = await client.get(feed_url)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        entries = root.findall(".//item") or root.findall(".//{*}entry")
        materials = []
        for entry in entries[:5]:
            title_node = _first_node(entry, ("title", "{*}title"))
            summary_node = _first_node(entry, ("description", "summary", "{*}summary", "{*}content"))
            link_node = _first_node(entry, ("link", "{*}link", "guid"))
            title = _clean_feed_text(title_node.text or "") if title_node is not None else ""
            summary = _clean_feed_text(summary_node.text or "")[:900] if summary_node is not None else ""
            link = (link_node.get("href") or link_node.text or "").strip() if link_node is not None else ""
            if title and link and not summary and any(domain in link for domain in REFERENCE_DOMAINS):
                summary = await _fetch_page_summary(client, link)
            if title and summary and any(domain in link for domain in REFERENCE_DOMAINS):
                materials.append(f"来源机构：{source_name}\n标题：{title}\n摘要：{summary}\n来源：{link}")
        return materials
    except Exception as exc:
        logger.debug("资料源不可用：{}（{}）", source_name, type(exc).__name__)
        return []


async def _fetch_source_material() -> str:
    global source_cache
    cache_seconds = int(os.getenv("SOURCE_CACHE_SECONDS", "21600"))
    if source_cache and time.monotonic() - source_cache[0] < cache_seconds:
        return source_cache[1]

    timeout_seconds = float(os.getenv("SOURCE_TIMEOUT_SECONDS", "6"))
    max_items = max(1, min(int(os.getenv("SOURCE_ITEMS_PER_REQUEST", "3")), 5))
    started_at = time.perf_counter()
    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 4.0))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        results = await asyncio.gather(
            *(_fetch_feed_materials(client, source_name, feed_url) for source_name, feed_url in SOURCE_FEEDS)
        )

    materials = [material for source_materials in results for material in source_materials]
    if not materials:
        raise RuntimeError("所有专业资料源暂时不可用")
    selected = random.sample(materials, min(max_items, len(materials)))
    material = "\n\n---\n\n".join(selected)
    source_cache = (time.monotonic(), material)
    logger.info("资料抓取耗时：{:.2f}s，可用条目：{}，选用：{}", time.perf_counter() - started_at, len(materials), len(selected))
    return material


async def _build_advanced_knowledge(detailed: bool = False) -> Message:
    topic = random.choice(ADVANCED_TOPICS)
    try:
        source_material = await _fetch_source_material()
    except Exception as exc:
        logger.warning("近期 AI 资料暂不可用，改用稳定专题知识：{}", exc)
        source_material = ""
    if source_material:
        source_instruction = (
            "下方提供了多条真实抓取的近期论文、官方博客或官方项目资料。选择其中最有技术价值的一条作为知识输入；"
            "最后必须标注“资料来源：”，并且只能原样复制材料中的一个来源网址。"
        )
        source_input = source_material
    else:
        source_instruction = (
            "当前没有可用的外部资料。请仅基于稳定的专业知识讨论备选专题，不得声称这是最新进展，"
            "不得虚构论文、实验数据、版本号、引用或网址，也不要输出“资料来源”。"
        )
        source_input = "无外部资料"
    length_instruction = (
        "正文 450 至 700 个中文字符，可以分成 3 至 5 个短段落。"
        if detailed
        else "正文 160 至 240 个中文字符，只保留最关键的机制、误区和工程启示，适合群聊快速阅读。"
    )
    prompt = (
        f"今天是 {datetime.now():%Y-%m-%d}。请写一条面向有一定编程基础读者的 AI 深度知识。备选专题是：{topic}。"
        f"{source_instruction}如果资料与备选专题不一致，以资料为准。难度定位为研究生入门或工程实践，不要解释最基础定义。"
        f"{length_instruction}"
        "必须包含：1）核心机制；2）一个关键公式、复杂度关系或训练/推理权衡（无法写公式时给出精确因果关系）；"
        "3）一个常见误区或失败条件；4）一个实际工程启示。结构清晰但不要 Markdown 表格。"
        "QQ 不支持 LaTeX 或 Markdown 数学公式。所有公式必须写成单行纯文本，例如："
        "Attention(Q,K,V)=softmax(QK^T/sqrt(d_k))*V，复杂度写成 O(n^2*d)。"
        "禁止使用美元符号、反斜杠命令、frac、数学代码块或 Markdown 标题。"
        "不要编造论文、数据、版本号或实验结论。"
        "可以讨论 AI 产品、产业、开源、算力、机器人、教育、医疗应用、就业、版权、隐私保护、安全与伦理。"
        "涉及争议时保持中立并聚焦技术机制、可靠来源和实际影响；不得提供违法危险操作、隐私窃取、"
        "医疗诊断或具体金融投资建议。"
        f"直接以“标题：”开始，不要寒暄，不要反问读者。\n\n资料输入：\n{source_input}"
    )
    try:
        text = await _call_ark(prompt, allow_links=bool(source_material), max_output_tokens=1000 if detailed else 500)
        title = "📖 AI 深度阅读" if detailed else "📚 今日 AI 知识"
        return Message(f"{title}\n\n{_compact_knowledge(text, detailed)}")
    except Exception:
        logger.exception("生成深度知识失败，使用高阶备用内容")
        return Message(random.choice(FALLBACK_KNOWLEDGE))


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
