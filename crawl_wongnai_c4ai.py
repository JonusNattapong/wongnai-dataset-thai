
import asyncio
import json
from crawl4ai import *
from bs4 import BeautifulSoup

async def main():
    async with AsyncWebCrawler() as crawler:
        import os
        # เตรียมโฟลเดอร์ output และ data
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        reviews = []
        # วนดึงทุกหน้า business (เช่น 1-2 หน้าเป็นตัวอย่าง)
        for page in range(1):
            url = f"https://www.wongnai.com/businesses?regions=9681&categoryGroupId=9&page.size=10&rerank=false&domain=1&page.number={page}"
            result = await crawler.arun(url=url)
            soup = BeautifulSoup(result.html, "html.parser")
            # หา href ร้าน
            seen_reviews = set()  # ป้องกันรีวิวซ้ำ
            import re
            for a in soup.select('a[href^="/restaurants/"]'):
                business_url = a['href']
                # normalize business_url: remove query string and /reviews
                base_url = business_url.split('?')[0]
                if base_url.endswith('/reviews'):
                    base_url = base_url[:-8]
                canonical_url = f"https://www.wongnai.com{base_url}"
                # ใช้ business_url เป็น key สำหรับไฟล์ html
                safe_name = re.sub(r'[<>:"/\\|?*]', '_', business_url)
                safe_name = safe_name.replace(' ', '_')[:80]
                html_path = os.path.join(data_dir, f"{safe_name}.html")
                if os.path.exists(html_path):
                    with open(html_path, "r", encoding="utf-8") as f:
                        html_content = f.read()
                else:
                    page_result = await crawler.arun(url=f"https://www.wongnai.com{business_url}")
                    html_content = page_result.html
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                soup2 = BeautifulSoup(html_content, "html.parser")
                # ดึงชื่อร้านจาก h1 หรือ element ที่แน่นอน
                business_name_tag = soup2.find("h1")
                business_name = business_name_tag.get_text(strip=True) if business_name_tag else ""
                # ใช้ logic robust แบบ test_single_restaurant.py
                for review_block in soup2.find_all("div", class_="font-highlight rg14 text-gray-550 mb-8"):
                    # หัวข้อรีวิว
                    title = review_block.find("h5")
                    title = title.get_text(strip=True) if title else ""
                    # ข้อความรีวิว (ลบ \r\n ออกด้วย)
                    p = review_block.find_next("p", class_="sc-1gcav05-0")
                    text = p.get_text(strip=True).replace("\r\n", " ").replace("\n", " ").replace("\r", " ") if p else ""
                    # ลบคำว่า 'ดูเพิ่มเติม' หรือ 'อ่านต่อ' ที่ท้ายประโยค
                    for tail in ["ดูเพิ่มเติม", "อ่านต่อ"]:
                        if text.endswith(tail):
                            text = text[: -len(tail)].rstrip()
                    # ดาว (นับ svg สีส้ม)
                    star_div = review_block.find_previous("div", class_="Gap-sc-ilei7b cJjcqk")
                    star = 0
                    if star_div:
                        star = len([svg for svg in star_div.find_all("svg") if svg.get("color") == "#F95700"])
                    # ป้องกันรีวิวซ้ำ (ใช้ canonical_url, title, text เป็น key)
                    review_key = (canonical_url, title, text)
                    if text and review_key not in seen_reviews:
                        seen_reviews.add(review_key)
                        # กำหนด sentiment ตาม star
                        if star >= 4:
                            sentiment = "positive"
                        elif star == 3:
                            sentiment = "neutral"
                        elif 1 <= star <= 2:
                            sentiment = "negative"
                        else:
                            sentiment = "unknown"
                        reviews.append({
                            "business_name": business_name,
                            # "business_url": canonical_url,
                            "title": title,
                            "text": text,
                            "star": star,
                            "sentiment": sentiment
                        })
        # บันทึกเป็น JSONL
        output_path = os.path.join(output_dir, "reviews_from_html.jsonl")
        with open(output_path, "w", encoding="utf-8") as f:
            for item in reviews:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"Done! Saved {len(reviews)} reviews to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
