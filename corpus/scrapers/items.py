import scrapy


class DocumentItem(scrapy.Item):
    source = scrapy.Field()
    url = scrapy.Field()
    title = scrapy.Field()
    raw_content = scrapy.Field()
    category = scrapy.Field()
    subcategory = scrapy.Field()
    language = scrapy.Field()
    published_at = scrapy.Field()
    metadata = scrapy.Field()
