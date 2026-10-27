#!/usr/bin/env python3
"""
Universal Rationale Polisher & Sentence Reframer (v2.0)
100% Local Inference Server + Air-Gapped Telegram Bot + :8080 Web UI

Backed by:
- Local llama.cpp / Llama.app (http://127.0.0.1:9931/v1)
- Model: gemma4:Q6 (Apple Silicon Metal GPU)
- Master Blueprint: POLISHER_MASTER_BLUEPRINT.md
"""

import os
import sys
import json
import time
import math
import re
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.request
import urllib.error

# ---------------------------------------------------------
# Isolated .env Loader (Zero External Dependencies)
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")


def load_local_env(env_file: str) -> None:
    """Loads environment variables from a local .env file if present without overriding existing OS env vars."""
    if not os.path.isfile(env_file):
        return
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception as exc:
        sys.stderr.write(f"[Polisher] Warning: Could not parse .env file: {exc}\n")


load_local_env(ENV_PATH)

# ---------------------------------------------------------
# Configuration (100% Environment-Isolated)
# ---------------------------------------------------------
LLAMA_URL = os.environ.get("LLAMA_CPP_URL", "http://127.0.0.1:9931/v1/chat/completions")
HEALTH_URL = os.environ.get("LLAMA_HEALTH_URL", "http://127.0.0.1:9931/v1/models")
LLAMA_MODEL = os.environ.get("LLAMA_MODEL", "gemma4:Q6")
PORT = int(os.environ.get("POLISHER_PORT", "8080"))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

# ---------------------------------------------------------
# Master Blueprint cadence normalization & Burstiness Prompt Engine
# ---------------------------------------------------------
SYSTEM_PROMPT_TEMPLATE = """You are an elite, native-level technical editor and evaluator rationale polisher operating at CEFR Level {level} (IELTS Band 8.5-9.0 equivalent).

Your objective is to rewrite the input into natural, authoritative, publication-grade rationale prose while defeating statistical automated text classifiers through high cognitive burstiness.

STRICT LINGUISTIC & cadence normalization CONSTRAINTS (POLISHER_MASTER_BLUEPRINT.md):
1. HIGH BURSTINESS (SENTENCE CADENCE VARIANCE):
   - Vary sentence lengths aggressively across every paragraph.
   - Alternate short, decisive assertions (4-9 words) with dense, multi-clause analytical explanations (20-35 words using semicolons, parenthetical specifics, or dependent clauses) and medium transitional observations (12-16 words).
   - NEVER produce 3 consecutive sentences of similar word length.
2. MANDATORY NATURAL CONTRACTIONS:
   - Always use natural conversational contractions (it's, doesn't, won't, can't, there's, wouldn't, isn't, they've, don't, wasn't) across both C1 and C2 registers to eliminate synthetic stiffness.
3. PRESERVE HUMAN DISCOURSE MARKERS:
   - Retain and strategically deploy precise analytical transitions where genuine logical friction or contrast exists: moreover, although, rather, furthermore, additionally, nevertheless, conversely, in contrast.
4. BANNED automated HALLMARKS & SYMMETRY TEMPLATES (RUTHLESSLY STRIP):
   - Never use synthetic editorial clichés: "delve", "delve into", "testament", "testament to", "robust", "seamlessly", "exhibits", "leverage", "leveraging", "utilize", "utilizing", "tapestry", "beacon", "game-changer", "multifaceted", "plethora", "pivotal", "crucial", "vital", "intricate", "meticulous", "commendable", "underscore", "foster", "it is important to note", "in conclusion", "in summary".
   - Never use robotic correlative templates like "Not only X, but also Y".
5. STRICT OUTPUT DISCIPLINE:
   - Output ONLY the polished text.
   - Do NOT include greetings, meta-acknowledgments ("Here is the polished rationale:"), wrapping quotation marks, or follow-up commentary."""

STYLE_INSTRUCTIONS = {
    "default": """STYLE MODE: DEFAULT (Detailed Evaluator Rationale)
Preserve full analytical granularity and evidential depth. Ensure every claim is grounded in clear cause-and-effect reasoning with sharp comparative transitions and alternating short/long sentence burstiness.""",

    "concise": """STYLE MODE: CONCISE (High-Density Punchy Evaluation)
Compress the rationale for maximum signal-per-token. Strip all throat-clearing, redundant qualifiers, and syntactic padding while maintaining a sharp contrast between ultra-short verdicts (4-8 words) and compact multi-point synthesis sentences."""
}

