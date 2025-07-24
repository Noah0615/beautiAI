

import os
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
import time

# Flask 앱 초기화
app = Flask(__name__, static_folder='', template_folder='')

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

# 업로드된 이미지를 제공하기 위한 라우트
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
# DB를 SQLite, PostgreSQL, Firebase