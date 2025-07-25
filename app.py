import os
import traceback
import torch
from PIL import Image
import cv2
import numpy as np
import joblib
import facer
from sklearn.cluster import KMeans
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
import base64
from io import BytesIO
import json
import ssl

# ==============================================================================
# SSL 인증서 오류 해결 (facer 모델 다운로드용)
# - facer 라이브러리가 모델을 다운로드할 때 SSL 인증서 오류가 발생할 수 있어서 우회 설정
# ==============================================================================
ssl._create_default_https_context = ssl._create_unverified_context

# Flask 웹 애플리케이션 초기화
# - static_folder='', template_folder='': 현재 디렉토리를 정적 파일과 템플릿 폴더로 설정
app = Flask(__name__, static_folder='', template_folder='')

# 웹앱 기본 설정
UPLOAD_FOLDER = 'uploads'  # 업로드된 이미지를 저장할 폴더
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)  # 폴더가 없으면 생성

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'}  # 허용되는 파일 확장자
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 최대 업로드 파일 크기: 16MB

# AI 모델 관련 전역 변수
MODEL_DIR = '.'  # 모델 파일이 저장된 디렉토리
N_REPRESENTATIVE_COLORS = 7  # 피부에서 추출할 대표 색상 개수
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')  # GPU 사용 가능하면 GPU, 아니면 CPU

# 퍼스널 컬러 타입별 정보 데이터
# - 각 클러스터(타입)에 대한 이름, 설명, 추천 색상 팔레트 정의
CLUSTER_DESCRIPTIONS = {
    0: {"name": "Golden", "visual_name": "골든 타입", "description": "명확한 웜 톤입니다.", "palette": ["#FFD700", "#FF7F50", "#FFA500", "#F4A460", "#FFFFE0"]},
    1: {"name": "Warm Beige", "visual_name": "웜 베이지 타입", "description": "웜하지만 올리브 기운이 있습니다.", "palette": ["#D2B48C", "#BC9A6A", "#8FBC8F", "#CD853F", "#DEB887"]},
    2: {"name": "Cool Rose", "visual_name": "쿨 로즈 타입", "description": "핑크와 레드가 혼합된 쿨 톤입니다.", "palette": ["#FFC0CB", "#FF69B4", "#DB7093", "#C71585", "#F08080"]},
    3: {"name": "Muted Clay", "visual_name": "뮤트 클레이 타입", "description": "차분하고 톤 다운된 색감입니다.", "palette": ["#BC9A6A", "#A0826D", "#8B7D6B", "#D2B48C", "#F5DEB3"]},
    4: {"name": "Warm Apricot", "visual_name": "웜 애프리콧 타입", "description": "안정적인 오렌지 계열의 웜 톤입니다.", "palette": ["#FFCBA4", "#FF8C69", "#FFA07A", "#F4A460", "#FFDAB9"]},
    5: {"name": "Peachy Pink", "visual_name": "피치 핑크 타입", "description": "사랑스러운 Red-Pink 계열입니다.", "palette": ["#FFCCCB", "#FFB6C1", "#FFA0B4", "#FF91A4", "#FFEFD5"]},
    6: {"name": "Honey Buff", "visual_name": "허니 버프 타입", "description": "유사성이 많지만 구분 가능한 톤입니다.", "palette": ["#F0DC82", "#DAA520", "#CD853F", "#DEB887", "#F5DEB3"]},
    7: {"name": "Beige Rose", "visual_name": "베이지 로즈 타입", "description": "부드러운 베이지 로즈 톤입니다.", "palette": ["#D2B48C", "#C4A484", "#BC9A6A", "#F5DEB3", "#E6D3C7"]}
}

# AI 모델 관련 전역 변수 초기화
kmeans_model = None      # K-means 클러스터링 모델 (퍼스널 컬러 분류용)
scaler = None           # 데이터 정규화용 스케일러
face_detector = None    # 얼굴 감지 모델
face_parser = None      # 얼굴 부위 분할 모델
models_loaded = False   # 모델 로딩 완료 여부 플래그

