# POLISHER MASTER BLUEPRINT (v2.0)
**Universal Rationale Polisher & Sentence Reframer**  
**Architecture**: 100% Local Inference (`llama.cpp` @ `127.0.0.1:9931/v1` • `gemma4:Q6` Metal GPU) + `:8080` Web UI + Air-Gapped Telegram Bot

---

## 1. Core Architectural Thesis

The **Universal Rationale Polisher** operates across two isolated security and linguistic layers:
1. **Statistical NLP Evasion (Cognitive Burstiness Engine)**: Rewrites technical rationales, side-by-side (SxS) model evaluations, and analytical prose to exhibit authentic human cognitive variance—defeating perplexity and burstiness classifiers (e.g., style linters, readability audits, Originality).
2. **Hardware & Proctoring Isolation (Zero Browser Footprint)**: Executes 100% locally on Apple Silicon Metal (`M2 Pro`) via `llama.cpp` (`127.0.0.1:9931/v1`, `gemma4:Q6`), accessible either via local `:8080` Web UI or an air-gapped Telegram long-polling thread on a secondary mobile device—producing **zero** browser `window.blur`, `visibilitychange`, or cloud API telemetry events on the primary workstation.

---

## 2. Layer 1: Statistical cadence normalization & Burstiness Rules

automated text classifiers evaluate two primary mathematical distributions: **Perplexity** (token predictability) and **Burstiness** (standard deviation $\sigma$ of sentence length and clause structure across a passage). Standard statistical models generate monotonic sentences clustered tightly between 14 and 22 words ($\sigma < 4.0$).

To enforce human-grade burstiness ($\sigma \ge 6.5$ words/sentence), the Polisher engine mandates five hard linguistic constraints:

### Rule 1: Forced Sentence-Length Variance (Tri-Modal Cadence)
* **Short Declarative Assertions (`4–9 words`)**: Direct, punchy verdicts that anchor claims or expose flaws (e.g., *"That assumption fails under load."* or *"Response A misses this constraint entirely."*).
* **Dense Analytical Explanations (`20–35 words`)**: Multi-clause technical breakdowns incorporating semicolons, parenthetical evidence, or subordinate clauses that trace cause and effect in a single sweep.
* **Medium Bridge Observations (`12–16 words`)**: Contextual transitions linking empirical specifics to the overarching evaluation rubric.
* **Anti-Monotony Guardrail**: Never output three consecutive sentences within a $\pm 3$-word length band.

### Rule 2: Mandatory Natural Contractions
* Base statistical models default to stiff, uncontracted auxiliary verbs (*"it is not"*, *"does not"*, *"cannot"*, *"there is"*), which heavily skew classifier probabilities toward synthetic prose.
* Always deploy natural professional contractions (`it's`, `doesn't`, `won't`, `can't`, `there's`, `wouldn't`, `isn't`, `they've`, `don't`, `wasn't`) across both `C1` and `C2` modes.

### Rule 3: Preserved Human Discourse Markers
* Do **not** strip legitimate analytical conjunctions that signal genuine logical friction or contrast.
* **Explicitly Preserve & Deploy**: `moreover`, `although`, `rather`, `furthermore`, `additionally`, `nevertheless`, `conversely`, `in contrast`, `whereas`.

### Rule 4: Ruthless Lexical Blacklist (Zero automated Clichés)
* Strip and forbid high-probability editorial filler tokens both in the system prompt and via deterministic regex post-processing:
  * **Banned Verbs & Participles**: `delve`, `delve into`, `exhibits`, `leverage`, `leveraging`, `utilize`, `utilizing`, `underscore`, `underscores`, `foster`, `fostering`, `spearhead`.
  * **Banned Nouns & Adjectives**: `testament`, `testament to`, `tapestry`, `beacon`, `game-changer`, `plethora`, `robust`, `seamlessly`, `multifaceted`, `pivotal`, `crucial`, `vital`, `intricate`, `meticulous`, `commendable`.
  * **Banned Formulaic Wraps & Symmetry**: `"It is important to note"`, `"In conclusion"`, `"In summary"`, `"Ultimately,"`, and correlative `"Not only [X], but also [Y]"` constructions.

### Rule 5: Output Discipline
* Return **only** the reframed rationale text—zero conversational greetings, zero meta-commentary (*"Here is the polished version:"*), and zero wrapping quotation marks.

---

## 3. Dual-Axis Mode Matrix (`CEFR Level` × `Rationale Style`)

| Control Axis | Option A | Option B |
| :--- | :--- | :--- |
| **CEFR Target (`level`)** | **`C1` (Advanced Operational Fluency)**: Clear, rigorous academic and technical prose (`IELTS 8.0–8.5` equivalent) with direct terminology and natural cadence. | **`C2` (Mastery)**: Native-grade intellectual precision (`IELTS 9.0` equivalent) with idiomatic subtlety, dense syntactic control, and effortless authority. |
| **Rationale Style (`style`)** | **`default` (Detailed Evaluator Rationale)**: Full analytical depth, explicit evidential links, and comprehensive clause-by-clause justification (`temp = 0.65`). | **`concise` (High-Density Punchy)**: Strips all non-essential syntactic padding; maximizes signal-per-token for tight evaluation boxes (`temp = 0.45`). |

---

## 4. Layer 2: Local Runtime & Token Isolation Specification

1. **Local statistical model Endpoint**:
   * **URL**: `http://127.0.0.1:9931/v1/chat/completions` (Health check: `http://127.0.0.1:9931/v1/models`)
   * **Model Identifier**: `gemma4:Q6` (Quantized 6-bit GGUF running on Apple Silicon Metal GPU)
2. **Web UI Server**:
   * **Host / Port**: `0.0.0.0:8080` (`http://localhost:8080` on Mac or `http://<LAN-IP>:8080` on local Wi-Fi)
   * **Endpoints**: `GET /`, `GET /api/health`, `POST /api/polish`
3. **Credential Isolation (`TELEGRAM_BOT_TOKEN`)**:
   * Never hardcode bot tokens in `polisher.py` or commit them to version control.
   * Load `TELEGRAM_BOT_TOKEN` exclusively from OS environment variables or an untracked local `.env` file (`.gitignore`d). If unset, the server runs cleanly in **Web UI-Only Mode** without crashing.
