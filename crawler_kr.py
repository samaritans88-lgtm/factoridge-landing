import feedparser
import requests
import sqlite3
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from config import COLLECT_DAYS, MAX_ITEMS_PER_SOURCE
from db import is_seen

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FactoridgeBot/1.0)"}

EXCLUDE_KEYWORDS = [
    "제약", "바이오", "의약품", "치료제", "임상", "게임", "엔터",
    "증권", "주식", "부동산", "배터리", "양극재", "음극재",
    "연예", "스포츠", "대선", "총선", "정치"
]

RSS_SOURCES = [
    # FA/자동화 전문 매체 (직접 RSS)
    {"name": "디일렉",          "url": "https://www.thelec.kr/rss/allArticle.xml",                                                          "category": "자동화뉴스/기술"},
    {"name": "산업일보",        "url": "https://www.kidd.co.kr/rss.xml",                                                                    "category": "자동화뉴스/기술"},
    {"name": "헬로티",          "url": "https://www.hellot.net/rss/allArticle.xml",                                                         "category": "자동화뉴스/기술"},
    {"name": "FA저널",          "url": "https://www.fajournal.com/rss/allArticle.xml",                                                      "category": "자동화뉴스/기술"},

    # FA/자동화 구글뉴스
    {"name": "구글뉴스_FA전문",     "url": "https://news.google.com/rss/search?q=오토메이션월드+FA저널+자동화&hl=ko&gl=KR&ceid=KR:ko",         "category": "자동화뉴스/기술"},
    {"name": "구글뉴스_제조AI",     "url": "https://news.google.com/rss/search?q=제조+AI+자동화+스마트팩토리&hl=ko&gl=KR&ceid=KR:ko",         "category": "자동화뉴스/기술"},
    {"name": "구글뉴스_산업자동화", "url": "https://news.google.com/rss/search?q=산업자동화+설비+국내+도입&hl=ko&gl=KR&ceid=KR:ko",           "category": "자동화뉴스/기술"},
    {"name": "구글뉴스_머신비전",   "url": "https://news.google.com/rss/search?q=머신비전+비전검사+카메라+시스템&hl=ko&gl=KR&ceid=KR:ko",     "category": "신기술/신제품"},
    {"name": "구글뉴스_협동로봇",   "url": "https://news.google.com/rss/search?q=협동로봇+코봇+제조현장+도입&hl=ko&gl=KR&ceid=KR:ko",        "category": "신기술/신제품"},
    {"name": "구글뉴스_FA부품",     "url": "https://news.google.com/rss/search?q=산업용센서+PLC+HMI+신제품+출시&hl=ko&gl=KR&ceid=KR:ko",     "category": "신기술/신제품"},
    {"name": "구글뉴스_로봇시스템", "url": "https://news.google.com/rss/search?q=산업용로봇+자동화라인+구축+사례&hl=ko&gl=KR&ceid=KR:ko",    "category": "신기술/신제품"},
    {"name": "구글뉴스_신제품",     "url": "https://news.google.com/rss/search?q=제조+자동화+신제품+출시+2026&hl=ko&gl=KR&ceid=KR:ko",       "category": "신기술/신제품"},
    {"name": "구글뉴스_키엔스",     "url": "https://news.google.com/rss/search?q=키엔스+바코드+비전+신제품&hl=ko&gl=KR&ceid=KR:ko",          "category": "신기술/신제품"},
    {"name": "구글뉴스_지멘스",     "url": "https://news.google.com/rss/search?q=지멘스+스마트팩토리+자동화+한국&hl=ko&gl=KR&ceid=KR:ko",   "category": "신기술/신제품"},
    {"name": "구글뉴스_ABB로봇",    "url": "https://news.google.com/rss/search?q=ABB+로봇+한국+제조+도입&hl=ko&gl=KR&ceid=KR:ko",            "category": "신기술/신제품"},

    # 경제신문 제조업 섹션
    {"name": "전자신문_제조",       "url": "https://news.google.com/rss/search?q=전자신문+스마트팩토리+제조+자동화&hl=ko&gl=KR&ceid=KR:ko",  "category": "자동화뉴스/기술"},
    {"name": "매경_제조업",         "url": "https://news.google.com/rss/search?q=매일경제+제조업+공장+자동화&hl=ko&gl=KR&ceid=KR:ko",        "category": "자동화뉴스/기술"},
    {"name": "한경_스마트팩토리",   "url": "https://news.google.com/rss/search?q=한국경제+스마트팩토리+제조혁신&hl=ko&gl=KR&ceid=KR:ko",    "category": "자동화뉴스/기술"},
    {"name": "뉴스핌_산업",         "url": "https://news.google.com/rss/search?q=뉴스핌+제조업+산업+자동화+동향&hl=ko&gl=KR&ceid=KR:ko",    "category": "자동화뉴스/기술"},

    # 정부지원/정책
    {"name": "구글뉴스_지원사업",   "url": "https://news.google.com/rss/search?q=중소기업+제조+지원사업+공고+신청&hl=ko&gl=KR&ceid=KR:ko",  "category": "정부지원/정책"},
    {"name": "구글뉴스_스마트공장", "url": "https://news.google.com/rss/search?q=스마트공장+지원사업+신청+모집&hl=ko&gl=KR&ceid=KR:ko",    "category": "정부지원/정책"},
    {"name": "구글뉴스_제조정책",   "url": "https://news.google.com/rss/search?q=제조업+산업부+정책+지원+2026&hl=ko&gl=KR&ceid=KR:ko",     "category": "정부지원/정책"},
    {"name": "구글뉴스_공급망",     "url": "https://news.google.com/rss/search?q=공급망+제조업+국내+투자+동향&hl=ko&gl=KR&ceid=KR:ko",     "category": "정부지원/정책"},
]


