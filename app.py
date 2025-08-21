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
from werkzeug.security import generate_password_hash, check_password_hash


# 가상 메이크업 기능에 필요한 import
from torchvision import transforms
from model import BiSeNet  # kaka 프로젝트의 model.py
from makeup import hair   # kaka 프로젝트의 makeup.py

# ==============================================================================
# SSL 인증서 오류 해결 (facer 모델 다운로드용)
# ==============================================================================
ssl._create_default_https_context = ssl._create_unverified_context

# Flask 웹 애플리케이션 초기화
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.urandom(24)

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

# 가상 메이크업에 사용할 컬러 팔레트
MAKEOVER_PALETTES = {
    # 0: Golden
    0: [
        ["#D9A882", "#A2DADA", "#F68B8B", "#F5E7C3"],  # Style 1 (Natural)
        ["#5D4B40", "#7F9C92", "#C45A5A", "#A7B6B4"],  # Style 2 (Smokey)
        ["#8A3500", "#33A399", "#D1256A", "#512525"]   # Style 3 (Vibrant)
    ],
    # 1: Warm Beige
    1: [
        ["#A0522D", "#E1C699", "#E57373", "#FFD580"],  # Style 1 (Natural)
        ["#4A403A", "#8DA399", "#B34747", "#9AB9B7"],  # Style 2 (Smokey)
        ["#C78967", "#6AABBB", "#E0607F", "#691DBB"]   # Style 3 (Pastel)
    ],
    # 2: Cool Rose
    2: [
        ["#C19A8B", "#5C7A86", "#A32E31", "#3A565A"],  # Style 1 (Ashy)
        ["#D1B7AA", "#9DB8B5", "#E5A4A4", "#D0BBDE"],  # Style 2 (Soft)
        ["#332436", "#8A3500", "#D1259A", "#58FFF4"]   # Style 3 (Fantasy)
    ],
    # 3: Muted Clay
    3: [
        ["#9E6B58", "#4A7E94", "#9E2A2B", "#354F52"],  # Style 1 (Earthy)
        ["#CBB3A5", "#A9C6C2", "#E9A6A6", "#D7C4E0"],  # Style 2 (Soft)
        ["#5C4033", "#78866B", "#B87333", "#05A6B1"]   # Style 3 (Woodsy)
    ],
    # 4: Warm Apricot
    4: [
        ["#7B3F00", "#C49E3F", "#8B4D40", "#C2B280"],  # Style 1 (Natural)
        ["#2A252F", "#5C7A86", "#A32E31", "#3A565A"],  # Style 2 (Smokey)
        ["#E46253", "#50B2C0", "#FF6A8A", "#FF916F"]   # Style 3 (Tropical)
    ],
    # 5: Peachy Pink
    5: [
        ["#D8A47F", "#9FD9D9", "#F08A8A", "#F7E6C4"],  # Style 1 (Natural)
        ["#3B2F2F", "#6B8E23", "#C94C4C", "#A8B5BA"],  # Style 2 (Earthy)
        ["#E55986", "#5EC4D4", "#FF6B6B", "#FFD166"]   # Style 3 (Vivid)
    ],
    # 6: Honey Buff
    6: [
        ["#A9746E", "#C7D3D4", "#D87070", "#E9CFCF"],  # Style 1 (Natural)
        ["#2A252F", "#5C7A86", "#A32E31", "#3A565A"],  # Style 2 (Smokey)
        ["#DAA520", "#4682B4", "#CD5C5C", "#6B8E23"]   # Style 3 (Bold)
    ],
    # 7: Beige Rose
    7: [
        ["#DDC2B4", "#BCA69A", "#D99A9A", "#EBD5C8"],  # Style 1 (Natural)
        ["#B17B78", "#C9D5D5", "#D97474", "#EBCFCF"],  # Style 2 (Soft Rose)
        ["#6A5ACD", "#20B2AA", "#F08080", "#3A565A"]   # Style 3 (Royal)
    ]
}

# AI 모델 관련 전역 변수 초기화
kmeans_model = None
scaler = None
face_detector = None
face_parser = None
face_parsing_net = None # 가상 메이크업용 모델
models_loaded = False

# 이미지 텐서 변환 (가상 메이크업용)
to_tensor = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
])

def hex_to_bgr(hex_color):
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2],16)
    g = int(hex_color[2:4],16)
    b = int(hex_color[4:6],16)
    return [b,g,r]
