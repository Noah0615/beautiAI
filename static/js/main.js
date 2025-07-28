/******************************************************
 * 전역 상태
 ******************************************************/
// 업로드/촬영된 이미지를 서버로 보낼 때 사용할 전역 변수
let fileForAnalysis = null;

/******************************************************
 * 페이지 전환 관련
 ******************************************************/
/**
 * id가 pageId인 섹션을 보여주고, 나머지는 숨김
 * 또한 업로드 페이지에서 벗어날 때는 웹캠을 중지
 */
function showPage(pageId) {
    const pages = document.querySelectorAll('.page-section');
    pages.forEach(page => page.classList.remove('active'));
    document.getElementById(pageId).classList.add('active');

    // 업로드 페이지가 아닐 경우 웹캠 스트림 종료
    if (pageId !== 'upload') {
        closeWebcam();
    }
}

/******************************************************
 * 파일 업로드 처리
 ******************************************************/
/**
 * <input type="file">의 change 이벤트 핸들러
 * 사용자가 실제로 선택한 첫 번째 파일을 displayAndSetFile로 전달
 */
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        displayAndSetFile(file);
    }
}

/**
 * 공통 로직: 전달받은 파일을
 * 1) 전역 변수에 저장하고
 * 2) 업로드 화면과 결과 화면에 미리보기 이미지를 렌더링하며
 * 3) "분석 시작" 버튼을 보이도록 설정
 */
function displayAndSetFile(file) {
    fileForAnalysis = file;

    const reader = new FileReader();
    reader.onload = function (e) {
        // 업로드 페이지의 프리뷰에 표시
        const previewContainer = document.getElementById('uploadPreview');
        previewContainer.innerHTML = `
            <img src="${e.target.result}" style="max-width: 100%; max-height: 200px; border-radius: 10px; margin-top: 1rem;">
        `;

        // 결과 페이지에도 동일 이미지를 미리 깔아둠(로딩 후 서버 URL로 교체될 수 있음)
        document.getElementById('uploadedPhoto').innerHTML = `
            <img src="${e.target.result}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 10px;">
        `;
    };
    // 파일을 Base64 DataURL로 읽어와서 미리보기에 사용
    reader.readAsDataURL(file);

    // 파일이 선택되면 분석 버튼을 노출
    document.getElementById('analyzeBtn').style.display = 'inline-block';
}

/******************************************************
 * 분석 시작 (백엔드와 통신)
 ******************************************************/
/**
 * 파일이 준비되었는지 확인하고,
 * 로딩 페이지로 전환하면서 단계별 애니메이션을 보여준 후
 * /analyze 엔드포인트로 FormData를 POST.
 * 성공 시 결과 화면을 업데이트하고 페이지 전환.
 */
async function startAnalysis() {
    // 파일이 없으면 사용자에게 알림
    if (!fileForAnalysis) {
        alert("먼저 사진을 선택하거나 촬영해주세요.");
        return;
    }

    // 로딩 화면으로 이동
    showPage('loading');

    // 로딩 단계 애니메이션 (step1~step4 순차 활성화)
    const steps = ['step1', 'step2', 'step3', 'step4'];
    let currentStep = 0;
    const progressInterval = setInterval(() => {
        if (currentStep < steps.length) {
            document.getElementById(steps[currentStep]).classList.add('active');
            currentStep++;
        } else {
            clearInterval(progressInterval);
        }
    }, 1000);

    // 서버로 전송할 폼 데이터 구성
    const formData = new FormData();
    formData.append('file', fileForAnalysis);

    try {
        // 백엔드 호출
        const response = await fetch('/analyze', {
            method: 'POST',
            body: formData
        });

        // HTTP 에러 핸들링
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // JSON 파싱
        const data = await response.json();

        // ----- 결과 페이지 구성 -----
        // 1) 타입명 + 설명
        document.querySelector('#result .result-info h2').textContent = `${data.personal_color_type} ✨`;
        document.querySelector('#result .result-info p').textContent = data.type_description;

        // 2) 팔레트 스와치 채우기
        const paletteContainer = document.querySelector('#result .color-palette');
        paletteContainer.innerHTML = ''; // 기존 스와치 제거
        data.palette.forEach(color => {
            const swatch = document.createElement('div');
            swatch.className = 'color-swatch';
            swatch.style.background = color;
            paletteContainer.appendChild(swatch);
        });

        // 3) 서버가 반환한 최종 업로드 이미지 URL로 교체
        document.getElementById('uploadedPhoto').innerHTML = `
            <img src="${data.uploaded_image_url}" style="width: 100%; height: 100%; object-fit: cover; border-radius: 10px;">
        `;

        // 로딩 인터벌 정리 및 결과 페이지로 전환
        clearInterval(progressInterval);
        showPage('result');

    } catch (error) {
        console.error('Analysis failed:', error);
        alert('분석에 실패했습니다. 다시 시도해주세요.');

        // 인터벌 정리 및 업로드 페이지로 복귀
        clearInterval(progressInterval);
        showPage('upload');
    }
}

/******************************************************
 * 웹캠 관련
 ******************************************************/
