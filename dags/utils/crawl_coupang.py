from datetime import timedelta
import pendulum
local_tz = pendulum.timezone("Asia/Seoul")
import time 
import yaml
import pandas as pd
import numpy as np 
import requests
import re
from bs4 import BeautifulSoup

from glob import glob
import warnings
warnings.filterwarnings('ignore')

from airflow.models import DAG
from airflow.utils.dates import days_ago
from airflow.operators.python import PythonOperator, PythonVirtualenvOperator
from airflow.operators.dummy import DummyOperator
from airflow.decorators import task

import sys
sys.path.append("/opt/airflow/dags/utils")

from utils import *
from utils.getdata import *
from utils.insertdata import *

import smtplib
from email.mime.text import MIMEText
from datetime import date, datetime, timezone, timedelta


## function 01 ##
### Price Extract ###
def coupang_info_manual():
    
    headers_02 = {'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                  'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3'}

    # url 정보 가져오기
    with open('/opt/airflow/dags/mongo.yaml') as f:
        config = yaml.safe_load(f)

    mongo_uri = config["config"]["mongo_uri"]

    products_collection, prices_collection, categories_collection = get_collection(mongo_uri)
    price_ids, url_list = get_coupang_info(mongo_uri)

    # 쿠팡 가격 정보
    origin_price, total_price_01, total_price_02 = [], [], []
    # 쿠팡 와우 회원 전용 가격 파악 목적
    price_text_01, price_text_02, price_text_03 = [], [], []
    # 배송 정보
    fee_info = []

    for url in tqdm(url_list):

        if "link." in url:
            default = "https://coupang.com/vp/products/"
            page_no = url.split('&')[0].split('?')[1].split('=')[1]
            itemid = url.split('&')[3]

            url = default + page_no + '?' + itemid

        try:
            res = requests.get(url, headers = headers_02)
            res.raise_for_status() # 웹페이지의 상태가 정상인지 확인
            print(url)

            soup = BeautifulSoup(res.text, "lxml")
            items = soup.find_all("div", attrs={"class":re.compile("prod-atf-main")})

            # 상품이 없는 URL
            if len(items) == 0:
                origin_price.append("No URL")
                total_price_01.append("No URL")
                total_price_02.append("No URL")
                fee_info.append("No URL")
                price_text_01.append("No URL")
                price_text_02.append("No URL")
                price_text_03.append("No URL")

            else:
                item = items[0]

                # 최 상단 가격 정보 확인
                try:
                    origin_price_ = item.find("span", attrs = {"class":"origin-price"}).text
                    origin_price_ = origin_price_.replace("\n", "")
                    origin_price_ = origin_price_.replace(",", "")
                    origin_price_ = origin_price_.replace("원", "")
                    origin_price_ = origin_price_.replace(" ", "")
                    origin_price.append(origin_price_)
                except:
                    origin_price.append(None)
            
                # 최종 가격 1차 확인
                try:
                    total_price_01_ = item.find_all("span", attrs = {"class": "total-price"})[0].text
                    total_price_01_ = total_price_01_.replace("\n", "")
                    total_price_01_ = total_price_01_.replace(",", "")
                    total_price_01_ = total_price_01_.replace("원", "")
                    total_price_01.append(total_price_01_)
                except:
                    total_price_01.append(None)
            
                #최종 가격 2차 확인
                try:
                    total_price_02_ = item.find_all("span", attrs = {"class": "total-price"})[1].text
                    total_price_02_ = total_price_02_.replace("\n", "")
                    total_price_02_ = total_price_02_.replace(",", "")
                    total_price_02_ = total_price_02_.replace("원", "")
                    total_price_02.append(total_price_02_)
                except:
                    total_price_02.append(None)

                # 배송비 확인
                try:
                    try:
                        fee_ = item.find("div", attrs = {"class":"prod-shipping-fee-message"}).text.replace("\n", "")

                    except:
                        fee_ = item.find("span", attrs = {"class":"shipping-fee-txt"}).text.replace("\n", "")

                    try:
                        if ("무료배송" in fee_) and ("판매자" in fee_):
                            fee_ = item.find("div", attrs = {"class":"delievery-fee-info"}).text.replace("\n", "")
                            fee_info.append(fee_)
                        else:
                            fee_info.append(fee_)

                    except:
                        fee_info.append(None)

                except:
                    fee_info.append(None)


                # 로켓와우 회원 전용 확인
                try:
                    text_01 = item.find("em", attrs = {"class" : "prod-txt-onyx prod-txt-blue"}).text
                    price_text_01.append(text_01)

                except:
                    price_text_01.append(None)

                # 가격 유형 텍스트 추출
                try:
                    text_02 = item.find_all("span", attrs = {"class" : "price-txt-info font-medium"})[0].text
                    price_text_02.append(text_02)
                except:
                    price_text_02.append(None)

                try:
                    text_03 = item.find_all("span", attrs = {"class":"price-txt-info font-medium"})[1].text
                    price_text_03.append(text_03)
                except:
                    price_text_03.append(None)

            time.sleep(np.random.randint(1, 4, 1)[0])
        
        except:
            origin_price.append("No URL")
            total_price_01.append("No URL")
            total_price_02.append("No URL")
            fee_info.append("No URL")
            price_text_01.append("No URL")
            price_text_02.append("No URL")
            price_text_03.append("No URL")

    res = pd.DataFrame(columns = ["price_id",
                              'origin_price',
                              'total_price_01',
                              'total_price_02',
                              "fee_info",
                              "user_dist",
                              "price_text_01",
                              "price_text_02",
                              "mall_url"],
                   index = range(len(origin_price)))

    res.price_id = price_ids
    res.mall_url = url_list
    res.origin_price = origin_price
    res.total_price_01 = total_price_01
    res.total_price_02 = total_price_02
    res.fee_info = fee_info
    res.user_dist = price_text_01
    res.price_text_01 = price_text_02
    res.price_text_02 = price_text_03

    clear_result = res[~((res['total_price_01'].isnull()) | (res['total_price_01'] == "No URL"))].reset_index(drop = True)

    user_price_01 = [] # 일반 회원
    user_price_02 = [] # 와우 회원
    final_fee = []

    c_origin_price = np.array(clear_result['origin_price'].fillna(9999999), dtype = int)
    c_total_price_01 = np.array(clear_result['total_price_01'].fillna(9999999), dtype = int)
    c_total_price_02 = np.array(clear_result['total_price_02'].fillna(9999999), dtype = int)

    c_fee = np.array(clear_result['fee_info'].fillna(''), dtype = str)
    c_user_dist = np.array(clear_result['user_dist'].fillna(''), dtype = str)
    c_price_text_01 = np.array(clear_result['price_text_01'].fillna(''), dtype = str)
    c_price_text_02 = np.array(clear_result['price_text_02'].fillna(''), dtype = str)

    for idx in range(len(clear_result)):
        tmp_price = []
        
        tmp_price.append(c_origin_price[idx])
        tmp_price.append(c_total_price_01[idx])
        tmp_price.append(c_total_price_02[idx])

        #print(np.min(tmp_price))
        # 와우 회원 전용인 경우
        if c_user_dist[idx] == "로켓와우 전용":
            user_price_01.append(-1)
            user_price_02.append(np.min(tmp_price))

            final_fee.append(str(0))

        elif ("로켓" in c_fee[idx]):
            user_price_01.append(-1)
            user_price_02.append(np.min(tmp_price))

            final_fee.append(str(0))

        else:
            if ("와우" in c_price_text_02[idx]):
                user_price_01.append(sorted(tmp_price)[1])
                user_price_02.append(sorted(tmp_price)[0])

                final_fee.append(str(0))

            else:
                user_price_01.append(np.min(tmp_price))
                user_price_02.append(-1)

                final_fee.append(c_fee[idx])

    clear_result.insert(9, "n_user_price", user_price_01)
    clear_result.insert(10, "y_user_price", user_price_02)
    clear_result.insert(11, "final_fee", final_fee)

    final_result = clear_result.reset_index(drop = True).copy()
    
    final_result['n_user_price'] = pd.to_numeric(final_result['n_user_price'], errors='coerce')
    final_result['y_user_price'] = pd.to_numeric(final_result['y_user_price'], errors='coerce')

    # 조건에 따라 final_price 계산
    final_result['final_price'] = final_result.apply(
        lambda row: row['n_user_price'] if row['y_user_price'] == -1 else row['y_user_price'],
        axis=1
    )
    
    def get_final_fee(fee_info):
        if "무료배송" in fee_info:
            return int(0)
            
        elif "배송비" in fee_info:
            fee_tmp = fee_info.split(" ")[1].replace(',', '').replace('원', '')
            fee_tmp = int(fee_tmp)

            return fee_tmp

        else:
            return int(0)
    
    
    final_result["final_fee"] = final_result['final_fee'].apply(lambda x : get_final_fee(x))

    two_price_result = final_result[(final_result["n_user_price"] != -1) & (final_result["y_user_price"] != -1)].reset_index(drop = True)
    final_result = final_result[~final_result["price_id"].isin(two_price_result["price_id"])].reset_index(drop = True)

    insert_prices = []

    for idx in range(len(final_result)):
        pid = final_result['price_id'][idx]
        tmp_price = int(final_result['final_price'][idx])
        tmp_fee = int(final_result['final_fee'][idx])

        insert_price = tmp_price + tmp_fee
        insert_prices.append(insert_price)

    return insert_prices, list(final_result['price_id'])