# ==============================================================================
# 고급 조명 보정 함수들 (기존과 동일)
# ==============================================================================
def analyze_lighting_conditions(image_np):
    """이미지의 조명 상태를 분석하여 보정 전략을 결정"""
    lab = cv2.cvtColor(image_np, cv2.COLOR_RGB2LAB)
    l_channel = lab[:, :, 0]
    mean_brightness = np.mean(l_channel)
    std_brightness = np.std(l_channel)
    dark_pixels = np.sum(l_channel < 85) / l_channel.size
    bright_pixels = np.sum(l_channel > 170) / l_channel.size
    return {
        'mean_brightness': mean_brightness, 'std_brightness': std_brightness,
        'dark_ratio': dark_pixels, 'bright_ratio': bright_pixels,
        'is_underexposed': mean_brightness < 120 and dark_pixels > 0.3,
        'is_overexposed': mean_brightness > 180 and bright_pixels > 0.2,
        'has_low_contrast': std_brightness < 25, 'has_uneven_lighting': std_brightness > 50
    }

def white_balance_correction(image_np, method='gray_world'):
    """화이트 밸런스 보정"""
    image = image_np.astype(np.float32) / 255.0
    if method == 'gray_world':
        mean_rgb = np.mean(image.reshape(-1, 3), axis=0)
        scale_factors = 0.5 / (mean_rgb + 1e-8)
        corrected = image * scale_factors
    elif method == 'white_patch':
        max_rgb = np.max(image.reshape(-1, 3), axis=0)
        scale_factors = 1.0 / (max_rgb + 1e-8)
        corrected = image * scale_factors
    else: # illuminant_estimation
        h, w = image.shape[:2]
        block_means = [np.mean(image[i:i+h//3, j:j+w//3].reshape(-1, 3), axis=0) for i in range(0, h, h//3) for j in range(0, w, w//3) if image[i:i+h//3, j:j+w//3].size > 0]
        if block_means:
            illuminant = np.array(block_means)[np.argmax(np.sum(block_means, axis=1))]
            scale_factors = 0.9 / (illuminant + 1e-8)
            corrected = image * scale_factors
        else:
            corrected = image
    return (np.clip(corrected, 0, 1) * 255).astype(np.uint8)

def adaptive_histogram_equalization(image_np, clip_limit=3.0, tile_grid_size=(8, 8)):
    """적응적 히스토그램 평활화 (CLAHE)"""
    lab = cv2.cvtColor(image_np, cv2.COLOR_RGB2LAB)
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    lab[:, :, 0] = clahe.apply(lab[:, :, 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

def gamma_correction(image_np, gamma=1.0):
    """감마 보정"""
    inv_gamma = 1.0 / gamma
    table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    return cv2.LUT(image_np, table)

def shadow_highlight_correction(image_np, shadow_amount=0.0, highlight_amount=0.0, shadow_width=50, highlight_width=50):
    """그림자/하이라이트 보정"""
    lab = cv2.cvtColor(image_np, cv2.COLOR_RGB2LAB).astype(np.float32)
    l_channel = lab[:, :, 0] / 255.0
    shadow_mask = np.exp(-((l_channel - 0.0) ** 2) / (2 * (shadow_width / 255.0) ** 2))
    highlight_mask = np.exp(-((l_channel - 1.0) ** 2) / (2 * (highlight_width / 255.0) ** 2))
    if shadow_amount != 0.0:
        l_channel += shadow_amount * shadow_mask * (1.0 - l_channel)
    if highlight_amount != 0.0:
        l_channel += highlight_amount * highlight_mask * (l_channel - 1.0)
    lab[:, :, 0] = np.clip(l_channel, 0, 1) * 255.0
    return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

def unsharp_masking(image_np, strength=0.5, radius=1.0, threshold=0.0):
    """언샤프 마스킹을 통한 선명도 향상"""
    blurred = cv2.GaussianBlur(image_np, (0, 0), radius)
    mask = image_np.astype(np.float32) - blurred.astype(np.float32)
    if threshold > 0:
        mask = np.where(np.abs(mask) < threshold, 0, mask)
    sharpened = np.clip(image_np.astype(np.float32) + strength * mask, 0, 255).astype(np.uint8)
    return sharpened

def comprehensive_lighting_correction(image_np, lighting_info=None):
    """종합적인 조명 보정 파이프라인"""
    if lighting_info is None:
        lighting_info = analyze_lighting_conditions(image_np)
    
    corrected = image_np.copy()
    correction_log = []
    
    wb_method = 'gray_world'
    if lighting_info['bright_ratio'] > 0.15: wb_method = 'white_patch'
    elif lighting_info['has_uneven_lighting']: wb_method = 'illuminant_estimation'
    corrected = white_balance_correction(corrected, method=wb_method)
    correction_log.append(f"White balance: {wb_method}")
    
    if lighting_info['is_underexposed']:
        corrected = shadow_highlight_correction(corrected, shadow_amount=0.3, highlight_amount=-0.1)
        corrected = gamma_correction(corrected, 0.7)
        correction_log.append("Underexposure correction: shadow lift + gamma 0.7")
    elif lighting_info['is_overexposed']:
        corrected = shadow_highlight_correction(corrected, shadow_amount=0.0, highlight_amount=-0.4)
        corrected = gamma_correction(corrected, 1.3)
        correction_log.append("Overexposure correction: highlight recovery + gamma 1.3")
    
    if lighting_info['has_low_contrast']:
        clip_limit = 4.0 if lighting_info['std_brightness'] < 15 else 2.5
        corrected = adaptive_histogram_equalization(corrected, clip_limit=clip_limit)
        correction_log.append(f"Low contrast correction: CLAHE (clip_limit={clip_limit})")
    elif lighting_info['has_uneven_lighting']:
        corrected = adaptive_histogram_equalization(corrected, clip_limit=2.0, tile_grid_size=(6, 6))
        correction_log.append("Uneven lighting correction: Soft CLAHE")
    
    if lighting_info['std_brightness'] < 30:
        corrected = unsharp_masking(corrected, strength=0.3, radius=1.2)
        correction_log.append("Sharpening applied")
        
    return corrected, correction_log

# ==============================================================================
# 모델 로드 및 주요 함수
# ==============================================================================

def load_models():
    """AI 모델과 스케일러를 로드하는 함수"""
    global kmeans_model, scaler, face_detector, face_parser, models_loaded, face_parsing_net
    
    try:
        print("Loading AI models...")
        
        # 퍼스널 컬러 진단 모델
        kmeans_model = joblib.load(os.path.join(MODEL_DIR, 'kmeans_model.joblib'))
        scaler = joblib.load(os.path.join(MODEL_DIR, 'scaler.joblib'))
        print("✓ K-means model and scaler loaded successfully.")

        # Facer 라이브러리의 얼굴 관련 모델들
        face_detector = facer.face_detector('retinaface/mobilenet', device=device)
        face_parser = facer.face_parser('farl/celebm/448', device=device)
        print("✓ Facer models loaded successfully.")
        
        # 가상 메이크업용 모델 로드 추가
        face_parsing_net = BiSeNet(n_classes=19)
        # 79999_iter.pth 파일이 'res/cp/' 폴더 안에 있어야 합니다.
        face_parsing_net.load_state_dict(torch.load('res/cp/79999_iter.pth', map_location='cpu'))
        face_parsing_net.eval()
        print("✓ Face Parsing model for makeover loaded successfully.")
        
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

def extract_facial_part_colors(image: Image.Image, n_colors_per_part=7, apply_lighting_correction=True, is_camera_input=False):
    """얼굴에서 피부 색상 특징(Lab 색공간)을 추출하는 핵심 함수 (조명 보정 포함)"""
    try:
        image_np = np.array(image)
        
        # 카메라 입력의 경우 노이즈 감소를 위해 양방향 필터 적용
        if is_camera_input:
            image_np = cv2.bilateralFilter(image_np, d=9, sigmaColor=75, sigmaSpace=75)

        correction_log = []
        if apply_lighting_correction:
            image_np, correction_log = comprehensive_lighting_correction(image_np)
            image = Image.fromarray(image_np)
        
        image_resized = image.resize((448, 448))
        image_tensor = torch.from_numpy(np.array(image_resized)).permute(2, 0, 1).unsqueeze(0).to(device)

        with torch.inference_mode():
            faces = face_detector(image_tensor)
            if len(faces['scores']) == 0 or faces['scores'][0] < 0.5:
                return None, "얼굴을 감지할 수 없습니다.", []
            faces = face_parser(image_tensor, faces)

        seg_map = faces['seg']['logits'].argmax(dim=1).squeeze(0).cpu().numpy()
        image_lab = cv2.cvtColor(np.array(image_resized), cv2.COLOR_RGB2Lab)
        skin_pixels = image_lab[np.isin(seg_map, [1, 2])]

        if len(skin_pixels) < n_colors_per_part:
            return None, "피부 영역이 충분하지 않습니다.", correction_log

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
    page = request.args.get('page', 'home')
    return render_template('index.html', user=session.get('user'), initial_page=page)

@app.route('/analyze', methods=['POST'])
def analyze():
    """이미지 분석을 수행하는 메인 API 엔드포인트"""
    if 'user' not in session:
        return jsonify({'error': '로그인이 필요한 서비스입니다.'}), 401

    if not models_loaded:
        return jsonify({'error': 'AI 모델이 로드되지 않았습니다.'}), 503

    try:
        image = None
        is_camera_input = False
        filename = f"upload_{np.datetime64('now').astype(int)}.jpg"
        apply_correction = request.form.get('apply_lighting_correction', 'true').lower() == 'true'
        
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '' or not allowed_file(file.filename):
                return jsonify({'error': '잘못된 파일입니다.'}), 400
            image = Image.open(file.stream).convert('RGB')
        elif request.json and 'image_data' in request.json:
            is_camera_input = True
            image_data = request.json['image_data'].split(',')[1]
            image = Image.open(BytesIO(base64.b64decode(image_data))).convert('RGB')
            apply_correction = request.json.get('apply_lighting_correction', True)
        else:
            return jsonify({'error': '이미지 파일 또는 데이터가 필요합니다.'}), 400

        lab_features, error_msg, correction_log = extract_facial_part_colors(
            image,
            n_colors_per_part=N_REPRESENTATIVE_COLORS,
            apply_lighting_correction=apply_correction,
            is_camera_input=is_camera_input
        )
        
        if error_msg:
            return jsonify({'error': error_msg}), 400

        scaled_features = scaler.transform(lab_features)
        predicted_cluster = kmeans_model.predict(scaled_features)[0]
        cluster_info = get_cluster_info(predicted_cluster)
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        image.save(filepath, 'JPEG')

        return jsonify({
            "success": True, "cluster_id": int(predicted_cluster),
            "personal_color_type": cluster_info["name"], "visual_name": cluster_info["visual_name"],
            "type_description": cluster_info["description"], "palette": cluster_info["palette"],
            "uploaded_image_url": f'/uploads/{filename}', "lighting_correction_applied": apply_correction,
            "correction_log": correction_log
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'분석 중 오류가 발생했습니다: {str(e)}'}), 500

@app.route('/makeover')
def makeover():
    """가상 스타일링 페이지를 렌더링하는 라우트"""
    filename = request.args.get('filename')
    cluster_num = request.args.get('cluster_num', type=int)
    palette_num = request.args.get('palette_num', type=int, default=0)

    if not filename or cluster_num is None:
        return "오류: 필요한 정보(파일 이름, 클러스터 번호)가 없습니다.", 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    img_bgr = cv2.imread(filepath)
    if img_bgr is None:
        return "오류: 원본 이미지 파일을 찾을 수 없습니다.", 404
        
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    # 얼굴 영역 파싱
    img_pil_resized = Image.fromarray(img_rgb).resize((512, 512))
    img_tensor = to_tensor(img_pil_resized).unsqueeze(0)
    with torch.no_grad():
        out = face_parsing_net(img_tensor)[0]
    parsing = out.squeeze(0).cpu().numpy().argmax(0)
    
    # 원본 이미지 크기에 맞게 파싱 마스크 리사이즈
    parsing_resized = np.array(Image.fromarray(parsing.astype(np.uint8)).resize((img_rgb.shape[1], img_rgb.shape[0]), Image.NEAREST))
    
    # 선택된 팔레트
    selected_palette = MAKEOVER_PALETTES.get(cluster_num)[palette_num]
    hair_color = hex_to_bgr(selected_palette[0])
    lens_color = hex_to_bgr(selected_palette[1])
    lip_color = hex_to_bgr(selected_palette[2])

    # 메이크업 적용
    img_makeup = hair(img_bgr, parsing_resized, 17, hair_color)      # 헤어
    img_makeup = hair(img_makeup, parsing_resized, 12, lip_color)    # 윗입술
    img_makeup = hair(img_makeup, parsing_resized, 13, lip_color)    # 아랫입술
    # 렌즈는 hair 함수를 재사용하되, 다른 파트 번호와 색상을 전달
    img_makeup = hair(img_makeup, parsing_resized, 4, lens_color)    # 왼쪽 눈
    img_makeup = hair(img_makeup, parsing_resized, 5, lens_color)    # 오른쪽 눈

    # 결과 이미지 저장
    result_filename = f"makeover_{palette_num}_{filename}"
    result_path = os.path.join(app.config['UPLOAD_FOLDER'], result_filename)
    cv2.imwrite(result_path, img_makeup)

    return render_template("makeover.html",
                           original_image=filename,
                           result_image=result_filename,
                           palettes=MAKEOVER_PALETTES,
                           selected_cluster=cluster_num,
                           selected_palette=palette_num,
                           user=session.get('user'))


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """업로드된 이미지 파일을 제공하는 라우트"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/guide')
def guide():
    """컬러 가이드 페이지를 렌더링하는 라우트"""
    return render_template('guide.html', user=session.get('user'))

@app.route('/about')
def about():
    """팀 소개 페이지를 렌더링하는 라우트"""
    return render_template('about.html', user=session.get('user'))

# ==============================================================================
# 사용자 인증 관련 라우트
# ==============================================================================

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json(silent=True)
    if not data or not all(k in data for k in ['name', 'password', 'email', 'sex']):
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    db = get_db()
    users = db.collection('users')

    # Check if name (ID) already exists
    name_query = users.where(field_path='name', op_string='==', value=data['name']).limit(1).stream()
    if next(name_query, None) is not None:
        return jsonify({'status': 'error', 'message': 'ID already exists'}), 400

    # Check if email already exists
    doc_ref = users.document(data['email'])
    if doc_ref.get().exists:
        return jsonify({'status': 'error', 'message': 'Email already exists'}), 400
    
    # 비밀번호를 해싱하여 저장
    hashed_password = generate_password_hash(data['password'])
    
    user_data = {
        'name': data['name'],
        'email': data['email'],
        'sex': data['sex'],
        'password': hashed_password
    }
    
    doc_ref.set(user_data)
    
    return jsonify({'status': 'success'}), 200

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True)
    if not data or not all(k in data for k in ['name', 'password']):
        return jsonify({'status': 'error', 'message': 'Missing name or password'}), 400

    db = get_db()
    users = db.collection('users')
    
    login_identifier = data['name']
    password = data['password']
    
    user_doc = None
    # Check if the identifier is an email
    if '@' in login_identifier:
        doc_ref = users.document(login_identifier)
        user_doc = doc_ref.get()
    else:
        # Assume it's a name/ID
        query = users.where(field_path='name', op_string='==', value=login_identifier).limit(1).stream()
        user_doc = next(query, None)

    user_data = user_doc.to_dict() if user_doc and user_doc.exists else None

    if user_data is None:
        return jsonify({'status': 'error', 'message': 'Invalid name or password'}), 401

    stored_password = user_data.get('password', '')
    
    # Use check_password_hash directly. It safely handles non-hashed strings by returning False.
    # Then, check for plaintext password for legacy support.
    if check_password_hash(stored_password, password) or stored_password == password:
        # If it was a plaintext password, hash it and update the DB.
        if not stored_password.startswith('pbkdf2:sha256') and stored_password == password:
            try:
                new_hashed_password = generate_password_hash(password)
                users.document(user_doc.id).update({'password': new_hashed_password})
                print(f"Password for user {user_data['name']} has been securely hashed.")
            except Exception as e:
                print(f"Error updating password for user {user_data['name']}: {e}")
        
        # If we are here, the password is correct.
        user_session_data = {
            'name': user_data.get('name'),
            'email': user_data.get('email'),
            'sex': user_data.get('sex'),
            'image': None if not user_data.get('image') else f"/user_image/{user_data.get('name')}"
        }
        session['user'] = user_session_data
        
        return jsonify({'status': 'success', 'user': user_session_data}), 200

    # If both checks fail, the password is wrong.
    return jsonify({'status': 'error', 'message': 'Invalid name or password'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'status': 'success'}), 200

@app.route('/me', methods=['GET'])
def get_profile():
    if not session.get('user'):
        return jsonify({'status': 'error', 'message': 'Not logged in'}), 401
    return jsonify({'status': 'success', 'user': session['user']}), 200


# ==============================================================================
# 메인 실행 부분
# ==============================================================================
if __name__ == '__main__':
    load_models()
    
    print("=" * 70)
    print(f"🚀 Enhanced Personal Color & Makeover Server Starting...")
    print(f"📱 Model Status: {'✅ Loaded' if models_loaded else '❌ Failed'}")
    print(f"🖥️  Device: {device}")
    print(f"🌐 Server: http://127.0.0.1:5001")
    print("=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=5001)