def load_models():
    """AI 모델과 스케일러를 로드하는 함수"""
    global kmeans_model, scaler, face_detector, face_parser, models_loaded
    
    try:
        print("Loading AI models...")
        
        # 미리 훈련된 K-means 모델과 스케일러 로드
        # - kmeans_model: 피부 색상 특징을 8개 퍼스널 컬러 타입으로 분류하는 모델
        # - scaler: 색상 특징 데이터를 정규화하는 스케일러
        kmeans_model = joblib.load(os.path.join(MODEL_DIR, 'kmeans_model.joblib'))
        scaler = joblib.load(os.path.join(MODEL_DIR, 'scaler.joblib'))
        print("✓ K-means model and scaler loaded successfully.")

        # Facer 라이브러리의 얼굴 관련 모델들 로드
        # - face_detector: 이미지에서 얼굴 위치를 찾는 모델
        # - face_parser: 얼굴 내에서 피부, 눈, 입 등의 부위를 분할하는 모델
        face_detector = facer.face_detector('retinaface/mobilenet', device=device)
        face_parser = facer.face_parser('farl/celebm/448', device=device)
        print("✓ Facer models loaded successfully.")
        print(f"✓ Using device: {device}")
        
        models_loaded = True  # 모든 모델 로딩 완료
    except FileNotFoundError as e:
        print(f"❌ ERROR: Model file not found. {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred during model loading: {e}")
        traceback.print_exc()

