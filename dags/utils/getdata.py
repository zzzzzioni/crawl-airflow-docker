import pymongo
from pymongo import MongoClient
from datetime import datetime


# 몽고 DB에서 데이터 추출
def get_data_mallname(mongo_uri, mallname):
    mongo_uri = mongo_uri

    client = MongoClient(mongo_uri)
    db = client.shopai

    prices_collection = db.prices
    
    query = {
    'mallName' : mallname
    }

    docs = prices_collection.find(query)

    return docs

# get collection
def get_collection(mongo_uri):
    mongo_uri = mongo_uri

    client = MongoClient(mongo_uri)
    db = client.shopai

    products_collection = db.products
    prices_collection = db.prices
    categories_collection = db.categories

    return products_collection, prices_collection, categories_collection

# 쿠팡 데이터 추출
def get_coupang_info(mongo_uri):
    products_collection, prices_collection, categories_collection = get_collection(mongo_uri)
    date_to = datetime(2024, 8, 1)
    date_from = datetime(2024, 7, 31)

    # mongo db에서 쿠팡 url만 가져오기
    #query01 = {"mallName" : "쿠팡", 'finishedAt': {'$lt': date_to}}
    query01 = {"mallName" : "쿠팡", 'startedAt': {'$gt': date_from}}
    query02 = {"_id" : 1, "productId":1, "mallUrl" : 1}
    prices_coupang = prices_collection.find(query01, query02)

    product_ids, price_ids, url_list = [], [], []

    for price in prices_coupang:
        price_ids.append(price["_id"])
        url_list.append(price["mallUrl"])

    return price_ids, url_list