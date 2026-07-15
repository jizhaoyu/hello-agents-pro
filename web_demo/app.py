"""
智能体学习平台 - 后端API（稳定版）
提供Web界面与Python代码的桥接

修复：
1. 使用logging替代print（避免stdout冲突）
2. 移除编码处理（避免debug模式冲突）
3. 改进错误处理
4. 超时控制
"""

from flask import Flask, jsonify, request, send_from_directory
import sys
import os
import re
import logging
from datetime import datetime
from functools import lru_cache

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')
app = Flask(__name__, static_folder=FRONTEND_DIR)
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024

# 配置logging（替代print）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# 添加code目录到路径
sys.path.insert(0, os.path.join(BASE_DIR, '..', 'code'))
from super_agent import get_super_agent

SUPER_AGENT = get_super_agent()

NOTES_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'notes'))

CHINESE_NUMBERS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8,
    "九": 9, "十": 10, "十一": 11, "十二": 12, "十三": 13, "十四": 14,
    "十五": 15, "十六": 16,
}

LEARNING_PHASES = [
    {
        "id": "foundations",
        "name": "基础认知",
        "range": [1, 3],
        "kicker": "ORIGIN",
        "description": "理解智能体、历史脉络与大语言模型这三块地基。",
    },
    {
        "id": "building",
        "name": "构建方法",
        "range": [4, 7],
        "kicker": "BUILD",
        "description": "从经典范式出发，走到框架开发和完整应用。",
    },
    {
        "id": "advanced",
        "name": "高级能力",
        "range": [8, 12],
        "kicker": "SYSTEMS",
        "description": "补齐记忆、上下文、协议、强化学习与评估能力。",
    },
    {
        "id": "projects",
        "name": "项目实战",
        "range": [13, 15],
        "kicker": "FIELDWORK",
        "description": "通过旅行、研究和赛博小镇完成综合实践。",
    },
    {
        "id": "graduation",
        "name": "毕业设计",
        "range": [16, 16],
        "kicker": "SHIP",
        "description": "把全部能力汇总成一件可以公开展示的作品。",
    },
]