// 모달/비디오 요소 (전역에서 재사용)
const modal = document.getElementById('webcamModal');
const video = document.getElementById('webcamVideo');
// getUserMedia로 얻는 MediaStream을 추후 정지하기 위해 저장
let stream = null;

/**
 * 웹캠 열기: 사용자에게 카메라 접근 권한을 요청하고,
 * 비디오 요소에 스트림을 연결, 모달 표시
 */
async function openWebcam() {
    try {
        // 카메라 권한 요청 및 스트림 획득
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        modal.style.display = 'block';
    } catch (err) {
        console.error("Error accessing webcam: ", err);
        alert("카메라에 접근할 수 없습니다. 브라우저 설정을 확인해주세요.");
    }
}

/**
 * 웹캠 닫기: 모든 트랙을 stop()하여 카메라 해제,
 * 모달 숨김
 */
function closeWebcam() {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    modal.style.display = 'none';
}

/**
 * 현재 비디오 프레임을 캡처하여 Blob -> File로 만들고
 * displayAndSetFile 호출(즉, 일반 업로드와 동일한 플로우로 처리)
 */
function takeSnapshot() {
    // 비디오 프레임 해상도대로 캔버스 생성
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const context = canvas.getContext('2d');
    context.drawImage(video, 0, 0, canvas.width, canvas.height);

    // 웹캠 종료
    closeWebcam();

    // 캔버스를 JPEG Blob으로 변환 후 File 객체 생성
    canvas.toBlob(function (blob) {
        const timestamp = new Date().getTime();
        const snapshotFile = new File([blob], `snapshot_${timestamp}.jpg`, { type: 'image/jpeg' });

        // 업로드된 파일과 동일한 경로로 처리
        displayAndSetFile(snapshotFile);
    }, 'image/jpeg');
}

/******************************************************
 * 탭/시뮬레이션/공유 등 UI 유틸
 ******************************************************/
/**
 * 결과 화면 내 탭 전환용
 * - 현재 구현은 event 객체를 직접 사용하고 있어, 함수 시그니처를 switchTab(event, tabName)으로 바꾸는게 안전
 * - 또는 addEventListener 내부에서 화살표 함수로 event를 캡처하는 방식 추천
 */
function switchTab(tabName) {
    const buttons = document.querySelectorAll('.tab-button');
    buttons.forEach(btn => btn.classList.remove('active'));

    // ⚠️ 아래 코드에서 event는 전역이 아님. 브라우저에 따라 동작하지 않을 수 있음.
    // 안전하게 하려면 인자로 받은 event.currentTarget을 쓰도록 수정 필요.
    event.target.classList.add('active');

    // TODO: tabName에 따라 각기 다른 컬러 옵션 UI를 보여주는 로직 작성
}

/**
 * 특정 타입(예: 립/상의 등)에 특정 색상을 적용하는 시뮬레이션
 * 실제 구현에서는 캔버스/웹GL/필터 등을 통해 미리보기 이미지에 색을 입히게 될 것
 */
function applyColor(type, color) {
    console.log(`Applying ${color} to ${type}`);
    alert(`${type}에 ${color} 색상을 적용합니다. (실제 구현에서는 가상 스타일링 이미지를 보여줍니다)`);
}

/**
 * 결과 저장(예: PDF 다운로드 등) – 현재는 단순 알림
 */
function saveResult() {
    alert('결과가 저장되었습니다! (실제 구현에서는 PDF 다운로드 등)');
}

/**
 * 결과 공유(예: 카카오톡/인스타그램 공유) – 현재는 단순 알림
 */
function shareResult() {
    alert('소셜 미디어 공유 기능 (실제 구현에서는 카카오톡, 인스타그램 등)');
}

/******************************************************
 * 드래그 앤 드롭 업로드
 ******************************************************/
const uploadAreaContainer = document.querySelector('.upload-section');

// 파일이 dragover 되는 동안 기본 동작(열기 등) 막기
uploadAreaContainer.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.stopPropagation();
});

// 영역을 벗어났을 때도 기본 동작 막기
uploadAreaContainer.addEventListener('dragleave', (e) => {
    e.preventDefault();
    e.stopPropagation();
});

// 드롭됐을 때 파일을 읽어 displayAndSetFile로 넘김
uploadAreaContainer.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();

    const files = e.dataTransfer.files;
    if (files.length > 0) {
        displayAndSetFile(files[0]);
    }
});

/******************************************************
 * 배경 파티클 애니메이션
 ******************************************************/
/**
 * .animated-bg 컨테이너 안에 랜덤 위치/크기의 파티클 div를
 * 20개 생성하고, 각각 다른 animationDelay/Duration을 적용
 */
function createParticles() {
    const container = document.querySelector('.animated-bg');
    for (let i = 0; i < 20; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.top = Math.random() * 100 + '%';
        particle.style.width = Math.random() * 10 + 5 + 'px';
        particle.style.height = particle.style.width;
        particle.style.animationDelay = Math.random() * 6 + 's';
        particle.style.animationDuration = (Math.random() * 3 + 3) + 's';
        container.appendChild(particle);
    }
}

// 페이지가 로드되면 파티클을 생성
window.addEventListener('load', createParticles);
