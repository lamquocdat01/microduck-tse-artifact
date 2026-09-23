"""Bộ nối tới model. Một giao diện: `chat(messages) -> Reply`.

Ba tham số sinh văn bản được ghim GIỐNG NHAU ở mọi model, vì nếu không thì bảng so
model biến thành bảng so cấu hình:

- `temperature = 0`. Cohere đã chứng minh nhiệt độ không phải câu chuyện ở đây
  (chủ nhân dặn "đừng ôm"), nên ghim về 0 để chạy lại ra đúng số cũ.
- `max_tokens = 100`. Đúng bằng giới hạn Cohere dùng cho LPR/WPR. Đổi số này là
  bảng của ta hết so được với bảng của họ.
- Không "suy nghĩ". `gemini-2.5-flash` mặc định tiêu ngân sách token vào phần nghĩ;
  với trần 100 token thì phần nghĩ ăn hết và câu trả lời ra rỗng. `thinking_budget=0`.
  Với Ollama, model họ `qwen3` cũng có chế độ nghĩ -> `think=False`.

Mọi bộ nối trả về `Reply` có `text`, `latency_ms`, `error`. **Lỗi không ném ra
ngoài**: một lượt hỏng phải được ghi vào jsonl như một lượt hỏng, không được làm đổ
cả mẻ chạy dài mấy tiếng.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Sequence

MAX_TOKENS = 100          # đúng giới hạn của Cohere
TEMPERATURE = 0.0


@dataclass
class Reply:
    text: str
    latency_ms: float
    model: str
    error: str | None = None
    raw: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "latency_ms": round(self.latency_ms, 1),
            "model": self.model,
            "error": self.error,
            **({"raw": self.raw} if self.raw else {}),
        }


class Backend:
    name = "?"

    def chat(self, messages: Sequence[dict]) -> Reply:
        raise NotImplementedError

    def price_usd(self, in_tokens: int, out_tokens: int) -> float:
        return 0.0


# ---------------------------------------------------------------------------


class GeminiBackend(Backend):
    """`gemini-2.5-flash` qua google-genai. Cùng key với `desktop/`, không đọc .env của nó."""

    # Giá công bố cho gemini-2.5-flash (USD / 1 triệu token). Dùng để ƯỚC chi phí
    # trước khi chạy; hoá đơn thật vẫn là hoá đơn thật.
    PRICE_IN = 0.30
    PRICE_OUT = 2.50

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", timeout_s: float = 60.0):
        from google import genai
        from google.genai import types

        self._types = types
        self.name = model
        self.model = model
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        )

    def chat(self, messages: Sequence[dict]) -> Reply:
        types = self._types
        system = None
        contents = []
        for turn in messages:
            if turn["role"] == "system":
                system = turn["content"]
                continue
            role = "user" if turn["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=turn["content"])]))

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=TEMPERATURE,
            max_output_tokens=MAX_TOKENS,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        started = time.perf_counter()
        try:
            response = self.client.models.generate_content(
                model=self.model, contents=contents, config=config
            )
        except Exception as exc:                       # mất mạng, quota, lọc an toàn...
            return Reply("", (time.perf_counter() - started) * 1000, self.name,
                         error=f"{type(exc).__name__}: {exc}"[:300])
        elapsed = (time.perf_counter() - started) * 1000

        usage = getattr(response, "usage_metadata", None)
        raw = {}
        if usage is not None:
            raw = {
                "in_tokens": getattr(usage, "prompt_token_count", None),
                "out_tokens": getattr(usage, "candidates_token_count", None),
            }
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            raw["finish_reason"] = str(getattr(candidates[0], "finish_reason", ""))
        return Reply((response.text or "").strip(), elapsed, self.name, raw=raw)

    def price_usd(self, in_tokens: int, out_tokens: int) -> float:
        return (in_tokens * self.PRICE_IN + out_tokens * self.PRICE_OUT) / 1_000_000


class OllamaBackend(Backend):
    """Model local qua Ollama. Bắt buộc có, để loại giả thuyết "chỉ là quirk của Gemini".

    Chạy CPU. `docs/ADR-006` đo `qwen2.5:3b` mất 31 s cho câu đầu vì Ollama phải nạp
    model và dựng lại KV cache. Prompt của thí nghiệm này có tiền tố cố định
    (`TASK_FRAME`) nên cache tái dùng được phần đầu, nhưng vẫn phải tính vào thời gian.
    """

    def __init__(self, model: str, base_url: str = "http://localhost:11434", timeout_s: float = 600.0):
        self.name = model
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def chat(self, messages: Sequence[dict]) -> Reply:
        payload = {
            "model": self.model,
            "messages": [{"role": t["role"], "content": t["content"]} for t in messages],
            "stream": False,
            "think": False,          # qwen3 và bạn bè mặc định nghĩ trước, ăn hết trần token
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": MAX_TOKENS,
                "seed": 0,           # cùng seed -> chạy lại ra cùng chữ
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return Reply("", (time.perf_counter() - started) * 1000, self.name,
                         error=f"{type(exc).__name__}: {exc}"[:300])
        elapsed = (time.perf_counter() - started) * 1000
        text = (data.get("message") or {}).get("content", "")
        return Reply(
            text.strip(),
            elapsed,
            self.name,
            raw={
                "in_tokens": data.get("prompt_eval_count"),
                "out_tokens": data.get("eval_count"),
                "done_reason": data.get("done_reason"),
            },
        )


class DeepInfraBackend(Backend):
    """Model open-weight chạy trên DeepInfra. Song song với `OllamaBackend`, KHÔNG thay nó.

    Vì sao có cả hai: hành vi ngôn ngữ là thuộc tính của **trọng số**, không phải của
    phần cứng — nên chạy cùng trọng số ở đâu cũng được. Nhưng nửa hệ thống của bài
    (`docs/ADR-006`, số CPU cục bộ) vẫn cần đường `ollama`, nên nó ở nguyên đó và
    chọn bằng cờ `--host`.

    **Không phải cùng trọng số y hệt.** DeepInfra công bố `quantization = bfloat16`;
    bản trong ollama là `Q4_K_M` (4 bit). Đổi host ở đây cũng là đổi lượng tử hoá.
    Đó chính là thứ `scripts/host_check.py` đo, và nó phải nằm trong threat-to-validity.

    Ba thứ ghi lại mỗi lượt vì tái lập phụ thuộc vào chúng:
    `model_returned` (chuỗi model API trả về, có thể khác chuỗi ta gửi),
    `usage` thật, và `attempts` (số lần thử — lượt phải retry là lượt đáng ngờ).
    """

    BASE_URL = "https://api.deepinfra.com/v1/openai"
    # Mã đáng thử lại: quá tải phía họ hoặc giới hạn nhịp. 4xx khác là lỗi của ta,
    # thử lại chỉ tốn thêm tiền và che mất lỗi.
    RETRY_STATUS = (408, 409, 425, 429, 500, 502, 503, 504)

    def __init__(
        self,
        model: str,
        api_key: str,
        *,
        timeout_s: float = 180.0,
        max_attempts: int = 6,
        base_url: str | None = None,
    ) -> None:
        self.name = model
        self.model = model
        self.api_key = api_key
        self.timeout_s = timeout_s
        self.max_attempts = max_attempts
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.metadata = self._fetch_metadata()

    def _fetch_metadata(self) -> dict:
        """Lượng tử hoá / ngữ cảnh / giá, lấy từ chính DeepInfra và ghi vào cấu hình.

        Chủ nhân dặn: không công bố thì ghi "không công bố". Ở đây HỌ CÓ công bố
        (`quantization`), nên ghi con số thật — và chính con số ấy là lý do phải chạy
        `host_check.py`.
        """
        try:
            with urllib.request.urlopen("https://api.deepinfra.com/models/list",
                                        timeout=30) as response:
                listing = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {"quantization": "không lấy được", "error": f"{type(exc).__name__}: {exc}"}
        for entry in listing:
            if entry.get("model_name") == self.model:
                pricing = entry.get("pricing") or {}
                deprecated = entry.get("deprecated")
                return {
                    "quantization": entry.get("quantization") or "không công bố",
                    "max_tokens": entry.get("max_tokens"),
                    "usd_per_m_input": (pricing.get("cents_per_input_token") or 0) * 1e6 / 100,
                    "usd_per_m_output": (pricing.get("cents_per_output_token") or 0) * 1e6 / 100,
                    "deprecated_ts": deprecated,
                    "replaced_by": entry.get("replaced_by"),
                }
        return {"quantization": "không có trong danh sách model của DeepInfra"}

    def chat(self, messages: Sequence[dict]) -> Reply:
        payload = {
            "model": self.model,
            "messages": [{"role": t["role"], "content": t["content"]} for t in messages],
            # temperature ghi TƯỜNG MINH: mặc định của mỗi nhà cung cấp một khác, và
            # đây là điều kiện tái lập chứ không phải tinh chỉnh.
            "temperature": TEMPERATURE,
            "top_p": 1.0,
            "max_tokens": MAX_TOKENS,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        started = time.perf_counter()
        last_error = "chưa thử lần nào"

        for attempt in range(1, self.max_attempts + 1):
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=body,
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {self.api_key}"},
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                    data = json.loads(response.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", "replace")[:200]
                except Exception:
                    pass
                last_error = f"HTTP {exc.code}: {detail}"
                if exc.code not in self.RETRY_STATUS or attempt == self.max_attempts:
                    return Reply("", (time.perf_counter() - started) * 1000, self.name,
                                 error=last_error[:300], raw={"attempts": attempt})
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt == self.max_attempts:
                    return Reply("", (time.perf_counter() - started) * 1000, self.name,
                                 error=last_error[:300], raw={"attempts": attempt})
            # Lùi theo cấp số nhân + nhiễu ngẫu nhiên. Nhiễu để 8 luồng cùng bị 429
            # không cùng quay lại một lúc rồi lại cùng bị 429 lần nữa.
            time.sleep(min(30.0, 1.5 * (2 ** (attempt - 1))) * (0.5 + random.random()))
        else:                                            # hết lượt thử
            return Reply("", (time.perf_counter() - started) * 1000, self.name,
                         error=last_error[:300], raw={"attempts": self.max_attempts})

        elapsed = (time.perf_counter() - started) * 1000
        choice = (data.get("choices") or [{}])[0]
        usage = data.get("usage") or {}
        return Reply(
            (choice.get("message", {}).get("content") or "").strip(),
            elapsed,
            self.name,
            raw={
                "in_tokens": usage.get("prompt_tokens"),
                "out_tokens": usage.get("completion_tokens"),
                "finish_reason": choice.get("finish_reason"),
                # Chuỗi model API TRẢ VỀ, không phải chuỗi ta gửi: nhà cung cấp có thể
                # định tuyến sang bản khác (bản Turbo, bản thay thế) mà không báo.
                "model_returned": data.get("model"),
                "attempts": attempt,
            },
        )

    def price_usd(self, in_tokens: int, out_tokens: int) -> float:
        return (in_tokens * self.metadata.get("usd_per_m_input", 0.0)
                + out_tokens * self.metadata.get("usd_per_m_output", 0.0)) / 1_000_000


class OpenAICompatBackend(Backend):
    """Model API thứ ba: bất cứ endpoint nào nói giao thức `/v1/chat/completions`.

    CHƯA BẬT — đang chờ chủ nhân trả lời có key nào (OpenAI hay Anthropic). Viết sẵn
    theo giao thức OpenAI vì cả OpenAI lẫn Anthropic đều có endpoint tương thích;
    nếu chốt Anthropic thì đổi `base_url` và thêm header, không phải viết lại lớp này.
    Không có key thì `runner` sẽ thay bằng model local thứ hai khác họ.
    """

    def __init__(self, model: str, api_key: str, base_url: str, timeout_s: float = 120.0,
                 extra_headers: dict | None = None):
        self.name = model
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.extra_headers = extra_headers or {}

    def chat(self, messages: Sequence[dict]) -> Reply:
        payload = {
            "model": self.model,
            "messages": [{"role": t["role"], "content": t["content"]} for t in messages],
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            **self.extra_headers,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return Reply("", (time.perf_counter() - started) * 1000, self.name,
                         error=f"{type(exc).__name__}: {exc}"[:300])
        elapsed = (time.perf_counter() - started) * 1000
        text = data["choices"][0]["message"].get("content") or ""
        usage = data.get("usage") or {}
        return Reply(
            text.strip(), elapsed, self.name,
            raw={"in_tokens": usage.get("prompt_tokens"), "out_tokens": usage.get("completion_tokens")},
        )
