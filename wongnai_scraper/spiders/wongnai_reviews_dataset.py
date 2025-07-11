import scrapy
import json

class WongnaiReviewSpider(scrapy.Spider):
    name = "wongnai_reviews_dataset"
    allowed_domains = ["wongnai.com"]
    start_urls = [
        "https://www.wongnai.com/businesses?regions=9681&categoryGroupId=9&page.size=10&rerank=false&domain=1&page.number=1"
    ]

    custom_settings = {
        'DEFAULT_REQUEST_HEADERS': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.wongnai.com/',
            'Origin': 'https://www.wongnai.com',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            # Paste your cookie string below (from your browser)
            'Cookie': 'PASTE_YOUR_COOKIE_HERE',
        },
        'DOWNLOAD_DELAY': 1.5,
    }

    def parse(self, response):
        data = json.loads(response.text)
        businesses = data.get('businesses', [])
        for business in businesses:
            business_id = business.get('id')
            if business_id:
                reviews_url = f"https://www.wongnai.com/_api/businesses/{business_id}/reviews?page.size=50&page.number=1"
                yield scrapy.Request(reviews_url, callback=self.parse_reviews, meta={'business_id': business_id, 'page': 1})

        # next page
        current_page = int(response.url.split('page.number=')[-1])
        if businesses:
            next_page = current_page + 1
            next_url = response.url.replace(f"page.number={current_page}", f"page.number={next_page}")
            yield scrapy.Request(next_url, callback=self.parse)

    def parse_reviews(self, response):
        data = json.loads(response.text)
        reviews = data.get('reviews', [])
        for review in reviews:
            text = review.get('text', '').replace('\n', ' ').strip()
            star = review.get('rating', None)
            if text and star is not None:
                yield {
                    'text': text,
                    'star': star
                }
        # next review page
        page = response.meta['page']
        business_id = response.meta['business_id']
        if reviews:
            next_page = page + 1
            next_url = f"https://www.wongnai.com/_api/businesses/{business_id}/reviews?page.size=50&page.number={next_page}"
            yield scrapy.Request(next_url, callback=self.parse_reviews, meta={'business_id': business_id, 'page': next_page})
