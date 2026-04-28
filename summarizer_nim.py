import json
from openai import OpenAI
from config import NVIDIA_API_KEY

# ── 클라이언트 설정 ──────────────────────────────
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
)
MODEL = "deepseek-ai/deepseek-v4-pro"

# ── 프롬프트 (기존 그대로 유지) ──────────────────
FILTER_PROMPT = """너는 한국 제조업 현장 전문가를 위한 뉴스레터 에디터다.
독자는 장비사 엔지니어, 생산기술 담당자, 자동화 솔루션 프로바이더다.

아래 기사 목록에서 독자에게 실질적으로 유용한 기사만 선별해라.

선별 기준:
- 현장에 바로 적용 가능한 신기술/신제품 정보
- 실무자가 알아야 할 정부 지원사업 공고
- 제조업 방향성을 파악할 수 있는 업계 동향
- 단순 기업 홍보, 인사이동, 주가/실적 뉴스는 제외
- 카테고리별 최대 5건만 선별

JSON 형식으로만 응답해. 다른 텍스트 없이:
{"selected": [0, 2, 5, 7, ...]}"""

SUMMARY_PROMPT = """너는 한국 제조업 현장 전문가를 위한 팩토릿지 뉴스레터 에디터다.
독자는 장비사 엔지니어, 생산기술 담당자, 자동화 솔루션 프로바이더다.
팩토릿지는 제조업 발주사와 장비사/솔루션 프로바이더를 연결하는 B2B 플랫폼이다.

기사를 아래 형식으로 요약해. 형식 지시어("핵심 한 줄 제목" 등)는 절대 그대로 출력하지 말 것:

📌 **[실제 핵심 제목을 여기 작성]**
→ 무엇이 달라졌는가
→ 현장에서 어떻게 쓸 수 있는가
🔍 **실무 포인트:** 핵심 1줄

카테고리별 실무 포인트 방향:
- 신기술/신제품: 기존 방식 대비 무엇이 나아졌는지, 도입 시 고려사항
- 정부지원/정책: 신청 대상/기한/지원 규모 중 핵심 1가지
- 자동화뉴스/기술: 이 트렌드가 우리 현장에 시사하는 것

규칙:
- 단순 사실 나열("~발표했다") 금지
- 영어 기사는 한국어로 번역 후 요약
- 전문용어(PLC, HMI, MES, AGV, 머신비전 등) 유지
- 홍보성 문구 제거
- 내용이 부족해도 제목만으로 추론해서 반드시 요약 완성할 것
- 4줄 초과 금지"""

INTRO_PROMPT = """너는 팩토릿지 뉴스레터 에디터다.
이번 주 수집된 기사 목록을 보고, 독자(장비사·생산기술 담당자·솔루션 프로바이더)를 위한
에디터 오프닝 코멘트를 2~3줄로 작성해라.

형식:
이번 주 제조업 현장에서 주목할 흐름: [핵심 트렌드 한 줄]
[독자에게 도움이 되는 실무 관점 1~2줄]

규칙:
- 광고/홍보 느낌 없이 동료 실무자가 쓰는 톤
- 구체적인 기술명/정책명 언급
- 2~3줄 초과 금지"""


# ── 공통 호출 함수 ───────────────────────────────
def _call(system: str, user: str, max_tokens: int = 400) -> str:
    """NIM API 호출 (스트리밍 → 문자열 조합)"""
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.7,
        top_p=0.95,
        max_tokens=max_tokens,
        extra_body={"chat_template_kwargs": {"thinking": False}},
        stream=True,
    )
    result = ""
    for chunk in stream:
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            result += delta
    return result.strip()


# ── 기사 선별 ────────────────────────────────────
def filter_articles(articles: list) -> list:
    if not articles:
        return []

    # 텔레그램 URL은 선별 없이 무조건 통과
    telegram_articles = [a for a in articles if a.get("source") == "텔레그램"]
    rss_articles      = [a for a in articles if a.get("source") != "텔레그램"]

    if not rss_articles:
        return telegram_articles

    article_list = "\n".join([
        f"[{i}] ({a['category']}) {a['title']} - {a['source']}"
        for i, a in enumerate(rss_articles)
    ])
    try:
        text = _call(FILTER_PROMPT, f"기사 목록:\n{article_list}", max_tokens=400)
        text = text.replace("```json", "").replace("```", "").strip()
        selected_idx = json.loads(text)["selected"]
        selected = [rss_articles[i] for i in selected_idx if i < len(rss_articles)]
        print(f"  → RSS {len(rss_articles)}건 중 {len(selected)}건 선별됨 + 텔레그램 {len(telegram_articles)}건 포함")
        return selected + telegram_articles
    except Exception as e:
        print(f"[FILTER ERROR] {e} → 전체 기사 사용")
        return rss_articles + telegram_articles


# ── 오프닝 생성 ──────────────────────────────────
def generate_intro(articles: list) -> str:
    article_list = "\n".join([
        f"- ({a['category']}) {a['title']}"
        for a in articles[:15]
    ])
    try:
        return _call(INTRO_PROMPT, f"이번 주 기사 목록:\n{article_list}", max_tokens=400)
    except Exception as e:
        print(f"[INTRO ERROR] {e}")
        return "이번 주 제조업 현장의 주요 소식을 정리했습니다."


# ── 개별 기사 요약 ───────────────────────────────
def summarize_article(article: dict) -> str:
    content = article.get("summary_raw", "").strip()
    if not content:
        content = f"제목 기반 요약 요청: {article['title']}"

    user_msg = (
        f"제목: {article['title']}\n"
        f"출처: {article['source']}\n"
        f"카테고리: {article['category']}\n"
        f"내용: {content[:600]}"
    )
    try:
        return _call(SUMMARY_PROMPT, user_msg, max_tokens=400)
    except Exception as e:
        print(f"[SUMMARIZE ERROR] {article['title']}: {e}")
        return f"📌 **{article['title']}**\n→ 원문: {article['link']}"


# ── 전체 실행 ────────────────────────────────────
def summarize_all(articles: list) -> tuple:
    print(f"=== NIM DeepSeek V4 Pro 선별 시작 ({len(articles)}건) ===")
    articles = filter_articles(articles)

    print("=== 에디터 오프닝 생성 중 ===")
    intro = generate_intro(articles)

    print(f"=== NIM DeepSeek V4 Pro 요약 시작 ({len(articles)}건) ===")
    for i, article in enumerate(articles):
        print(f"  [{i+1}/{len(articles)}] {article['title'][:40]}...")
        article["summary"] = summarize_article(article)

    return articles, intro
