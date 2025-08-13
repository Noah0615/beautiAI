import os
import traceback
import torch
from PIL import Image
import cv2
import numpy as np
import joblib
import facer
from fb import get_db
from sklearn.cluster import KMeans
from flask import Flask, request, jsonify, render_template, send_from_directory, session
from werkzeug.utils import secure_filename
import base64
from io import BytesIO
import json
import ssl
import albumentations as A
from scipy import ndimage
from skimage import exposure, color

# ==============================================================================
# SSL 인증서 오류 해결 (facer 모델 다운로드용)
# ==============================================================================
ssl._create_default_https_context = ssl._create_unverified_context

# Flask 웹 애플리케이션 초기화
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = '12345'

# 웹앱 기본 설정
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# AI 모델 관련 전역 변수
MODEL_DIR = '.'
N_REPRESENTATIVE_COLORS = 7
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# 퍼스널 컬러 타입별 정보 데이터
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
kmeans_model = None
scaler = None
face_detector = None
face_parser = None
models_loaded = False

# ==============================================================================
# 고급 조명 보정 함수들
# ==============================================================================

def analyze_lighting_conditions(image_np):
    """이미지의 조명 상태를 분석하여 보정 전략을 결정"""
    # RGB를 LAB 색공간으로 변환
    lab = cv2.cvtColor(image_np, cv2.COLOR_RGB2LAB)
    l_channel = lab[:, :, 0]
    
    # 조명 상태 분석 지표들
    mean_brightness = np.mean(l_channel)
    std_brightness = np.std(l_channel)
    
    # 히스토그램 분석
    hist, _ = np.histogram(l_channel, 256, [0, 256])
    
    # 어두운 픽셀과 밝은 픽셀의 비율
    dark_pixels = np.sum(l_channel < 85) / l_channel.size
    bright_pixels = np.sum(l_channel > 170) / l_channel.size
    
    lighting_info = {
        'mean_brightness': mean_brightness,
        'std_brightness': std_brightness,
        'dark_ratio': dark_pixels,
        'bright_ratio': bright_pixels,
        'is_underexposed': mean_brightness < 120 and dark_pixels > 0.3,
        'is_overexposed': mean_brightness > 180 and bright_pixels > 0.2,
        'has_low_contrast': std_brightness < 25,
        'has_uneven_lighting': std_brightness > 50
    }
    
    return lighting_info

