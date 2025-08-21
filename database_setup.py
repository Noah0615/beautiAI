# import mysql.connector
# from mysql.connector import errorcode

# # 데이터베이스 연결 정보
# DB_CONFIG = {
#     'host': '123.45.67.89',
#     'user': 'underdog',
#     'password': '12345',
#     'port': 3306
# }
# DB_NAME = 'beautiAI'

# # 생성할 테이블 정의
# TABLES = {}
# TABLES['users'] = (
#     """
#     CREATE TABLE `users` (
#       `id` int(11) NOT NULL AUTO_INCREMENT,
#       `name` varchar(50) NOT NULL UNIQUE,
#       `email` varchar(100) NOT NULL UNIQUE,
#       `password_hash` varchar(255) NOT NULL,
#       `sex` enum('male','female') NOT NULL,
#       `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
#       PRIMARY KEY (`id`)
#     ) ENGINE=InnoDB
#     """
# )

# TABLES['analysis_history'] = (
#     """
#     CREATE TABLE `analysis_history` (
#       `id` int(11) NOT NULL AUTO_INCREMENT,
#       `user_id` int(11) NOT NULL,
#       `personal_color_type` varchar(50) NOT NULL,
#       `visual_name` varchar(50) NOT NULL,
#       `type_description` text,
#       `palette` json,
#       `image_url` varchar(255) NOT NULL,
#       `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
#       PRIMARY KEY (`id`),
#       KEY `user_id` (`user_id`),
#       CONSTRAINT `analysis_history_ibfk_1` FOREIGN KEY (`user_id`) 
#       REFERENCES `users` (`id`) ON DELETE CASCADE
#     ) ENGINE=InnoDB
#     """
# )

# def setup_database():
#     """데이터베이스와 테이블을 생성합니다."""
#     try:
#         # MySQL 서버에 연결
#         cnx = mysql.connector.connect(**DB_CONFIG)
#         cursor = cnx.cursor()
#         print("MySQL 서버에 연결되었습니다.")

#         # 데이터베이스 생성
#         try:
#             cursor.execute(f"CREATE DATABASE {DB_NAME} DEFAULT CHARACTER SET 'utf8'")
#             print(f"데이터베이스 '{DB_NAME}'를 생성했습니다.")
#         except mysql.connector.Error as err:
#             if err.errno == errorcode.ER_DB_CREATE_EXISTS:
#                 print(f"데이터베이스 '{DB_NAME}'는 이미 존재합니다.")
#             else:
#                 print(err)
#                 exit(1)
        
#         # 생성된 데이터베이스 사용
#         cnx.database = DB_NAME

#         # 테이블 생성
#         for table_name, table_description in TABLES.items():
#             try:
#                 print(f"테이블 '{table_name}' 생성 중... ", end='')
#                 cursor.execute(table_description)
#                 print("성공")
#             except mysql.connector.Error as err:
#                 if err.errno == errorcode.ER_TABLE_EXISTS_ERROR:
#                     print("이미 존재합니다.")
#                 else:
#                     print(err.msg)
        
#         print("\n데이터베이스 설정이 완료되었습니다.")

#     except mysql.connector.Error as err:
#         if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
#             print("MySQL 사용자 이름 또는 비밀번호가 잘못되었습니다.")
#         elif err.errno == errorcode.ER_BAD_DB_ERROR:
#             print(f"데이터베이스 '{DB_NAME}'가 존재하지 않습니다.")
#         else:
#             print(err)
#     finally:
#         if 'cursor' in locals() and cursor:
#             cursor.close()
#         if 'cnx' in locals() and cnx.is_connected():
#             cnx.close()
#             print("MySQL 연결을 닫았습니다.")

# if __name__ == '__main__':
#     setup_database()

import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import json

# Firebase 초기화
def initialize_firebase():
    """Firebase를 초기화합니다."""
    try:
        # 서비스 계정 키 파일 경로 (Firebase Console에서 다운로드)
        cred = credentials.Certificate("/Users/jeonjaewon/Desktop/python/streamlit/streamlit/google-services.json")
        firebase_admin.initialize_app(cred)
        print("Firebase가 성공적으로 초기화되었습니다.")
        return True
    except Exception as e:
        print(f"Firebase 초기화 실패: {e}")
        return False

# Firestore 클라이언트 가져오기
def get_firestore_client():
    """Firestore 클라이언트를 반환합니다."""
    return firestore.client()

