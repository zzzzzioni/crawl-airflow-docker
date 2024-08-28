from datetime import datetime, timedelta
import time
import pendulum
local_tz = pendulum.timezone("Asia/Seoul")

from glob import glob
import warnings
warnings.filterwarnings('ignore')

from airflow.models import DAG
from airflow.utils.dates import days_ago
from airflow.operators.python import PythonOperator, PythonVirtualenvOperator
from airflow.operators.dummy import DummyOperator
from airflow.decorators import task


import pymongo
from pymongo import MongoClient
from bson import ObjectId
import json

import pandas as pd
import numpy as np

import urllib
from tqdm import tqdm

import re
import requests
from bs4 import BeautifulSoup

import sys
sys.path.append("/opt/airflow/dags/utils")

from utils import *
from utils.getdata import *
from utils.insertdata import *

def get_naver_url(keyword):
    keyword = keyword
    
    ########################################
    client_id = ""
    client_secret = ""
    ########################################
    query = urllib.parse.quote(keyword)
    display = "100"  #### display 한 번에 표시할 검색 결과 개수
    
    url = (
        "https://openapi.naver.com/v1/search/shop?query="
        + query
        + "&display="
        + display
    )

    request = urllib.request.Request(url)
    request.add_header("X-Naver-Client-Id", client_id)
    request.add_header("X-Naver-Client-Secret", client_secret)
    
    response = urllib.request.urlopen(request)
    
    json_response = response.read().decode("utf-8")
    
    # Parse the JSON response
    data = json.loads(json_response)
    ########################################
    ########################################
    items = data["items"]
    
    product_name = []
    product_base_price = []
    product_price = []
    product_unit_price = []
    delivery_fee = []
    rocket_type = []
    product_url = []
    product_thumbnail = []
    review_count = []
    source = []
    
    for item in items:
        title = item['title']
        title = title.replace('<b>', '').replace('</b>', '')
        product_name.append(title)
    
        price = item['lprice']
        try:
            #price = int(price)
            price = price
        except:
            price = price
        product_base_price.append(price)
    
        product_price.append(None)
        product_unit_price.append(None)
        delivery_fee.append(None)
        rocket_type.append(None)
        product_url.append(item['link'])
        product_thumbnail.append(item['image'])
        review_count.append(None)
        if 'smartstore' in item['link']:
            source.append('네이버')
        else:
            source.append(item['mallName'])
    
    
    naver_df = pd.DataFrame(columns = [
                                         'keyword',
                                         'source',
                                         'product_name',
                                         'product_base_price',
                                         'product_price',
                                         'product_unit_price',
                                         'delivery_fee',
                                         'rocket_type',
                                         'product_url',
                                         'product_thumbnail',
                                         'product_review_count'
                                        ], index = range(len(product_name)))
    
    naver_df['keyword'] = keyword
    naver_df['source'] = source
    naver_df['product_name'] = product_name
    naver_df['product_base_price'] = product_base_price
    naver_df['product_price'] = product_price
    naver_df['product_unit_price'] = product_unit_price
    naver_df['delivery_fee'] = delivery_fee
    naver_df['rocket_type'] = rocket_type
    naver_df['product_url'] = product_url
    naver_df['product_thumbnail'] = product_thumbnail

    naver_df['source'] = np.array(naver_df['source'], dtype = str)

    naver_df = naver_df[naver_df['source'] != "네이버 네이버"].reset_index(drop = True)
    naver_df = naver_df[~(naver_df["source"].str.contains('쿠팡'))].reset_index(drop = True)

    return naver_df


