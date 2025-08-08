import mysql.connector
from mysql.connector import errorcode

# 데이터베이스 연결 정보
DB_CONFIG = {
    'host': '123.45.67.89',
    'user': 'underdog',
    'password': '12345',
    'port': 3306
}
DB_NAME = 'beautiAI'

# 생성할 테이블 정의
TABLES = {}
TABLES['users'] = (
    """
    CREATE TABLE `users` (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      `name` varchar(50) NOT NULL UNIQUE,
      `email` varchar(100) NOT NULL UNIQUE,
      `password_hash` varchar(255) NOT NULL,
      `sex` enum('male','female') NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`)
    ) ENGINE=InnoDB
    """
)

TABLES['analysis_history'] = (
    """
    CREATE TABLE `analysis_history` (
      `id` int(11) NOT NULL AUTO_INCREMENT,
      `user_id` int(11) NOT NULL,
      `personal_color_type` varchar(50) NOT NULL,
      `visual_name` varchar(50) NOT NULL,
      `type_description` text,
      `palette` json,
      `image_url` varchar(255) NOT NULL,
      `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      KEY `user_id` (`user_id`),
      CONSTRAINT `analysis_history_ibfk_1` FOREIGN KEY (`user_id`) 
      REFERENCES `users` (`id`) ON DELETE CASCADE
    ) ENGINE=InnoDB
    """
)

def setup_database():
    """데이터베이스와 테이블을 생성합니다."""
    try:
        # MySQL 서버에 연결
        cnx = mysql.connector.connect(**DB_CONFIG)
        cursor = cnx.cursor()
        print("MySQL 서버에 연결되었습니다.")

        # 데이터베이스 생성
        try:
            cursor.execute(f"CREATE DATABASE {DB_NAME} DEFAULT CHARACTER SET 'utf8'")
            print(f"데이터베이스 '{DB_NAME}'를 생성했습니다.")
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_DB_CREATE_EXISTS:
                print(f"데이터베이스 '{DB_NAME}'는 이미 존재합니다.")
            else:
                print(err)
                exit(1)
        
        # 생성된 데이터베이스 사용
        cnx.database = DB_NAME

        # 테이블 생성
        for table_name, table_description in TABLES.items():
            try:
                print(f"테이블 '{table_name}' 생성 중... ", end='')
                cursor.execute(table_description)
                print("성공")
            except mysql.connector.Error as err:
                if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
                    print("이미 존재합니다.")
                else:
                    print(err.msg)
        
        print("\n데이터베이스 설정이 완료되었습니다.")

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("MySQL 사용자 이름 또는 비밀번호가 잘못되었습니다.")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print(f"데이터베이스 '{DB_NAME}'가 존재하지 않습니다.")
        else:
            print(err)
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'cnx' in locals() and cnx.is_connected():
            cnx.close()
            print("MySQL 연결을 닫았습니다.")

if __name__ == '__main__':
    setup_database()