# 컬렉션 및 문서 구조 설정
def setup_firestore_collections():
    """Firestore 컬렉션을 설정하고 인덱스 규칙을 생성합니다."""
    db = get_firestore_client()
    
    # 컬렉션 구조 정의
    collections_info = {
        'users': {
            'description': '사용자 정보를 저장하는 컬렉션',
            'fields': {
                'name': 'string (unique)',
                'email': 'string (unique)', 
                'password_hash': 'string',
                'sex': 'string (male/female)',
                'created_at': 'timestamp'
            }
        },
        'analysis_history': {
            'description': '퍼스널 컬러 분석 기록을 저장하는 컬렉션',
            'fields': {
                'user_id': 'string (users 컬렉션의 문서 ID 참조)',
                'personal_color_type': 'string',
                'visual_name': 'string',
                'type_description': 'string',
                'palette': 'array/map',
                'image_url': 'string',
                'created_at': 'timestamp'
            }
        }
    }
    
    print("=== Firestore 컬렉션 구조 ===")
    for collection_name, info in collections_info.items():
        print(f"\n컬렉션: {collection_name}")
        print(f"설명: {info['description']}")
        print("필드:")
        for field, field_type in info['fields'].items():
            print(f"  - {field}: {field_type}")
    
    # 예시 문서 생성 (선택사항)
    try:
        # users 컬렉션에 예시 사용자 생성
        users_ref = db.collection('users')
        example_user = {
            'name': 'example_user',
            'email': 'example@test.com',
            'password_hash': 'hashed_password_here',
            'sex': 'female',
            'created_at': datetime.now()
        }
        
        # 이미 존재하는지 확인
        existing_user = users_ref.where('email', '==', 'example@test.com').limit(1).get()
        if not existing_user:
            users_ref.add(example_user)
            print("\n예시 사용자가 생성되었습니다.")
        else:
            print("\n예시 사용자가 이미 존재합니다.")
            
    except Exception as e:
        print(f"예시 데이터 생성 중 오류: {e}")

# 사용자 관리 함수들
class FirebaseUserManager:
    def __init__(self):
        self.db = get_firestore_client()
        
    def create_user(self, name, email, password_hash, sex):
        """새 사용자를 생성합니다."""
        try:
            # 중복 확인
            users_ref = self.db.collection('users')
            
            # 이메일 중복 확인
            email_check = users_ref.where('email', '==', email).limit(1).get()
            if email_check:
                return {'success': False, 'error': '이미 존재하는 이메일입니다.'}
            
            # 이름 중복 확인
            name_check = users_ref.where('name', '==', name).limit(1).get()
            if name_check:
                return {'success': False, 'error': '이미 존재하는 사용자명입니다.'}
            
            # 새 사용자 생성
            user_data = {
                'name': name,
                'email': email,
                'password_hash': password_hash,
                'sex': sex,
                'created_at': datetime.now()
            }
            
            doc_ref = users_ref.add(user_data)
            return {'success': True, 'user_id': doc_ref[1].id}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_user_by_email(self, email):
        """이메일로 사용자를 조회합니다."""
        try:
            users_ref = self.db.collection('users')
            user_docs = users_ref.where('email', '==', email).limit(1).get()
            
            if user_docs:
                user_doc = user_docs[0]
                user_data = user_doc.to_dict()
                user_data['id'] = user_doc.id
                return {'success': True, 'user': user_data}
            else:
                return {'success': False, 'error': '사용자를 찾을 수 없습니다.'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}

# 분석 기록 관리 함수들
class FirebaseAnalysisManager:
    def __init__(self):
        self.db = get_firestore_client()
    
    def save_analysis(self, user_id, personal_color_type, visual_name, 
                     type_description, palette, image_url):
        """분석 결과를 저장합니다."""
        try:
            analysis_data = {
                'user_id': user_id,
                'personal_color_type': personal_color_type,
                'visual_name': visual_name,
                'type_description': type_description,
                'palette': palette,
                'image_url': image_url,
                'created_at': datetime.now()
            }
            
            doc_ref = self.db.collection('analysis_history').add(analysis_data)
            return {'success': True, 'analysis_id': doc_ref[1].id}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_user_analysis_history(self, user_id):
        """사용자의 분석 기록을 조회합니다."""
        try:
            analysis_ref = self.db.collection('analysis_history')
            analyses = analysis_ref.where('user_id', '==', user_id)\
                                 .order_by('created_at', direction=firestore.Query.DESCENDING)\
                                 .get()
            
            analysis_list = []
            for analysis in analyses:
                analysis_data = analysis.to_dict()
                analysis_data['id'] = analysis.id
                analysis_list.append(analysis_data)
            
            return {'success': True, 'analyses': analysis_list}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

# 메인 설정 함수
def setup_firebase_database():
    """Firebase 데이터베이스를 설정합니다."""
    print("Firebase 데이터베이스 설정을 시작합니다...")
    
    # Firebase 초기화
    if not initialize_firebase():
        return False
    
    # 컬렉션 구조 설정
    setup_firestore_collections()
    
    print("\nFirebase 데이터베이스 설정이 완료되었습니다.")
    print("이제 FirebaseUserManager와 FirebaseAnalysisManager 클래스를 사용할 수 있습니다.")
    
    return True

# 사용 예시
if __name__ == '__main__':
    # 데이터베이스 설정
    if setup_firebase_database():
        # 사용자 관리자 생성
        user_manager = FirebaseUserManager()
        analysis_manager = FirebaseAnalysisManager()
        
        # 예시: 새 사용자 생성
        result = user_manager.create_user(
            name="test_user",
            email="test@example.com", 
            password_hash="hashed_password",
            sex="female"
        )
        print(f"\n사용자 생성 결과: {result}")
        
        # 예시: 사용자 조회
        user_result = user_manager.get_user_by_email("test@example.com")
        if user_result['success']:
            user_id = user_result['user']['id']
            
            # 예시: 분석 결과 저장
            analysis_result = analysis_manager.save_analysis(
                user_id=user_id,
                personal_color_type="Spring",
                visual_name="Bright Spring",
                type_description="따뜻하고 밝은 톤이 어울리는 타입",
                palette=["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4"],
                image_url="https://example.com/image.jpg"
            )
            print(f"분석 저장 결과: {analysis_result}")