def allowed_file(filename):
    """업로드된 파일이 허용된 확장자인지 확인하는 함수"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_facial_part_colors(image: Image.Image, n_colors_per_part=7):
    """얼굴에서 피부 색상 특징(Lab 색공간)을 추출하는 핵심 함수"""
    try:
        # 1. 이미지를 모델 입력 크기(448x448)로 리사이즈
        image_resized = image.resize((448, 448))
        image_np = np.array(image_resized)
        
        # 2. PyTorch 텐서로 변환 (NCHW 형태: Batch, Channel, Height, Width)
        image_tensor = torch.from_numpy(image_np).permute(2, 0, 1).unsqueeze(0).to(device)

        # 3. 얼굴 감지 및 분할 수행
        with torch.inference_mode():  # 추론 모드 (그래디언트 계산 비활성화)
            # 얼굴 감지: 이미지에서 얼굴의 위치와 신뢰도 점수 반환
            faces = face_detector(image_tensor)
            
            # 얼굴이 감지되지 않거나 신뢰도가 낮으면 오류 반환
            if len(faces['scores']) == 0 or faces['scores'][0] < 0.5:
                return None, "얼굴을 감지할 수 없습니다. 정면을 향한 선명한 얼굴 사진을 업로드해주세요."
            
            # 얼굴 부위 분할: 피부, 눈, 입, 머리카락 등으로 픽셀 단위 분류
            faces = face_parser(image_tensor, faces)

        # 4. 분할 결과에서 피부 영역만 추출
        seg_map = faces['seg']['logits'].argmax(dim=1).squeeze(0).cpu().numpy()
        
        # 5. RGB를 Lab 색공간으로 변환 (색상 분석에 더 적합)
        # Lab: L(명도), a(적녹색), b(황청색) - 인간의 시각 인지와 유사
        image_lab = cv2.cvtColor(np.array(image_resized), cv2.COLOR_RGB2Lab)

        # 6. 피부 영역 마스크 생성 (1: 피부, 2: 코)
        skin_mask = np.isin(seg_map, [1, 2])
        skin_pixels = image_lab[skin_mask]  # 피부 픽셀들의 Lab 값만 추출

        # 7. 피부 픽셀이 충분하지 않으면 오류 반환
        if len(skin_pixels) < n_colors_per_part:
            return None, "피부 영역이 충분하지 않습니다. 얼굴이 더 크게 나온 사진을 사용해주세요."

        # 8. K-means 클러스터링으로 대표 색상 추출
        # 피부의 다양한 색상을 n_colors_per_part개의 대표 색상으로 요약
        kmeans = KMeans(n_clusters=n_colors_per_part, n_init='auto', random_state=42)
        kmeans.fit(skin_pixels.astype(np.float32))
        
        # 9. 클러스터 중심점(대표 색상들)을 1차원 배열로 변환하여 반환
        # 형태: [L1,a1,b1, L2,a2,b2, ..., L7,a7,b7] → 총 21개 특징
        return kmeans.cluster_centers_.astype(np.float32).flatten().reshape(1, -1), None

    except Exception as e:
        traceback.print_exc()
        return None, f"이미지 분석 중 오류가 발생했습니다: {str(e)}"

def get_cluster_info(cluster_id):
    """클러스터 ID에 해당하는 퍼스널 컬러 정보를 반환하는 함수"""
    return CLUSTER_DESCRIPTIONS.get(cluster_id, CLUSTER_DESCRIPTIONS[0])  # ID가 없으면 기본값(0번) 반환

# ==============================================================================
# 웹 라우트 정의
# ==============================================================================

@app.route('/')
def index():
    """메인 페이지를 렌더링하는 라우트"""
    return render_template('beauty_advisor_webapp.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """이미지 분석을 수행하는 메인 API 엔드포인트"""
    # 1. 모델 로딩 상태 확인
    if not models_loaded:
        return jsonify({'error': 'AI 모델이 로드되지 않았습니다.'}), 503

    try:
        image = None
        filename = f"upload_{np.datetime64('now').astype(int)}.jpg"  # 고유한 파일명 생성
        
        # 2. 이미지 입력 처리 (파일 업로드 또는 Base64 데이터)
        if 'file' in request.files:
            # 파일 업로드 방식
            file = request.files['file']
            if file.filename == '' or not allowed_file(file.filename):
                return jsonify({'error': '잘못된 파일입니다.'}), 400
            image = Image.open(file.stream).convert('RGB')
                
        elif request.json and 'image_data' in request.json:
            # Base64 데이터 방식 (웹캠 촬영 등)
            image_data = request.json['image_data'].split(',')[1]  # "data:image/jpeg;base64," 부분 제거
            image = Image.open(BytesIO(base64.b64decode(image_data))).convert('RGB')
        else:
            return jsonify({'error': '이미지 파일 또는 데이터가 필요합니다.'}), 400

        # 3. 퍼스널 컬러 분석 파이프라인 실행
        # 3-1. 얼굴에서 피부 색상 특징 추출
        lab_features, error_msg = extract_facial_part_colors(image, n_colors_per_part=N_REPRESENTATIVE_COLORS)
        if error_msg:
            return jsonify({'error': error_msg}), 400

        # 3-2. 특징 데이터 정규화 (훈련 시와 동일한 스케일로 변환)
        scaled_features = scaler.transform(lab_features)
        
        # 3-3. K-means 모델로 퍼스널 컬러 타입 예측
        predicted_cluster = kmeans_model.predict(scaled_features)[0]

        # 4. 결과 데이터 생성 및 이미지 저장
        cluster_info = get_cluster_info(predicted_cluster)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        image.save(filepath, 'JPEG')  # 분석된 이미지를 서버에 저장

        # 5. 클라이언트에게 전송할 결과 JSON 생성
        result_data = {
            "success": True,
            "cluster_id": int(predicted_cluster),           # 예측된 클러스터 번호
            "personal_color_type": cluster_info["name"],    # 영문 타입명
            "visual_name": cluster_info["visual_name"],     # 한글 타입명
            "type_description": cluster_info["description"], # 타입 설명
            "palette": cluster_info["palette"],             # 추천 색상 팔레트
            "uploaded_image_url": f'/uploads/{filename}'    # 저장된 이미지 URL
        }
        return jsonify(result_data)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'분석 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """업로드된 이미지 파일을 제공하는 라우트"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ==============================================================================
# 메인 실행 부분
# ==============================================================================
if __name__ == '__main__':
    # 서버 시작 전 AI 모델들을 미리 로드
    load_models()
    
    # 서버 상태 정보 출력
    print("=" * 50)
    print(f"🚀 Flask 서버 시작 중... (http://127.0.0.1:5001)")
    print(f"📱 모델 로드 상태: {'✅ 성공' if models_loaded else '❌ 실패'}")
    print(f"🖥️  사용 장치: {device}")
    print("=" * 50)
    
    # Flask 개발 서버 실행
    # - debug=True: 코드 변경 시 자동 재시작, 오류 정보 상세 출력
    # - host='0.0.0.0': 모든 네트워크 인터페이스에서 접근 허용
    # - port=5001: 5001번 포트 사용
    app.run(debug=True, host='0.0.0.0', port=5001)