from datetime import timedelta
import pendulum
local_tz = pendulum.timezone("Asia/Seoul")
import time 

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
from utils.crawl_11str import *

## function 01 ##
### Price Extract ###
def update_11str():
    # extract price corresponding to prices_id
    price, prices_id, deleted = extract_price_11str()
    
    
    # for airflow test
    now = time
    test_df = pd.DataFrame(columns = ["id", "price", "time"], index = range(len(price)))
    test_df.time = now.strftime('%Y-%m-%d %H:%M:%S')
    test_df.price = price 
    test_df.id = prices_id
    test_df.to_excel('/opt/airflow/dags/output/11str_extracted.xlsx')
    
    
    with open('/opt/airflow/dags/mongo.yaml') as f:
        config = yaml.safe_load(f)

    mongo_uri = config["config"]["mongo_uri"]

    # collection 가져오기
    products_collection, prices_collection, categories_collection = get_collection(mongo_uri)
    
    
    
    # 몽고DB에 가격정보 삽입
    # airflow test
    # insert_price_info(prices_collection, price, prices_id)
    
    # 실패한 URLs 엑셀로 저장 
    now = time
    false_df = pd.DataFrame(columns = ["time", "url"], index = range(len(deleted)))
    false_df.time = now.strftime('%Y-%m-%d %H:%M:%S')
    false_df.url = deleted 
    false_df.to_excel('/opt/airflow/dags/output/11str_batch_failed.xlsx')
    pass

## connect function ##
args = {'owner': 'zzioni',
        'start_date': days_ago(n=1),
        'tzinfo' : local_tz}

with DAG(dag_id = 'update_11str',
          default_args = args,
          schedule_interval = timedelta(hours=4)) as dag:

    start = DummyOperator(task_id = 'dummy_start', dag = dag)
    end = DummyOperator(task_id = 'dummy_end', dag = dag)

    t1 = PythonOperator(task_id = 'update_11str',
                        provide_context = True,
                        python_callable = update_11str,
                        dag = dag)

    start >> t1 >> end