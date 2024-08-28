import pymongo
from pymongo import MongoClient
from datetime import date, datetime, timezone, timedelta
from tqdm import tqdm


def insert_price_info(
    prices_collection,
    price,
    prices_id):

    for i in range(len(price)):
        if price[i] != -1:
            try:
                query = {
                    '_id' : prices_id[i]
                }

                new_logs = {
                    "amount": int(price[i]),
                    'createdAt' : datetime.utcnow(),
                    'updatedAt' : datetime.utcnow()}

                result = prices_collection.update_one(
                    {
                        '_id' : prices_id[i]
                    },
                    {
                        '$push' : {'logs' : new_logs}
                    })

                result = prices_collection.update_one(
                    {
                        '_id': prices_id[i]
                    },
                    {
                        '$set': {'updatedAt': datetime.utcnow()}
                    })

            except:
                pass