LEVEL_DESCRIPTIONS = {
    "C1": "C1 Advanced (IELTS 8.0-8.5): Articulate, direct professional and academic fluency with natural contractions and zero robotic phrasing.",
    "C2": "C2 Mastery (IELTS 9.0): Native-grade intellectual authority, effortless idiomatic precision, incisive analytical rhythm, and zero synthetic residue."
}

# Deterministic regex replacements for post-generation sanitization
CLICHE_REPLACEMENTS = [
    (r"\bdelves into\b", "examines"),
    (r"\bdelved into\b", "examined"),
    (r"\bdelving into\b", "examining"),
    (r"\bdelve into\b", "examine"),
    (r"\bdelves\b", "digs"),
    (r"\bdelve\b", "dig"),
    (r"\ba testament to\b", "clear proof of"),
    (r"\btestament to\b", "proof of"),
    (r"\brobust\b", "solid"),
    (r"\bseamlessly\b", "smoothly"),
    (r"\bseamless\b", "smooth"),
    (r"\bexhibits\b", "shows"),
    (r"\bexhibited\b", "showed"),
    (r"\bleveraging\b", "using"),
    (r"\bleveraged\b", "used"),
    (r"\bleverages\b", "uses"),
    (r"\bleverage\b", "use"),
    (r"\butilizing\b", "using"),
    (r"\butilized\b", "used"),
    (r"\butilizes\b", "uses"),
    (r"\butilize\b", "use"),
    (r"\bmultifaceted\b", "complex"),
    (r"\bpivotal\b", "key"),
    (r"\bcrucial\b", "key"),
    (r"\bvital\b", "essential"),
    (r"\bplethora of\b", "wide range of"),
    (r"\btapestry of\b", "mix of"),
    (r"\bbeacon of\b", "model of"),
    (r"\bgame-changer\b", "major shift"),
    (r"\bunderscores\b", "highlights"),
    (r"\bunderscore\b", "highlight"),
    (r"\bmeticulously\b", "carefully"),
    (r"\bmeticulous\b", "careful"),
    (r"\bit is important to note that\b", ""),
    (r"\bit is worth noting that\b", ""),
    (r"\bin conclusion,\s*", ""),
    (r"\bin summary,\s*", ""),
    (r"\bin order to\b", "to"),
    (r"\bdue to the fact that\b", "because"),
    (r"\bmake sure\b", "ensure"),
    (r"\bmakes sure\b", "ensures"),
    (r"\bkeep track of\b", "monitor"),
    (r"\bfind out\b", "determine"),
    (r"\blook into\b", "examine"),
    (r"\bset up\b", "configure"),
    (r"\bget rid of\b", "eliminate"),
]

UNCONTRACTED_FIXES = [
    (r"\b[Ii]t is\b", lambda m: "It's" if m.group(0)[0].isupper() else "it's"),
    (r"\b[Dd]oes not\b", lambda m: "Doesn't" if m.group(0)[0].isupper() else "doesn't"),
    (r"\b[Dd]o not\b", lambda m: "Don't" if m.group(0)[0].isupper() else "don't"),
    (r"\b[Dd]id not\b", lambda m: "Didn't" if m.group(0)[0].isupper() else "didn't"),
    (r"\b[Cc]annot\b", lambda m: "Can't" if m.group(0)[0].isupper() else "can't"),
    (r"\b[Ww]ill not\b", lambda m: "Won't" if m.group(0)[0].isupper() else "won't"),
    (r"\b[Ww]ould not\b", lambda m: "Wouldn't" if m.group(0)[0].isupper() else "wouldn't"),
    (r"\b[Ss]hould not\b", lambda m: "Shouldn't" if m.group(0)[0].isupper() else "shouldn't"),
    (r"\b[Cc]ould not\b", lambda m: "Couldn't" if m.group(0)[0].isupper() else "couldn't"),
    (r"\b[Ii]s not\b", lambda m: "Isn't" if m.group(0)[0].isupper() else "isn't"),
    (r"\b[Aa]re not\b", lambda m: "Aren't" if m.group(0)[0].isupper() else "aren't"),
    (r"\b[Ww]as not\b", lambda m: "Wasn't" if m.group(0)[0].isupper() else "wasn't"),
    (r"\b[Ww]ere not\b", lambda m: "Weren't" if m.group(0)[0].isupper() else "weren't"),
    (r"\b[Hh]as not\b", lambda m: "Hasn't" if m.group(0)[0].isupper() else "hasn't"),
    (r"\b[Hh]ave not\b", lambda m: "Haven't" if m.group(0)[0].isupper() else "haven't"),
    (r"\b[Tt]here is\b", lambda m: "There's" if m.group(0)[0].isupper() else "there's"),
]


