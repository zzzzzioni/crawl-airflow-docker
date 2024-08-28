import pymongo
from pymongo import MongoClient
import os   
from datetime import datetime, timedelta
import time
from bson import ObjectId

import pandas as pd
import numpy as np

from tqdm import tqdm

import requests
import re
from bs4 import BeautifulSoup
   
os.environ['PATH'] += ":/usr/src/chrome"

import selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def from_db(mongo_uri):
    """
    Connect to mongo DB and get data
    
    <input>
    - mongo_uri (str) : connection uri of mongo db 
    
    <output>
    - product_ids (list) : a list of product_ids 
    - price_ids (list) : a list of price_ids
    - url_list (list) : a list of urls 
    """
    
    client = MongoClient(mongo_uri)
    db = client.shopai

    products_collection = db.products
    prices_collection = db.prices
    categories_collection = db.categories

    date_to = datetime(2024, 8, 1)
    date_from = datetime(2024, 7, 31)

    #query01 = {"mallName" : "11번가", 'finishedAt': {'$lt': date_to}}
    query01 = {"mallName" : "11번가", 'startedAt': {'$gt': date_from}}
    query02 = {"_id" : 1, "productId":1, "mallUrl" : 1}
    prices_11str = prices_collection.find(query01, query02)

    product_ids, price_ids, url_list = [], [], []

    for price in prices_11str:
        price_ids.append(price["_id"])
        url_list.append(price["mallUrl"])
        product_ids.append(price["productId"])
    
    for i, e in enumerate(url_list):
        if 'Gateway' in e:
            e = 'https://www.11st.co.kr/products/pa/' + e.split('=')[-2].split('&')[0]
            url_list[i] = e
        elif 'NaPm' in e:
            e = e.split('?')[0]
            url_list[i] = e
        
    return product_ids, price_ids, url_list