## function 01 ##
### Price Extract ###
def naver_info_manual():
    mongo_uri = ""

    client = MongoClient(mongo_uri)
    db = client.shopai

    products_collection = db.products
    prices_collection = db.prices
    categories_collection = db.categories


    # Product DB 정의
    query_01 = {}
    query_02 = {"brand" : 1, "name" : 1, "options" : 1}

    products_docs = products_collection.find(query_01, query_02)

    product_ids, brand, name, options = [], [], [], []

    for doc in products_docs:
        product_ids.append(doc['_id'])
        brand.append(doc['brand'])
        name.append(doc['name'])
        options.append(doc['options'])

    opts = []

    for option in options:
        opt = []
        for option_value in option:
            opt.append(option_value["value"])

        opts.append(opt)

    opt_result = []

    for opt in opts:
        result = ''

        for op in opt:
            try:
                result += op
                result += ' '
            except:
                result = result

        opt_result.append(result.rstrip())
        

    product_df = pd.DataFrame(columns = ['product_ids', 'brand', 'name', 'options'],
                            index = range(len(product_ids)))

    product_df['product_ids'] = product_ids
    product_df['brand'] = brand
    product_df['name'] = name
    product_df['options'] = opt_result

    # 키워드 정의
    keywords = []

    for i in range(len(product_ids)):
        tmp = ''
        keyword = tmp + brand[i] + ' ' + name[i] + ' ' + opt_result[i]
        keywords.append(keyword.rstrip())
        
        #tmp = ''
        #keyword = tmp + brand[i] + ' ' + name[i]
        #keywords.append(keyword)

        #keywords.append(name[i])
        

    # url 수집
    init_df = pd.DataFrame(columns = [
                                    'keyword',
                                    'source',
                                    'product_name',
                                    'product_base_price',
                                    'product_price',
                                    'product_unit_price',
                                    'delivery_fee',
                                    'rocket_type',
                                    'product_url',
                                    'product_thumbnail',
                                    'product_review_count'],
                            index = range(0))

    for keyword in tqdm(keywords):
        try:
            naver_url_df = get_naver_url(keyword)
            naver_url_df = naver_url_df[naver_url_df['product_url'].str.contains('smart')].reset_index(drop = True)

            init_df = pd.concat([init_df, naver_url_df], axis = 0).reset_index(drop = True)
        #time.sleep(2)
        except:
            pass

    db_naver_list = []
    db_naver_ids = []
    db_naver_mallName = []
    db_naver_recent_price = []
    db_naver_pid = []

    date_to = datetime(2024, 8, 1)
    date_from = datetime(2024, 7, 31)

    #query01 = {"mallName": {"$regex": "네이버"}, 'finishedAt': {'$lt': date_to}}
    query01 = {"mallName": {"$regex": "네이버"}, 'startedAt': {'$gt': date_from}}
    query02 = {"mallUrl" : 1, "logs": 1, "mallName" : 1, "productId":1}

    naver_docs = prices_collection.find(query01, query02)

    for doc in naver_docs:
        db_naver_list.append(doc['mallUrl'])
        db_naver_ids.append(doc['_id'])
        db_naver_mallName.append(doc['mallName'])
        db_naver_recent_price.append(doc['logs'][-1]['amount'])
        db_naver_pid.append(doc['productId'])


    naver_api_result = init_df[init_df['product_url'].isin(db_naver_list)].reset_index(drop = True)
    naver_api_result = naver_api_result.loc[: ,['source', 'product_base_price', 'product_url']]
    naver_api_result.columns = ['source', 'product_price', 'url']
    naver_api_result = naver_api_result.drop_duplicates().reset_index(drop = True)

    naver_fee = pd.read_excel('/opt/airflow/dags/output/check_fee.xlsx')
    naver_fee = naver_fee.loc[:, ['price_id', 'url', 'fee']]

    naver_merge = pd.merge(naver_api_result, naver_fee, on = 'url', how = 'left')

    def get_oid(id_):
        return ObjectId(id_)

    naver_merge['price_id'] = naver_merge['price_id'].apply(lambda x : get_oid(x))



    db_naver_df = pd.DataFrame(columns = ['product_id',
                                        'price_id',
                                        'mallName',
                                        'mallurl',
                                        'recent_price'],
                            index = range(len(db_naver_list)))

    db_naver_df["product_id"] = db_naver_pid
    db_naver_df["price_id"] = db_naver_ids
    db_naver_df["mallName"] = db_naver_mallName
    db_naver_df['mallurl'] = db_naver_list
    db_naver_df['recent_price'] = db_naver_recent_price

    no_merge_naver = db_naver_df[~(db_naver_df['price_id'].isin(naver_merge['price_id']))].reset_index(drop = True)



    price_ids = np.array(naver_merge["price_id"])
    prices = np.array(naver_merge["product_price"])
    fees = np.array(naver_merge["fee"])

    # for airflow test
    now = time
    test_df = pd.DataFrame(columns = ["id", "price", "time"], index = range(len(price_ids)))
    test_df.time = now.strftime('%Y-%m-%d %H:%M:%S')
    test_df.price = prices 
    test_df.id = price_ids
    test_df.to_excel('/opt/airflow/dags/output/naver_extracted.xlsx')    

    # for airflow test
    # for idx in range(len(price_ids)):
    #     price_id = price_ids[idx]

    #     price = int(prices[idx])
    #     fee = int(fees[idx])

    #     insert_price = int(price + fee)

    #     new_logs = {
    #         "amount": insert_price,
    #         'createdAt' : datetime.utcnow(),
    #         'updatedAt' : datetime.utcnow()}

    #     query01 = {'_id': ObjectId(price_id)}
    #     query02 = {"$push" : {"logs" : new_logs}}

    #     result = prices_collection.update_one(query01, query02)
    #     result = prices_collection.update_one(
    #         query01,
    #         {'$set': {'updatedAt': datetime.utcnow()}})



    price_ids = np.array(no_merge_naver["price_id"])
    prices = np.array(no_merge_naver["recent_price"])

    # for airflow test
    now = time
    test_df = pd.DataFrame(columns = ["id", "price", "time"], index = range(len(price_ids)))
    test_df.time = now.strftime('%Y-%m-%d %H:%M:%S')
    test_df.price = prices 
    test_df.id = price_ids
    test_df.to_excel('/opt/airflow/dags/output/naver_extracted_add.xlsx')    


    # for airflow test
    # for idx in range(len(price_ids)):
    #     price_id = price_ids[idx]
    #     price = int(prices[idx])

    #     insert_price = price

    #     new_logs = {
    #         "amount": insert_price,
    #         'createdAt' : datetime.utcnow(),
    #         'updatedAt' : datetime.utcnow()}

    #     query01 = {'_id': ObjectId(price_id)}
    #     query02 = {"$push" : {"logs" : new_logs}}

    #     result = prices_collection.update_one(query01, query02)
    #     result = prices_collection.update_one(
    #         query01,
    #         {'$set': {'updatedAt': datetime.utcnow()}})
    


## connect function ##
args = {'owner': 'zzioni',
        'start_date': days_ago(n=1),
        'tzinfo' : local_tz}

with DAG(dag_id = 'update_naver',
          default_args = args,
          schedule_interval = timedelta(hours = 6)) as dag:

    start = DummyOperator(task_id = 'dummy_start', dag = dag)
    end = DummyOperator(task_id = 'dummy_end', dag = dag)

    t1 = PythonOperator(task_id = 'update_naver',
                        provide_context = True,
                        python_callable = naver_info_manual,
                        dag = dag)

    start >> t1 >> end
