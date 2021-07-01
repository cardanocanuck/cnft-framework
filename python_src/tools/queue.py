import pika
from dotenv import load_dotenv
from os import getenv
import time
import psycopg2
from tools.scripts.dogs_maintenance import derive_price

connection = None
channel = None

last_heartbeat = None

load_dotenv()
rabbitmq_conn = getenv("RABBITMQ_HOST") or 'localhost'
rabbitmq_user = getenv("RABBITMQ_USER") or 'guest'
rabbitmq_pw = getenv("RABBITMQ_PW") or 'guest'
rabbitmq_params = pika.ConnectionParameters(rabbitmq_conn, credentials=pika.credentials.PlainCredentials(rabbitmq_user, rabbitmq_pw))
if getenv("TOKENS_DB_URL"):
    db_tokens = psycopg2.connect(getenv("TOKENS_DB_URL"))

def get_channel():
    global connection
    global channel
    global last_heartbeat

    
    if not (connection and connection.is_open):
        print("getting RABBITMQ connection")
        connection = pika.BlockingConnection(rabbitmq_params)
        print("finished getting RABBITMQ connection")

    else:
        # Check it is still alive
        # Only if we didn't recently do a check already (because it takes 100ms)
        if not last_heartbeat or last_heartbeat + 20 < time.time():
            last_heartbeat = time.time()
            try:
                connection.process_data_events(time_limit=0.1)
            except Exception:
                connection = pika.BlockingConnection(rabbitmq_params)
                channel = None

    if channel and channel.is_open:
        return channel


    channel = connection.channel()

    channel.queue_declare(queue='doggies', durable=False, exclusive=False, auto_delete=False,
            arguments={
                'x-message-ttl': 29030400000,
                'x-max-priority': 10,
                'expires': 29030400000}) # 1 year time limit

    return channel

def get_channel_info():
    connection = pika.BlockingConnection(rabbitmq_params)
    channel = connection.channel()

    return channel.queue_declare(queue='doggies', durable=False, exclusive=False, auto_delete=False,
            arguments={
                'x-message-ttl': 29030400000,
                'x-max-priority': 10,
                'expires': 29030400000}) # 1 year time limit

def purge_queue():
    channel = get_channel()
    channel.queue_purge('doggies')

def fill_queue(refill=False):
    channel = get_channel()
    with db_tokens.cursor() as c:

        used_prices = None
        if refill:
            c.execute("SELECT price FROM doggies;")
            used_prices = [item for item in c.fetchall()]

        update_queries = list()

        if refill:
            c.execute("SELECT id,key,price,tier from doggies WHERE (reserved_until < current_timestamp) AND ((NOT is_sold) AND (NOT is_sent)) ORDER BY id ASC")
        else:
            c.execute("SELECT id,key,price,tier from doggies WHERE ((reserved_until is NULL) OR (reserved_until < current_timestamp)) AND ((NOT is_sold) AND (NOT is_sent)) ORDER BY id ASC")
        for item in c.fetchall():
            # Define priority. Lower tier = higher priority
            # Tiers start at 0
            token_tier = item[3]
            priority = 9 - token_tier
            token_id = item[0]
            token_key = item[1]
            token_price = item[2]
            if refill:
                while True:
                    print(f"refilling {id} - token tier {token_tier}")
                    unique_price = derive_price(token_id,tier=token_tier)
                    if not (unique_price in used_prices):
                        break
                used_prices.append(unique_price)
                token_price = unique_price
                update_queries.append(f"UPDATE doggies SET price = {unique_price}, reserved_until = NULL, reserve_hash = NULL WHERE id = {token_id}")

            channel.basic_publish(exchange='', routing_key='doggies', body=f'{token_id},{token_key},{token_price},{token_tier},',
                    properties=pika.BasicProperties(priority=priority))


        if update_queries:
            for q in update_queries:
                c.execute(q)
            db_tokens.commit()
        else:
            c.execute("UPDATE doggies SET reserved_until = NULL, reserve_hash = NULL WHERE reserved_until < current_timestamp")
            db_tokens.commit()

def queue_length():
    return get_channel_info()


