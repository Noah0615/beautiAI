import os
from flask import Flask, request, jsonify, render_template, send_from_directory,session
from werkzeug.utils import secure_filename
import time
#from db import get_db_connection
from fb import get_db
# Flask 앱 초기화
app = Flask(__name__, static_folder='', template_folder='')
app.secret_key = '12345'
# 업로드 폴더 설정
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# 메인 페이지 렌더링
@app.route('/')
def index():
    return render_template('beauty_advisor_webapp.html')

# 이미지 분석 API 엔드포인트
@app.route('/analyze', methods=['POST'])
def analyze():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # ===============================================================
        # 여기에 AI 모델 분석 로직을 추가합니다.
        # 1. filepath의 이미지 로드
        # 2. 보고서의 파이프라인 실행 (얼굴 감지, 피부 추출, 클러스터 예측 등)
        # 3. 가상 스타일링 이미지 생성 및 저장
        # ===============================================================
        
        # 지금은 분석 시뮬레이션을 위해 잠시 대기합니다.
        time.sleep(2) 

        # 분석 결과를 JSON 형태로 반환 (임시 데이터)
        # 실제로는 AI 모델의 분석 결과를 바탕으로 이 데이터를 구성해야 합니다.
        result_data = {
          "personal_color_type": "Golden",
          "type_description": "AI 분석 결과: 따뜻하고 화사한 골드 톤은 당신을 생기 있게 만들어 줍니다.",
          "palette": ["#FFD700", "#FFA500", "#FF8C00", "#FF7F50", "#FF6347"],
          "uploaded_image_url": f'/uploads/{filename}'
        }
        
        return jsonify(result_data)

    return jsonify({'error': 'File type not allowed'}), 400

#store user's data in database
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'status': 'error', 'message': 'Invalid or missing JSON'}), 400

    name = data.get('name')
    password = data.get('password')
    email = data.get('email')
    sex = data.get('sex')

    if not name or not password or not email or not sex:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    db = get_db()
    users = db.collection('users')

    # Enforce unique email (recommended) — fast lookup by doc id
    # Use email as document id to guarantee uniqueness
    doc_ref = users.document(email)
    if doc_ref.get().exists:
        return jsonify({'status': 'error', 'message': 'Email already exists'}), 400

    # If you also want to enforce unique name, query:
    same_name = users.where('name', '==', name).limit(1).stream()
    if any(same_name):
        return jsonify({'status': 'error', 'message': 'Name already taken'}), 400

    # Create user document
    doc_ref.set({
        'name': name,
        'email': email,
        'password': password,  # ⚠️ store hashed later
        'sex': sex,
        'image': None
    })

    return jsonify({'status': 'success'}), 200

#check username and passowrd when logging in
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    name = data.get('name')
    password = data.get('password')

    if not name or not password:
        return jsonify({'status': 'error', 'message': 'Missing name or password'}), 400

    db = get_db()
    users = db.collection('users')

    # Keep compatibility with your existing frontend: login by name
    # (If multiple docs have same name, we take the first one found.)
    q = users.where('name', '==', name).limit(1).stream()
    user_doc = next(q, None)

    if not user_doc:
        return jsonify({'status': 'error', 'message': 'Invalid name or password'}), 401

    user = user_doc.to_dict()
    if user.get('password') != password:
        return jsonify({'status': 'error', 'message': 'Invalid name or password'}), 401

    session['user'] = {
        'name': user['name'],
        'email': user['email'],
        'sex': user['sex'],
        'image': None if not user.get('image') else f"/user_image/{user['name']}"
    }
    return jsonify({'status': 'success'}), 200

#fetch user info
@app.route('/me', methods=['GET'])
def get_profile():
    user = session.get('user')
    if not user:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    return jsonify({'status': 'success', 'user': user}), 200


# 업로드된 이미지를 제공하기 위한 라우트
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