def white_balance_correction(image_np, method='gray_world'):
    """화이트 밸런스 보정"""
    image = image_np.astype(np.float32) / 255.0
    
    if method == 'gray_world':
        # Gray World 알고리즘: 이미지의 평균 색상이 회색이 되도록 조정
        mean_rgb = np.mean(image.reshape(-1, 3), axis=0)
        # 회색점(0.5, 0.5, 0.5)을 기준으로 스케일링
        scale_factors = 0.5 / (mean_rgb + 1e-8)
        corrected = image * scale_factors
        
    elif method == 'white_patch':
        # White Patch 알고리즘: 가장 밝은 점이 흰색이 되도록 조정
        max_rgb = np.max(image.reshape(-1, 3), axis=0)
        scale_factors = 1.0 / (max_rgb + 1e-8)
        corrected = image * scale_factors
        
    elif method == 'illuminant_estimation':
        # 조명 추정 기반 보정 (단순화된 버전)
        # 이미지를 3x3 블록으로 나누어 각 블록의 평균 계산
        h, w = image.shape[:2]
        block_means = []
        for i in range(0, h, h//3):
            for j in range(0, w, w//3):
                block = image[i:i+h//3, j:j+w//3]
                if block.size > 0:
                    block_means.append(np.mean(block.reshape(-1, 3), axis=0))
        
        if block_means:
            # 최대 밝기 블록을 기준으로 조명 추정
            block_means = np.array(block_means)
            max_idx = np.argmax(np.sum(block_means, axis=1))
            illuminant = block_means[max_idx]
            scale_factors = 0.9 / (illuminant + 1e-8)
            corrected = image * scale_factors
        else:
            corrected = image
    
    # 값 범위를 [0, 1]로 클리핑하고 uint8로 변환
    corrected = np.clip(corrected, 0, 1)
    return (corrected * 255).astype(np.uint8)

def adaptive_histogram_equalization(image_np, clip_limit=3.0, tile_grid_size=(8, 8)):
    """적응적 히스토그램 평활화 (CLAHE)"""
    # LAB 색공간에서 L 채널에만 적용하여 색상 왜곡 방지
    lab = cv2.cvtColor(image_np, cv2.COLOR_RGB2LAB)
    l_channel = lab[:, :, 0]
    
    # CLAHE 적용
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    l_channel_eq = clahe.apply(l_channel)
    
    # LAB를 다시 결합하고 RGB로 변환
    lab[:, :, 0] = l_channel_eq
    corrected = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
    
    return corrected

def gamma_correction(image_np, gamma=1.0):
    """감마 보정"""
    if gamma == 1.0:
        return image_np
    
    # 감마 보정 룩업 테이블 생성
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    
    # 룩업 테이블 적용
    return cv2.LUT(image_np, table)

def shadow_highlight_correction(image_np, shadow_amount=0.0, highlight_amount=0.0, shadow_width=50, highlight_width=50):
    """그림자/하이라이트 보정"""
    if shadow_amount == 0.0 and highlight_amount == 0.0:
        return image_np
    
    # RGB를 LAB로 변환
    lab = cv2.cvtColor(image_np, cv2.COLOR_RGB2LAB).astype(np.float32)
    l_channel = lab[:, :, 0] / 255.0
    
    # 그림자 영역 마스크 (어두운 부분)
    shadow_mask = np.exp(-((l_channel - 0.0) ** 2) / (2 * (shadow_width / 255.0) ** 2))
    
    # 하이라이트 영역 마스크 (밝은 부분)
    highlight_mask = np.exp(-((l_channel - 1.0) ** 2) / (2 * (highlight_width / 255.0) ** 2))
    
    # 조정 적용
    if shadow_amount != 0.0:
        l_channel = l_channel + shadow_amount * shadow_mask * (1.0 - l_channel)
    
    if highlight_amount != 0.0:
        l_channel = l_channel + highlight_amount * highlight_mask * (l_channel - 1.0)
    
    # 값 범위 클리핑
    l_channel = np.clip(l_channel, 0, 1)
    lab[:, :, 0] = l_channel * 255.0
    
    # LAB를 RGB로 변환
    corrected = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
    
    return corrected

def unsharp_masking(image_np, strength=0.5, radius=1.0, threshold=0.0):
    """언샤프 마스킹을 통한 선명도 향상"""
    if strength == 0.0:
        return image_np
    
    # 가우시안 블러를 이용한 언샤프 마스크 생성
    blurred = cv2.GaussianBlur(image_np, (0, 0), radius)
    mask = image_np.astype(np.float32) - blurred.astype(np.float32)
    
    # 임계값 적용
    if threshold > 0:
        mask = np.where(np.abs(mask) < threshold, 0, mask)
    
    # 언샤프 마스크 적용
    sharpened = image_np.astype(np.float32) + strength * mask
    sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)
    
    return sharpened

def comprehensive_lighting_correction(image_np, lighting_info=None):
    """종합적인 조명 보정 파이프라인"""
    if lighting_info is None:
        lighting_info = analyze_lighting_conditions(image_np)
    
    corrected = image_np.copy()
    correction_log = []
    
    # 1. 화이트 밸런스 보정 (항상 적용)
    wb_method = 'gray_world'
    if lighting_info['bright_ratio'] > 0.15:
        wb_method = 'white_patch'
    elif lighting_info['has_uneven_lighting']:
        wb_method = 'illuminant_estimation'
    
    corrected = white_balance_correction(corrected, method=wb_method)
    correction_log.append(f"White balance: {wb_method}")
    
    # 2. 노출 보정
    if lighting_info['is_underexposed']:
        # 어두운 이미지: 그림자 복구 + 감마 보정
        corrected = shadow_highlight_correction(corrected, shadow_amount=0.3, highlight_amount=-0.1)
        gamma_value = 0.7  # 밝게
        corrected = gamma_correction(corrected, gamma_value)
        correction_log.append(f"Underexposure correction: shadow lift + gamma {gamma_value}")
        
    elif lighting_info['is_overexposed']:
        # 밝은 이미지: 하이라이트 복구
        corrected = shadow_highlight_correction(corrected, shadow_amount=0.0, highlight_amount=-0.4)
        gamma_value = 1.3  # 어둡게
        corrected = gamma_correction(corrected, gamma_value)
        correction_log.append(f"Overexposure correction: highlight recovery + gamma {gamma_value}")
    
    # 3. 대비 보정
    if lighting_info['has_low_contrast']:
        # 낮은 대비: CLAHE 적용
        clip_limit = 4.0 if lighting_info['std_brightness'] < 15 else 2.5
        corrected = adaptive_histogram_equalization(corrected, clip_limit=clip_limit)
        correction_log.append(f"Low contrast correction: CLAHE (clip_limit={clip_limit})")
    
    elif lighting_info['has_uneven_lighting']:
        # 불균등한 조명: 부드러운 CLAHE
        corrected = adaptive_histogram_equalization(corrected, clip_limit=2.0, tile_grid_size=(6, 6))
        correction_log.append("Uneven lighting correction: Soft CLAHE")
    
    # 4. 선명도 향상 (선택적)
    if lighting_info['std_brightness'] < 30:  # 흐릿한 이미지
        corrected = unsharp_masking(corrected, strength=0.3, radius=1.2)
        correction_log.append("Sharpening applied")
    
    # 5. Albumentations를 이용한 추가 보정 (미세 조정)
    transform = A.Compose([
        A.RandomBrightnessContrast(
            brightness_limit=0.1, 
            contrast_limit=0.1, 
            p=0.5
        ),
        A.ColorJitter(
            brightness=0.05,
            contrast=0.05,
            saturation=0.05,
            hue=0.02,
            p=0.3
        )
    ])
    
    # 50% 확률로 미세 조정 적용
    if np.random.random() < 0.5:
        augmented = transform(image=corrected)
        corrected = augmented['image']
        correction_log.append("Fine-tuning with Albumentations")
    
    return corrected, correction_log

def load_models():
    """AI 모델과 스케일러를 로드하는 함수"""
    global kmeans_model, scaler, face_detector, face_parser, models_loaded
    
    try:
        print("Loading AI models...")
        
        # 미리 훈련된 K-means 모델과 스케일러 로드
        kmeans_model = joblib.load(os.path.join(MODEL_DIR, 'kmeans_model.joblib'))
        scaler = joblib.load(os.path.join(MODEL_DIR, 'scaler.joblib'))
        print("✓ K-means model and scaler loaded successfully.")

        # Facer 라이브러리의 얼굴 관련 모델들 로드
        face_detector = facer.face_detector('retinaface/mobilenet', device=device)
        face_parser = facer.face_parser('farl/celebm/448', device=device)
        print("✓ Facer models loaded successfully.")
        print(f"✓ Using device: {device}")
        
        models_loaded = True
    except FileNotFoundError as e:
        print(f"❌ ERROR: Model file not found. {e}")
    except Exception as e:
        print(f"❌ An unexpected error occurred during model loading: {e}")
        traceback.print_exc()

def allowed_file(filename):
    """업로드된 파일이 허용된 확장자인지 확인하는 함수"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_facial_part_colors(image: Image.Image, n_colors_per_part=7, apply_lighting_correction=True):
    """얼굴에서 피부 색상 특징(Lab 색공간)을 추출하는 핵심 함수 (조명 보정 포함)"""
    try:
        # 이미지를 numpy 배열로 변환
        image_np = np.array(image)
        
        # 조명 보정 적용
        correction_log = []
        if apply_lighting_correction:
            print("🔧 조명 상태 분석 중...")
            lighting_info = analyze_lighting_conditions(image_np)
            
            print(f"   평균 밝기: {lighting_info['mean_brightness']:.1f}")
            print(f"   밝기 편차: {lighting_info['std_brightness']:.1f}")
            print(f"   어두운 픽셀 비율: {lighting_info['dark_ratio']:.2%}")
            print(f"   밝은 픽셀 비율: {lighting_info['bright_ratio']:.2%}")
            
            # 종합적인 조명 보정 적용
            print("🔧 조명 보정 적용 중...")
            image_np, correction_log = comprehensive_lighting_correction(image_np, lighting_info)
            
            for log in correction_log:
                print(f"   ✓ {log}")
            
            # 보정된 이미지를 PIL Image로 변환
            image = Image.fromarray(image_np)
        
        # 이미지를 모델 입력 크기(448x448)로 리사이즈
        image_resized = image.resize((448, 448))
        image_resized_np = np.array(image_resized)
        
        # PyTorch 텐서로 변환
        image_tensor = torch.from_numpy(image_resized_np).permute(2, 0, 1).unsqueeze(0).to(device)

        # 얼굴 감지 및 분할 수행
        with torch.inference_mode():
            faces = face_detector(image_tensor)
            
            if len(faces['scores']) == 0 or faces['scores'][0] < 0.5:
                return None, "얼굴을 감지할 수 없습니다. 정면을 향한 선명한 얼굴 사진을 업로드해주세요.", []
            
            faces = face_parser(image_tensor, faces)

        # 분할 결과에서 피부 영역만 추출
        seg_map = faces['seg']['logits'].argmax(dim=1).squeeze(0).cpu().numpy()
        
        # RGB를 Lab 색공간으로 변환
        image_lab = cv2.cvtColor(image_resized_np, cv2.COLOR_RGB2Lab)

        # 피부 영역 마스크 생성
        skin_mask = np.isin(seg_map, [1, 2])
        skin_pixels = image_lab[skin_mask]

        if len(skin_pixels) < n_colors_per_part:
            return None, "피부 영역이 충분하지 않습니다. 얼굴이 더 크게 나온 사진을 사용해주세요.", correction_log

        # K-means 클러스터링으로 대표 색상 추출
        kmeans = KMeans(n_clusters=n_colors_per_part, n_init='auto', random_state=42)
        kmeans.fit(skin_pixels.astype(np.float32))
        
        return kmeans.cluster_centers_.astype(np.float32).flatten().reshape(1, -1), None, correction_log

    except Exception as e:
        traceback.print_exc()
        return None, f"이미지 분석 중 오류가 발생했습니다: {str(e)}", []

def get_cluster_info(cluster_id):
    """클러스터 ID에 해당하는 퍼스널 컬러 정보를 반환하는 함수"""
    return CLUSTER_DESCRIPTIONS.get(cluster_id, CLUSTER_DESCRIPTIONS[0])

# ==============================================================================
# 웹 라우트 정의
# ==============================================================================

@app.route('/')
def index():
    """메인 페이지를 렌더링하는 라우트"""
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """이미지 분석을 수행하는 메인 API 엔드포인트"""
    if not models_loaded:
        return jsonify({'error': 'AI 모델이 로드되지 않았습니다.'}), 503

    try:
        image = None
        filename = f"upload_{np.datetime64('now').astype(int)}.jpg"
        
        # 조명 보정 옵션 (기본값: True)
        apply_correction = request.form.get('apply_lighting_correction', 'true').lower() == 'true'
        
        # 이미지 입력 처리
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '' or not allowed_file(file.filename):
                return jsonify({'error': '잘못된 파일입니다.'}), 400
            image = Image.open(file.stream).convert('RGB')
                
        elif request.json and 'image_data' in request.json:
            image_data = request.json['image_data'].split(',')[1]
            image = Image.open(BytesIO(base64.b64decode(image_data))).convert('RGB')
            # JSON 요청에서도 조명 보정 옵션 확인
            apply_correction = request.json.get('apply_lighting_correction', True)
        else:
            return jsonify({'error': '이미지 파일 또는 데이터가 필요합니다.'}), 400

        print(f"🔍 퍼스널 컬러 분석 시작 (조명 보정: {'ON' if apply_correction else 'OFF'})")
        
        # 퍼스널 컬러 분석 파이프라인 실행
        lab_features, error_msg, correction_log = extract_facial_part_colors(
            image, 
            n_colors_per_part=N_REPRESENTATIVE_COLORS,
            apply_lighting_correction=apply_correction
        )
        
        if error_msg:
            return jsonify({'error': error_msg}), 400

        # 특징 데이터 정규화 및 예측
        scaled_features = scaler.transform(lab_features)
        predicted_cluster = kmeans_model.predict(scaled_features)[0]

        print(f"✅ 분석 완료: {get_cluster_info(predicted_cluster)['visual_name']}")

        # 결과 데이터 생성
        cluster_info = get_cluster_info(predicted_cluster)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        image.save(filepath, 'JPEG')

        result_data = {
            "success": True,
            "cluster_id": int(predicted_cluster),
            "personal_color_type": cluster_info["name"],
            "visual_name": cluster_info["visual_name"],
            "type_description": cluster_info["description"],
            "palette": cluster_info["palette"],
            "uploaded_image_url": f'/uploads/{filename}',
            "lighting_correction_applied": apply_correction,
            "correction_log": correction_log
        }
        return jsonify(result_data)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'분석 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/analyze_lighting', methods=['POST'])
def analyze_lighting():
    """조명 분석 전용 엔드포인트"""
    try:
        image = None
        
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '' or not allowed_file(file.filename):
                return jsonify({'error': '잘못된 파일입니다.'}), 400
            image = Image.open(file.stream).convert('RGB')
                
        elif request.json and 'image_data' in request.json:
            image_data = request.json['image_data'].split(',')[1]
            image = Image.open(BytesIO(base64.b64decode(image_data))).convert('RGB')
        else:
            return jsonify({'error': '이미지가 필요합니다.'}), 400

        # 조명 상태 분석
        image_np = np.array(image)
        lighting_info = analyze_lighting_conditions(image_np)
        
        # 보정된 이미지 생성
        corrected_np, correction_log = comprehensive_lighting_correction(image_np, lighting_info)
        
        # 보정된 이미지를 Base64로 인코딩
        corrected_image = Image.fromarray(corrected_np)
        buffer = BytesIO()
        corrected_image.save(buffer, format='JPEG')
        corrected_b64 = base64.b64encode(buffer.getvalue()).decode()
        
        return jsonify({
            'success': True,
            'lighting_analysis': lighting_info,
            'correction_log': correction_log,
            'corrected_image': f'data:image/jpeg;base64,{corrected_b64}'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'조명 분석 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """업로드된 이미지 파일을 제공하는 라우트"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
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

# logout route
@app.route('/logout', methods=['POST'])
def logout():
    session.clear() # 세션 클리어
    return jsonify({'status': 'success'}), 200

#fetch user info
@app.route('/me', methods=['GET'])
def get_profile():
    user = session.get('user')
    if not user:
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    return jsonify({'status': 'success', 'user': user}), 200

# ==============================================================================
# 메인 실행 부분
# ==============================================================================
if __name__ == '__main__':
    # 서버 시작 전 AI 모델들을 미리 로드
    load_models()
    
    print("=" * 70)
    print(f"🚀 Enhanced Personal Color Analysis Server Starting...")
    print(f"📱 Model Status: {'✅ Loaded' if models_loaded else '❌ Failed'}")
    print(f"🖥️  Device: {device}")
    print(f"🔧 Advanced Lighting Corrections Available:")
    print(f"   • White Balance (Gray World, White Patch, Illuminant Estimation)")
    print(f"   • Adaptive Histogram Equalization (CLAHE)")
    print(f"   • Gamma Correction")
    print(f"   • Shadow/Highlight Recovery")
    print(f"   • Unsharp Masking")
    print(f"   • Albumentations Fine-tuning")
    print(f"🌐 Server: http://127.0.0.1:5001")
    print("=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=5001)