
import asyncio
import json
from crawl4ai import *
from bs4 import BeautifulSoup

async def main():
    # ฟังก์ชันช่วยเช็ค svg ดาว active (สีส้ม)
    def is_active_star(svg):
        # Accept Wongnai orange/yellow star colors: #F95700, #F7A707, #F9xxxx, #F7xxxx
        def is_active_color(val):
            if not val:
                return False
            val = val.lower()
            # Accept Wongnai orange/yellow/red star colors
            if val.startswith('#f9') or val.startswith('#f7') or val.startswith('#cd'):
                return True
            if val in ['#f95700', '#f7a707', '#cd1201']:
                return True
            return False
        # Check color attribute
        if svg.has_attr("color") and is_active_color(svg["color"]):
            return True
        if svg.has_attr("fill") and is_active_color(svg["fill"]):
            return True
        if svg.has_attr("style") and ("#f9" in svg["style"].lower() or "#f7" in svg["style"].lower()):
            return True
        return False
    async with AsyncWebCrawler() as crawler:
        import os
        # เตรียมโฟลเดอร์ output และ data
        output_dir = os.path.join(os.path.dirname(__file__), "output")
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        reviews = []
        # วนดึงทุกหน้า business (เช่น 1-2 หน้าเป็นตัวอย่าง)
        import random
        for page in range(1, 100):  # เปลี่ยนเป็น 1-6 เพื่อดึง 5 หน้า
            url = f"https://www.wongnai.com/businesses?regions=9681&categoryGroupId=9&page.size=10&rerank=false&domain=1&page.number={page}"
            result = await crawler.arun(url=url)
            soup = BeautifulSoup(result.html, "html.parser")
            # หา href ร้าน
            seen_reviews = set()  # ป้องกันรีวิวซ้ำ
            import re
            for a in soup.select('a[href^="/restaurants/"]'):
                business_url = a['href']
                # เพิ่ม delay เล็กน้อยระหว่าง request ร้าน (0.5-1.5 วินาที)
                await asyncio.sleep(random.uniform(0.5, 1.5))
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
                # --- Flexible star detection for reviews ---
                for parent in soup2.find_all("div", class_="mb-8 mb-6-mWeb"):
                    all_divs = parent.find_all("div")
                    # ใช้ class ที่ยืดหยุ่น: ต้องมีทั้ง font-highlight, mb-8, fpuVLl
                    review_blocks = [d for d in all_divs if d.get('class') and all(c in d.get('class') for c in ["font-highlight", "mb-8", "fpuVLl"])]
                    for review_block in review_blocks:
                        # หัวข้อรีวิว (แบบตัวอย่าง Wongnai)
                        title_tag = review_block.find("h5")
                        title = title_tag.get_text(strip=True) if title_tag else ""
                        # ข้อความรีวิว: <p class="sc-1gcav05-0"> ที่อยู่ถัดไป (next)
                        p = review_block.find_next("p", class_="sc-1gcav05-0")
                        text = p.get_text(strip=True).replace("\r\n", " ").replace("\n", " ").replace("\r", " ") if p else ""
                        # ลบคำว่า 'ดูเพิ่มเติม' หรือ 'อ่านต่อ' ที่ท้ายประโยค
                        for tail in ["ดูเพิ่มเติม", "อ่านต่อ"]:
                            if text.endswith(tail):
                                text = text[: -len(tail)].rstrip()
                        # clean up
                        for tail in ["ดูเพิ่มเติม", "อ่านต่อ"]:
                            if text.endswith(tail):
                                text = text[: -len(tail)].rstrip()
                        # Remove date/view count at the start (e.g., '3 ก.ค. 2024 ดูแล้ว 3,079')
                        import re
                        # Pattern: date (1-2 digit) space (เดือน) space (ปี) space 'ดูแล้ว' space number (with comma)
                        text = re.sub(r'^\d{1,2} [ก-ฮ]+\. \d{4} ดูแล้ว [\d,]+\s*', '', text)
                        # Remove relative date (e.g., 'เมื่อ 2 เดือนที่แล้ว ดูแล้ว 63')
                        text = re.sub(r'^เมื่อ \d+ เดือนที่แล้ว ดูแล้ว [\d,]+\s*', '', text)
                        # Remove date only (e.g., '3 ก.ค. 2024') if present
                        text = re.sub(r'^\d{1,2} [ก-ฮ]+\. \d{4}\s*', '', text)
                        # Skip if text is still just date/view format after cleaning
                        if re.match(r'^[\d\s,ก-ฮ\.\-เมื่อที่แล้วดูแล้ว]+$', text.strip()):
                            continue
                        # Flexible: หา next sibling div ที่มี svg ดาวสีส้ม (color="#F95700")
                        star = 0
                        next_div = review_block.find_next_sibling("div")
                        found_star_div = False
                        while next_div:
                            all_svgs = next_div.find_all("svg")
                            svg_stars = [svg for svg in all_svgs if svg.has_attr("xmlns") and svg["xmlns"] == "http://www.w3.org/2000/svg" and is_active_star(svg)]
                            if len(svg_stars) > 0:
                                star = len(svg_stars)
                                found_star_div = True
                                break
                            next_div = next_div.find_next_sibling("div")
                        # fallback: หา svg ดาว active ใน review_block ด้วย (บางกรณี)
                        if not found_star_div or star == 0:
                            all_svgs = review_block.find_all("svg")
                            for svg in all_svgs:
                                color_val = svg.get("color", "")
                                fill_val = svg.get("fill", "")
                            svg_stars = [svg for svg in all_svgs if svg.has_attr("xmlns") and svg["xmlns"] == "http://www.w3.org/2000/svg" and is_active_star(svg)]
                            star = len(svg_stars)
                        # DEBUG: print after star is set
                        # print(f"[DEBUG] Review block: title='{title[:30]}', text found={bool(text)}, star={star}")
                        # print(f"[DEBUG] ADD REVIEW: title='{title[:30]}', text='{text[:30]}', star={star}")
                        # ป้องกันรีวิวซ้ำ (ใช้ canonical_url, title, text เป็น key)
                        review_key = (canonical_url, title, text)
                        # เอาเฉพาะรีวิวที่มีดาวเท่านั้น (star > 0)
                        if text and star > 0 and review_key not in seen_reviews:
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
                                # "business_name": business_name,
                                # "business_url": canonical_url,
                                # "title": title,
                                "text": text,
                                "star": star,
                                "sentiment": sentiment
                            })
        # บันทึกเป็น JSONL
        import datetime
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        output_path = os.path.join(output_dir, f"reviews_{date_str}_{len(reviews)}.jsonl")
        with open(output_path, "w", encoding="utf-8") as f:
            for item in reviews:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"Done! Saved {len(reviews)} reviews to {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