def extract_price_11str():
    """
    Extract current final price of url lists with crawling

    <output>
    - price_ids (list) : a list of price_ids
    - prices (list) : a list of final prices(price + fee) corresponding to price_ids 
    """
    
    # Connect to DB and get data 
    mongo_uri = ""
    product_ids, price_ids, url = from_db(mongo_uri)
    
    # Set headers for crawling
    headers = {"User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3"}
    
    # Set Cromedriver for crawling
    chrome_options = webdriver.ChromeOptions()
    service = Service(executable_path=r"/usr/src/chrome/chromedriver")
    
    chrome_options.binary_location = "/usr/src/chrome"

    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument("log-level=3")
    chrome_options.add_argument("--single-process")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("disable-gpu")

    # driver = webdriver.Chrome(options=chrome_options)
    driver = webdriver.Chrome(service=service, options=chrome_options)
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
    # Set variable lists
    origin_price, sale_price = [], []
    fee_info = []

    # Deleted URLs
    deleted = []

    # Crawling price and price(fee) info for whole urls
    for i, url in zip(range(len(url)),url):
        res = requests.get(url, headers = headers)
        res.raise_for_status() # 웹페이지의 상태가 정상인지 확인

        soup = BeautifulSoup(res.text, "lxml")
        items = soup.find_all("div", attrs={"class":re.compile("l_product_side_info")})
        
        # 웹 비정상이면 동적크롤링 시도 
        if len(items) == 0:
            try:
                driver.get(url)
            
                price = driver.find_element(By.CSS_SELECTOR, '#finalDscPrcArea > dd.price > strong > span.value')
                price = price.text.replace(',', '')
                
                try:
                    driver.find_element(By.CSS_SELECTOR, '#layBodyWrap > div > div.s_product.s_product_detail > div.l_product_cont_wrap > div > div.l_product_view_wrap > div.l_product_summary > div.l_product_side_info > div.b_product_info_price.b_product_info_price_style2 > div > div > dl > div:nth-child(1) > dd')
                    origin = driver.find_element(By.CSS_SELECTOR, '#layBodyWrap > div > div.s_product.s_product_detail > div.l_product_cont_wrap > div > div.l_product_view_wrap > div.l_product_summary > div.l_product_side_info > div.b_product_info_price.b_product_info_price_style2 > div > div > dl > div:nth-child(1) > dd')
                    origin = origin.text.replace(',', '').replace('원', '').replace('\n', '').replace('~', '')
                    origin_price.append(origin)
                except:
                    origin = None
                
                try:
                    driver.find_element(By.CSS_SELECTOR, '#maxDiscountResult > dd.price > strong > span.value')
                    price = driver.find_element(By.CSS_SELECTOR, '#maxDiscountResult > dd.price > strong > span.value')
                    price = price.text.replace(',', '')
                except:
                    pass

                try:
                    if int(price) < int(origin):
                        sale_price.append(price)
                    else:
                        sale_price.append(None)
                except:
                    sale_price.append(None) # 0729_revised
                    
                try:
                    driver.find_element(By.XPATH, '//*[@id="layBodyWrap"]/div/div[1]/div[2]/div/div[1]/div[2]/div[2]/dl/div[3]/dt')
                    ship = driver.find_element(By.XPATH, '//*[@id="layBodyWrap"]/div/div[1]/div[2]/div/div[1]/div[2]/div[2]/dl/div[3]/dt')
                    ship = ship.text.split('\n')[1]
                    fee_info.append(ship)
                except:
                    fee_info.append(None)
                
            except:
                deleted.append(url)
                origin_price.append("No URL")
                sale_price.append("No URL")
                fee_info.append("No URL")   

        else:
            item = items[0]
            
            # 가격 셀 추출 
            try:
                price_cell = item.find("div", attrs = {"class":"c_prd_price c_product_price_basic"})
            
                # 판매가 추출 
                price = price_cell.find("div", attrs = {"id":"finalDscPrcArea"})

                price = price_cell.find("dd", attrs = {"class":"price"})
                price = price.find("span", attrs = {"class":"value"}).text
                price = price.replace(",", "")

                # 할인 가격일 때 원가 추출 및 판매가 입력 
                if price_cell.find("dd", attrs = {"class":"price_regular"}):
                    origin_price_ = price_cell.find("dd", attrs = {"class":"price_regular"}).text
                    origin_price_ = origin_price_.replace("\n", "")
                    origin_price_ = origin_price_.replace(",", "")
                    origin_price_ = origin_price_.replace("원", "")
                    origin_price_ = origin_price_.replace(" ", "")
                    origin_price.append(origin_price_)
                    sale_price.append(price)
                    
                else:
                    # 할인 안 할 때 
                    origin_price.append(price)
                    sale_price.append(None)


                # 일반배송 
                if item.find("div", attrs = {"class":"delivery"}):
                    deliv_cell = str(item.find("div", attrs = {"class":"delivery"}))    
                    deliv_info = deliv_cell.split('</span>')[1]
                    deliv_info = deliv_info.split('<button')[0]
                    deliv_info = deliv_info.strip()
                    deliv_info = deliv_info.replace("\n", "")
                    fee_info.append(deliv_info)
                
                # 해외배송 
                elif item.find("div", attrs = {"class":"delivery_abroad"}):
                    deliv_cell = str(item.find("div", attrs = {"class":"delivery_abroad"}))    
                    deliv_info = deliv_cell.split('</span>')[1]
                    deliv_info = deliv_info.split('<button')[0]
                    deliv_info = deliv_info.strip()
                    deliv_info = deliv_info.replace("\n", "")
                    fee_info.append(deliv_info)
                    
                else:
                    fee_info.append(None)
            
            except:
                # 정적크롤링으로 안 먹혔을 경우 동적 크롤링 시도 
                try:
                    driver.get(url)
                
                    price = driver.find_element(By.CSS_SELECTOR, '#finalDscPrcArea > dd.price > strong > span.value')
                    price = price.text.replace(',', '')
                    
                    try:
                        driver.find_element(By.CSS_SELECTOR, '#layBodyWrap > div > div.s_product.s_product_detail > div.l_product_cont_wrap > div > div.l_product_view_wrap > div.l_product_summary > div.l_product_side_info > div.b_product_info_price.b_product_info_price_style2 > div > div > dl > div:nth-child(1) > dd')
                        origin = driver.find_element(By.CSS_SELECTOR, '#layBodyWrap > div > div.s_product.s_product_detail > div.l_product_cont_wrap > div > div.l_product_view_wrap > div.l_product_summary > div.l_product_side_info > div.b_product_info_price.b_product_info_price_style2 > div > div > dl > div:nth-child(1) > dd')
                        origin = origin.text.replace(',', '').replace('원', '').replace('\n', '').replace('~', '')
                        origin_price.append(origin)
                    except:
                        origin = None
                    
                    try:
                        driver.find_element(By.CSS_SELECTOR, '#maxDiscountResult > dd.price > strong > span.value')
                        price = driver.find_element(By.CSS_SELECTOR, '#maxDiscountResult > dd.price > strong > span.value')
                        price = price.text.replace(',', '')
                    except:
                        pass

                    try:
                        if int(price) < int(origin):
                            sale_price.append(price)
                        else:
                            sale_price.append(None)
                    except:
                        sale_price.append(None) # 0729_revised
                        
                    try:
                        driver.find_element(By.XPATH, '//*[@id="layBodyWrap"]/div/div[1]/div[2]/div/div[1]/div[2]/div[2]/dl/div[3]/dt')
                        ship = driver.find_element(By.XPATH, '//*[@id="layBodyWrap"]/div/div[1]/div[2]/div/div[1]/div[2]/div[2]/dl/div[3]/dt')
                        ship = ship.text.split('\n')[1]
                        fee_info.append(ship)
                    except:
                        fee_info.append(None)
                    
                except:
                    deleted.append(url)
                    origin_price.append("No URL")
                    sale_price.append("No URL")
                    fee_info.append("No URL")
            
        time.sleep(np.random.choice([0.5, 1, 1.5, 2]))
    
    driver.quit()
    
    # Make DataFrame     
    res = pd.DataFrame(columns = ['product_id',
                              "price_id",
                              'origin_price',
                              'sale_price',
                              "fee_info",
                              "mall_url"],
                   index = range(len(origin_price)))

    res.product_id = product_ids
    res.price_id = price_ids
    res.mall_url = url
    res.origin_price = origin_price
    res.sale_price = sale_price
    res.fee_info = fee_info

    # Clean failed urls
    clear_result = res[~((res['origin_price'].isnull()) | (res['origin_price'] == "No URL"))].reset_index(drop = True)
    clear_result['fee_info'] = clear_result['fee_info'].fillna('무료배송')
    
    # Seperate member type
    user_price_01 = [] # 비회원
    user_price_02 = [] # 회원

    origin = np.array(clear_result['origin_price'].fillna('None'), dtype = str)
    sale = np.array(clear_result['sale_price'].fillna('None'), dtype = str)

    for idx in range(len(clear_result)):
        if sale[idx] == 'None':
            user_price_01.append(origin[idx])
            user_price_02.append(-1)
        
        else:
            user_price_02.append(sale[idx])
            user_price_01.append(origin[idx])
    
    clear_result.insert(6, "n_user_price", user_price_01)
    clear_result.insert(7, "y_user_price", user_price_02)
    
    # Preprocessing of prices 
    def get_final_price(n_user_price, y_user_price):
        """
        회원 유형별로 다른 가격 출력 
        """
        if y_user_price == -1:
            return int(n_user_price)

        elif n_user_price == -1:
            return int(y_user_price)

        elif (n_user_price != -1) and (y_user_price != -1):
            return int(y_user_price)
        
    def get_fee(info):
        """
        배송비 유형별로 다른 전처리 
        """

        if "무료배송" in info:
            fee_tmp =  int(0)
            
        elif "배송비" in info:
            fee_tmp = info.split(" ")
            if "1개당" in fee_tmp:
                fee_tmp = fee_tmp[-1].replace(',', '').replace('원', '')
            elif "(수량별" in fee_tmp:
                fee_tmp = fee_tmp[1].replace(',', '').replace('원', '')
            elif "이상" in fee_tmp:
                fee_tmp = fee_tmp[1].replace(',', '').replace('원', '')
            else:
                fee_tmp = fee_tmp[-1].replace(',', '').replace('원', '')
            
            fee_tmp = int(fee_tmp)

        else:
            fee_tmp =  int(0)
            
        return fee_tmp

    # Get 'final_price' 
    final_result = clear_result.reset_index(drop = True).copy()
    final_result["final_fee"] = final_result['fee_info'].apply(lambda x : get_fee(x))
    final_result["final_price"] = final_result.apply(lambda x : get_final_price(x.n_user_price, x.y_user_price), axis = 1)
    final_result["final_price"] = final_result["final_price"] + final_result["final_fee"]
    
    return list(final_result.final_price), list(final_result.price_id), deleted