def strip_markdown(value):
    """将简短 Markdown 文本压缩为适合卡片展示的纯文本。"""
    value = re.sub(r"[`*_>#\[\]|]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" -:")


def get_note_phase(number):
    for phase in LEARNING_PHASES:
        if phase["range"][0] <= number <= phase["range"][1]:
            return phase
    return LEARNING_PHASES[-1]


def extract_note_summary(lines, title):
    candidates = []
    in_code_block = False
    for raw_line in lines[1:80]:
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block or not line or line == "---" or line.startswith("#"):
            continue
        cleaned = strip_markdown(line)
        if cleaned and not cleaned.startswith(("项目时长", "难度", "目标")):
            candidates.append(cleaned)
        if sum(len(item) for item in candidates) >= 90:
            break

    summary = " ".join(candidates) or f"围绕{title}整理的个人学习笔记。"
    return summary[:108] + ("…" if len(summary) > 108 else "")


def get_notes_signature():
    """Return a cache key that changes whenever a Markdown note changes."""
    if not os.path.isdir(NOTES_DIR):
        return ()

    signature = []
    for filename in os.listdir(NOTES_DIR):
        if not filename.endswith('.md'):
            continue
        path = os.path.join(NOTES_DIR, filename)
        try:
            stat = os.stat(path)
            signature.append((filename, stat.st_mtime_ns, stat.st_size))
        except OSError as exc:
            logger.warning("Skipping unreadable note metadata %s: %s", filename, exc)
    return tuple(sorted(signature))


def load_note_catalog():
    return load_note_catalog_cached(get_notes_signature())


@lru_cache(maxsize=4)
def load_note_catalog_cached(notes_signature):
    """从 notes 目录构建学习网站目录，Markdown 文件是唯一内容源。"""
    chapters = []
    if not notes_signature:
        return chapters

    for filename, _, _ in notes_signature:
        match = re.match(r"第([一二三四五六七八九十]+)章", filename)
        if not match or match.group(1) not in CHINESE_NUMBERS:
            continue

        number = CHINESE_NUMBERS[match.group(1)]
        path = os.path.join(NOTES_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8-sig") as note_file:
                content = note_file.read()
        except (OSError, UnicodeError) as exc:
            logger.warning("Skipping unreadable note %s: %s", filename, exc)
            continue

        lines = content.splitlines()
        heading = next((line[2:].strip() for line in lines if line.startswith("# ")), filename[:-3])
        title = re.sub(r"^第.+?章[：:\s]*", "", heading)
        title = re.sub(r"\s*[·｜|].*$", "", title).strip() or heading
        sections = []
        in_code_block = False
        for line in lines:
            if line.strip().startswith("```"):
                in_code_block = not in_code_block
                continue
            if not in_code_block and line.startswith("## "):
                sections.append(strip_markdown(line[3:].strip()))
        meaningful_characters = len(re.sub(r"\s+", "", content))
        phase = get_note_phase(number)
        modified_at = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y.%m.%d")

        chapters.append({
            "id": f"chapter-{number:02d}",
            "number": number,
            "chapterLabel": f"第 {number:02d} 章",
            "title": title,
            "fullTitle": heading,
            "summary": extract_note_summary(lines, title),
            "phaseId": phase["id"],
            "phaseName": phase["name"],
            "sections": sections,
            "sectionCount": len(sections),
            "readingMinutes": max(3, round(meaningful_characters / 520)),
            "characters": meaningful_characters,
            "updatedAt": modified_at,
            "filename": filename,
        })

    chapters.sort(key=lambda item: item["number"])
    return chapters


def build_learning_overview():
    chapters = load_note_catalog()
    phases = []
    for phase in LEARNING_PHASES:
        phase_chapters = [chapter for chapter in chapters if chapter["phaseId"] == phase["id"]]
        phases.append({
            **phase,
            "chapterIds": [chapter["id"] for chapter in phase_chapters],
            "chapterCount": len(phase_chapters),
        })

    return {
        "title": "智能体学习档案",
        "subtitle": "从第一性原理到多智能体应用",
        "chapters": chapters,
        "phases": phases,
        "stats": {
            "chapterCount": len(chapters),
            "phaseCount": len([phase for phase in phases if phase["chapterCount"]]),
            "sectionCount": sum(chapter["sectionCount"] for chapter in chapters),
            "readingMinutes": sum(chapter["readingMinutes"] for chapter in chapters),
            "characters": sum(chapter["characters"] for chapter in chapters),
        },
    }


# ============ API路由 ============

@app.route('/')
def index():
    """首页"""
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/api/learning', methods=['GET'])
def get_learning_overview():
    """获取由本地 Markdown 笔记生成的完整学习目录。"""
    return jsonify({
        "success": True,
        "data": build_learning_overview(),
    })


@app.route('/api/learning/<chapter_id>', methods=['GET'])
def get_learning_note(chapter_id):
    """读取单章笔记正文与相邻章节。"""
    chapters = load_note_catalog()
    chapter_index = next(
        (index for index, chapter in enumerate(chapters) if chapter["id"] == chapter_id),
        None,
    )
    if chapter_index is None:
        return jsonify({"success": False, "error": "学习笔记不存在"}), 404

    chapter = chapters[chapter_index]
    note_path = os.path.join(NOTES_DIR, chapter["filename"])
    try:
        with open(note_path, "r", encoding="utf-8-sig") as note_file:
            content = note_file.read()
    except (OSError, UnicodeError) as exc:
        logger.warning("Unable to read note %s: %s", chapter["filename"], exc)
        return jsonify({"success": False, "error": "笔记暂时无法读取"}), 500

    return jsonify({
        "success": True,
        "data": {
            **chapter,
            "content": content,
            "previousId": chapters[chapter_index - 1]["id"] if chapter_index > 0 else None,
            "nextId": chapters[chapter_index + 1]["id"] if chapter_index < len(chapters) - 1 else None,
        },
    })


@app.route('/api/agent/status', methods=['GET'])
def get_agent_status():
    """获取统一智能体状态"""
    return jsonify({
        "success": True,
        "data": SUPER_AGENT.status()
    })


@app.route('/api/agent/chat', methods=['POST'])
def chat_with_agent():
    """统一智能体对话"""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "请求必须是 JSON 对象"}), 400

    message = data.get('message')
    mode = data.get('mode', 'auto')
    use_real_ai = data.get('use_real_ai', False)
    if not isinstance(message, str) or not message.strip():
        return jsonify({"success": False, "error": "请输入问题"}), 400
    if len(message) > 2000:
        return jsonify({"success": False, "error": "问题不能超过 2000 个字符"}), 413
    if not isinstance(mode, str) or mode not in {'auto', 'reasoning_patterns', 'memory_tools_context', 'learning_assistant'}:
        return jsonify({"success": False, "error": "不支持的工作模式"}), 400
    if not isinstance(use_real_ai, bool) or use_real_ai:
        return jsonify({"success": False, "error": "分享版仅支持本地学习模式"}), 400

    result = SUPER_AGENT.chat(message, mode=mode)
    status = 200 if result.get("success") else 400
    if not result.get("success"):
        logger.warning("Agent request failed: %s", result.get("error", "unknown error"))
        return jsonify({"success": False, "error": "学习助手暂时无法回答，请稍后重试"}), status
    return jsonify(result), status


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    platform = SUPER_AGENT.status()
    learning = build_learning_overview()
    return jsonify({
        "success": True,
        "status": "running",
        "chapters": learning["stats"]["chapterCount"],
        "demos": 0,
        "platform_capabilities": len(platform["capabilities"]),
        "platform_name": platform["name"],
        "learning_chapters": learning["stats"]["chapterCount"],
        "learning_sections": learning["stats"]["sectionCount"],
    })


# ============ 静态文件 ============

@app.route('/<path:path>')
def static_files(path):
    """提供静态文件"""
    return send_from_directory(FRONTEND_DIR, path)


# ============ 错误处理 ============

@app.errorhandler(404)
def not_found(e):
    return jsonify({"success": False, "error": "资源不存在"}), 404


@app.errorhandler(500)
def internal_error(e):
    return jsonify({"success": False, "error": "服务器内部错误"}), 500


@app.errorhandler(413)
def request_too_large(e):
    return jsonify({"success": False, "error": "请求内容过大"}), 413


# ============ 启动服务 ============

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🤖 超级智能体平台 - Web服务启动")
    print("=" * 70)
    platform = SUPER_AGENT.status()
    print(f"\n📊 本地学习助手能力数: {len(platform['capabilities'])}")
    print(f"🧠 当前会话记忆条目: {platform['memory']['session_facts']}")

    print("\n🌐 访问地址:")
    print("   本地: http://localhost:5000")

    print("\n💡 提示:")
    print("   - 按 Ctrl+C 停止服务")
    print("   - 仅限本机访问，不提供局域网服务")
    print("   - 使用logging记录日志（无stdout冲突）")

    print("\n" + "=" * 70 + "\n")

    # 关闭Flask的默认logger，使用我们自己的
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)

    # 使用生产模式
    app.run(host='127.0.0.1', port=5000, debug=False, threaded=True)