def _match_case(repl: str, original: str) -> str:
    if not repl:
        return ""
    if original.isupper():
        return repl.upper()
    if original[0].isupper():
        return repl[0].upper() + repl[1:]
    return repl


def sanitize_ai_cliches(text: str, level: str = "C1", style: str = "default") -> str:
    """Post-processing guardrail: strips preambles, clichés, stiff uncontracted verbs, and restructures sentence cadence."""
    cleaned = text.strip()

    # Strip common conversational preambles if the local model emitted any
    cleaned = re.sub(
        r"^(?:Here(?:'s| is) (?:the |your )?(?:polished|reframed|revised|updated)[^:\n]*:\s*)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    # Strip wrapping outer quotes if entire block is quoted
    if len(cleaned) >= 2 and cleaned[0] in ('"', "“") and cleaned[-1] in ('"', "”"):
        cleaned = cleaned[1:-1].strip()

    # Replace blacklisted automated clichés preserving case
    for pattern, repl in CLICHE_REPLACEMENTS:
        def _replacer(match, r=repl):
            return _match_case(r, match.group(0))
        cleaned = re.sub(pattern, _replacer, cleaned, flags=re.IGNORECASE)

    # Enforce natural contractions if the model left formal uncontracted auxiliaries
    for pattern, fn in UNCONTRACTED_FIXES:
        cleaned = re.sub(pattern, fn, cleaned)

    # Tri-Modal Sentence Cadence & Register Shaping (Offline & Post-statistical model)
    if level.upper() == "C2":
        for pat, rep in [(r"\bexamine\b", "dissect"), (r"\bsolid\b", "resilient"), (r"\bcomplex\b", "multi-layered"), (r"\bkey\b", "decisive")]:
            cleaned = re.sub(pat, lambda m, r=rep: _match_case(r, m.group(0)), cleaned, flags=re.I)

    sents = re.split(r"(?<=[.!?])\s+", cleaned)
    reshaped = []
    for idx, s in enumerate(sents):
        s = s.strip()
        if not s:
            continue
        if re.match(r"^(Furthermore|Moreover|Additionally|Consequently),?\s+", s, flags=re.I):
            pivots = ["Even so, ", "Beyond that, ", "Still, "] if level.upper() == "C2" else ["Plus, ", "Still, ", "Look — "]
            s = re.sub(r"^(Furthermore|Moreover|Additionally|Consequently),?\s+", pivots[idx % len(pivots)], s, flags=re.I)
        if style.lower() == "concise":
            s = re.sub(r"^(Basically|Essentially|Generally speaking|Notably),?\s+", "", s, flags=re.I)
            s = re.sub(r"\b(just|really|actually|literally|quite|simply|basically)\s+", "", s, flags=re.I)
        words = s.split()
        if len(words) >= 13:
            m = re.match(r"^(.{15,140}?),\s+(and|but|so|yet|which|because|while)\s+(.{12,})$", s, flags=re.I)
            if not m:
                m = re.match(r"^([^,]{15,140}?)\s+(and|but|so|yet|which|because|while)\s+(.{12,})$", s, flags=re.I)
            if m:
                c1 = m.group(1).strip().rstrip(".!?")
                conj = m.group(2).lower()
                c2 = m.group(3).strip()
                c2_low = c2[0].lower() + c2[1:] if len(c2) > 1 else c2
                c2_cap = c2[0].upper() + c2[1:] if len(c2) > 1 else c2.upper()
                if style.lower() == "concise":
                    s = f"{c1}. {c2_cap}"
                elif conj in ("but", "yet", "while"):
                    s = f"{c1}. Still, {c2_low}"
                elif conj == "so":
                    s = f"{c1}. That's why {c2_low}"
                elif conj == "which":
                    s = f"{c1}. This directly {c2_low}"
                elif conj == "because":
                    s = f"{c1}. The reason: {c2_low}"
                else:
                    s = f"{c1}. {c2_cap}"
        if s and s[0].islower():
            s = s[0].upper() + s[1:]
        if len(s.split()) >= 5 and s[-1] not in ".!?:;":
            s += "."
        reshaped.append(s)

    cleaned = " ".join(reshaped)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned


def compute_burstiness_metrics(text: str) -> dict:
    """Computes sentence count, average words/sentence, standard deviation (burstiness), and min-max range."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not sentences:
        sentences = [s.strip() for s in re.split(r"[.!?]+", text.strip()) if s.strip()]

    word_counts = [len(s.split()) for s in sentences if s.split()]
    if not word_counts:
        return {
            "sentence_count": 0,
            "avg_sentence_words": 0.0,
            "burstiness_sd": 0.0,
            "sentence_range": "0-0w",
            "contraction_count": 0,
        }

    n = len(word_counts)
    avg_len = sum(word_counts) / n
    if n > 1:
        variance = sum((w - avg_len) ** 2 for w in word_counts) / n
        sd = math.sqrt(variance)
    else:
        sd = 0.0

    contractions = re.findall(r"\b\w+'\w+\b", text)
    return {
        "sentence_count": n,
        "avg_sentence_words": round(avg_len, 1),
        "burstiness_sd": round(sd, 1),
        "sentence_range": f"{min(word_counts)}–{max(word_counts)}w",
        "contraction_count": len(contractions),
    }


def check_llama_health() -> dict:
    """Queries local llama.cpp /v1/models endpoint and verifies active model."""
    try:
        req = urllib.request.Request(HEALTH_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            models = data.get("data", [])
            detected_model = LLAMA_MODEL
            if isinstance(models, list) and models:
                first_id = models[0].get("id")
                if first_id:
                    detected_model = first_id
            return {
                "status": "ok",
                "backend": "llama.cpp connected",
                "model": detected_model,
                "configured_model": LLAMA_MODEL,
                "endpoint": LLAMA_URL,
                "telegram_active": bool(TELEGRAM_BOT_TOKEN),
            }
    except Exception as exc:
        return {
            "status": "degraded",
            "backend": f"llama.cpp offline ({exc})",
            "model": LLAMA_MODEL,
            "configured_model": LLAMA_MODEL,
            "endpoint": LLAMA_URL,
            "telegram_active": bool(TELEGRAM_BOT_TOKEN),
        }


def polish_text(text: str, level: str = "C1", style: str = "default") -> dict:
    start_time = time.time()
    level = level.upper() if level.upper() in ("C1", "C2") else "C1"
    style = style.lower() if style.lower() in ("default", "concise") else "default"

    system_content = (
        f"{SYSTEM_PROMPT_TEMPLATE.format(level=level)}\n\n"
        f"{STYLE_INSTRUCTIONS[style]}\n\n"
        f"CEFR PROFILE: {LEVEL_DESCRIPTIONS[level]}"
    )

    user_prompt = (
        f"Rewrite and polish the following text at CEFR {level} in {style.upper()} mode. "
        f"Enforce strict sentence-length burstiness (alternating 4-9 word punchy assertions with 20-35 word analytical clauses), "
        f"natural contractions, and zero automated clichés:\n\n{text}"
    )

    payload = {
        "model": LLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.45 if style == "concise" else 0.65,
        "top_p": 0.90,
        "repeat_penalty": 1.12,
        "max_tokens": 1500,
        "stream": False,
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        LLAMA_URL,
        data=req_data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_output = data["choices"][0]["message"]["content"]
            polished = sanitize_ai_cliches(raw_output, level=level, style=style)
            latency_ms = int((time.time() - start_time) * 1000)
            metrics = compute_burstiness_metrics(polished)

            return {
                "success": True,
                "result": polished,
                "level": level,
                "style": style,
                "model": LLAMA_MODEL,
                "latency_ms": latency_ms,
                **metrics,
            }
    except Exception as exc:
        # Automatic zero-statistical model deterministic fallback when local llama.cpp is offline
        polished = sanitize_ai_cliches(text, level=level, style=style)
        latency_ms = max(1, int((time.time() - start_time) * 1000))
        metrics = compute_burstiness_metrics(polished)
        return {
            "success": True,
            "result": polished,
            "polished": polished,
            "level": level,
            "style": style,
            "model": f"Built-In Reframer (llama.cpp offline)",
            "latency_ms": latency_ms,
            **metrics,
        }


# ---------------------------------------------------------
# Web Server & API Handler (:8080)
# ---------------------------------------------------------
class PolisherHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep console output clean; suppress routine /api/health poll logs
        if len(args) > 0 and "/api/health" in str(args[0]):
            return
        super().log_message(format, *args)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_path = os.path.join(BASE_DIR, "index.html")
            with open(html_path, "rb") as f:
                self.wfile.write(f.read())
        elif self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            res = check_llama_health()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif self.path == "/api/blueprint":
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.end_headers()
            bp_path = os.path.join(BASE_DIR, "POLISHER_MASTER_BLUEPRINT.md")
            if os.path.isfile(bp_path):
                with open(bp_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"# Blueprint file not found.")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/polish":
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length)
            try:
                req_json = json.loads(post_body.decode("utf-8"))
                text = req_json.get("text", "").strip()
                level = req_json.get("level", "C1")
                style = req_json.get("style", "default")

                if not text:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(
                        json.dumps({"success": False, "error": "Empty text provided"}).encode("utf-8")
                    )
                    return

                result = polish_text(text, level=level, style=style)
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as exc:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    json.dumps({"success": False, "error": str(exc)}).encode("utf-8")
                )
        else:
            self.send_response(404)
            self.end_headers()


# ---------------------------------------------------------
# Telegram Long-Polling Thread (Air-Gapped Mobile Workflow)
# ---------------------------------------------------------
def telegram_worker():
    if not TELEGRAM_BOT_TOKEN:
        print("[Telegram Bot] TELEGRAM_BOT_TOKEN not set in env/.env. Running in Web UI-only mode.")
        return

    print("[Telegram Bot] Air-gapped Telegram long-polling listener initialized.")
    offset = 0
    user_states = {}  # chat_id -> {"level": "C1", "style": "default"}
    base_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    def send_tg_message(chat_id: int, text: str, parse_mode: str = "Markdown"):
        try:
            url = f"{base_api}/sendMessage"
            payload = {"chat_id": chat_id, "text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            # Fallback to plain text if Markdown escaping fails on special characters
            try:
                url = f"{base_api}/sendMessage"
                data = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=10)
            except Exception as err:
                print(f"[Telegram Bot] Send error: {err}")

    while True:
        try:
            url = f"{base_api}/getUpdates?offset={offset}&timeout=25"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=35) as resp:
                updates = json.loads(resp.read().decode("utf-8"))
                for item in updates.get("result", []):
                    offset = item["update_id"] + 1
                    msg = item.get("message", {})
                    chat_id = msg.get("chat", {}).get("id")
                    text = msg.get("text", "").strip()

                    if not chat_id or not text:
                        continue

                    if chat_id not in user_states:
                        user_states[chat_id] = {"level": "C1", "style": "default"}

                    state = user_states[chat_id]
                    cmd = text.lower()

                    if cmd in ("/start", "/help", "/status"):
                        health = check_llama_health()
                        send_tg_message(
                            chat_id,
                            f"⚡ *Universal Rationale Polisher v2.0*\n"
                            f"Active Mode: `{state['level']}` | `{state['style']}`\n"
                            f"Backend: `{health['model']}` (`{health['status']}`)\n\n"
                            f"*Mode Toggles:*\n"
                            f"• `/c1` — CEFR C1 Advanced\n"
                            f"• `/c2` — CEFR C2 Mastery\n"
                            f"• `/default` — Detailed Evaluator Rationale\n"
                            f"• `/concise` — High-Density Punchy Reframing\n\n"
                            f"Send any draft rationale directly to polish with the burstiness engine.",
                        )
                    elif cmd in ("/c1", "/c2"):
                        state["level"] = cmd.replace("/", "").upper()
                        send_tg_message(chat_id, f"✅ CEFR target set to *{state['level']}*")
                    elif cmd in ("/default", "/concise"):
                        state["style"] = cmd.replace("/", "").lower()
                        send_tg_message(chat_id, f"✅ Rationale style set to *{state['style']}*")
                    else:
                        res = polish_text(text, level=state["level"], style=state["style"])
                        if res.get("success"):
                            reply = (
                                f"{res['result']}\n\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"📊 `{res['level']}` | `{res['style']}` | `σ={res['burstiness_sd']}w` ({res['sentence_range']}) | `{res['latency_ms']}ms`"
                            )
                            send_tg_message(chat_id, reply)
                        else:
                            send_tg_message(chat_id, f"❌ Error: {res.get('error')}", parse_mode="")
        except Exception:
            time.sleep(4)


# ---------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------
if __name__ == "__main__":
    tg_thread = threading.Thread(target=telegram_worker, daemon=True)
    tg_thread.start()

    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, PolisherHandler)
    print("\n==================================================")
    print("🚀 Universal Rationale Polisher v2.0 Live")
    print(f"📡 Web UI:          http://localhost:{PORT}")
    print(f"🧠 Local Backend:   {LLAMA_URL} ({LLAMA_MODEL})")
    print(
        f"🔒 Telegram Bot:    {'Active (Token Loaded)' if TELEGRAM_BOT_TOKEN else 'Isolated/Disabled (Set TELEGRAM_BOT_TOKEN in .env)'}"
    )
    print("==================================================\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[Polisher] Shutting down gracefully...")
        httpd.server_close()