def parse_date(entry) -> datetime:
    try:
        return datetime(*entry.published_parsed[:6])
    except:
        return datetime.now()


def is_relevant(title: str) -> bool:
    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return False
    return True


def fetch_rss(source: dict) -> list:
    cutoff = datetime.now() - timedelta(days=COLLECT_DAYS)
    results = []
    try:
        feed = feedparser.parse(source["url"])
        for entry in feed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "").strip()
            if not url or not title:
                continue
            if parse_date(entry) < cutoff:
                continue
            if is_seen(url):
                continue
            if not is_relevant(title):
                continue
            summary_raw = BeautifulSoup(
                entry.get("summary", "") or entry.get("description", ""),
                "html.parser"
            ).get_text()[:800]
            results.append({
                "title": title,
                "link": url,
                "summary_raw": summary_raw,
                "source": source["name"],
                "category": source["category"],
                "pub_date": parse_date(entry).strftime("%Y-%m-%d"),
            })
            if len(results) >= MAX_ITEMS_PER_SOURCE:
                break
    except Exception as e:
        print(f"[RSS ERROR] {source['name']}: {e}")
    return results


def fetch_article_content(url: str) -> str:
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(res.text, "html.parser")
        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
        return text[:800]
    except Exception as e:
        print(f"[크롤링 ERROR] {url}: {e}")
        return ""


def collect_telegram_urls() -> list:
    results = []
    try:
        conn = sqlite3.connect("/Users/openclaw/Desktop/factoridge _newsletter/seen_urls.db")
        c = conn.cursor()
        c.execute("""
            SELECT url, title, created_at FROM seen_urls
            WHERE source = '텔레그램' AND published = 0
            ORDER BY created_at ASC
            LIMIT 5
        """)
        rows = c.fetchall()
        conn.close()
        for url, title, created_at in rows:
            print(f"  [텔레그램 크롤링] {url[:50]}...")
            content = fetch_article_content(url)
            results.append({
                "title": title,
                "link": url,
                "summary_raw": content,
                "source": "텔레그램",
                "category": "자동화뉴스/기술",
                "pub_date": created_at or datetime.now().strftime("%Y-%m-%d"),
            })
    except Exception as e:
        print(f"[텔레그램 DB ERROR]: {e}")
    return results


def mark_telegram_published(urls: list):
    try:
        conn = sqlite3.connect("/Users/openclaw/Desktop/factoridge _newsletter/seen_urls.db")
        c = conn.cursor()
        for url in urls:
            c.execute("UPDATE seen_urls SET published = 1 WHERE url = ?", (url,))
        conn.commit()
        conn.close()
        print(f"  텔레그램 {len(urls)}건 발행 완료 처리")
    except Exception as e:
        print(f"[텔레그램 발행처리 ERROR]: {e}")


def collect_all() -> list:
    all_articles = []
    print("=== 기사 수집 시작 ===")
    for source in RSS_SOURCES:
        articles = fetch_rss(source)
        print(f"  {source['name']}: {len(articles)}건")
        all_articles.extend(articles)

    telegram_articles = collect_telegram_urls()
    if telegram_articles:
        print(f"  텔레그램 수동입력: {len(telegram_articles)}건")
        all_articles.extend(telegram_articles)

    print(f"=== 총 수집: {len(all_articles)}건 ===")
    return all_articles
