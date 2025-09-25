import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host='localhost',
        user='underdog',
        password='12345',
        database='beautiAI'
    )