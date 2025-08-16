/******************************************************
 * 전역 상태
 ******************************************************/
// 업로드/촬영된 이미지를 서버로 보낼 때 사용할 전역 변수
let fileForAnalysis = null;

// 로그인된 사용자 정보를 저장할 전역 변수
window.loggedInUser = null;

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

    // 이전에 활성화된 모든 로딩 단계를 재설정
    const allSteps = document.querySelectorAll('.loading-step');
    allSteps.forEach(step => step.classList.remove('active'));

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

        analyzedClusterId = data.cluster_id;
        uploadedFilename = data.uploaded_image_url.split('/').pop(); // URL에서 파일명 추출

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

let analyzedClusterId = null; // 분석된 클러스터 ID
let uploadedFilename = null; // 업로드된 파일의 이름

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
 * 로그인/회원가입 모달 관련
 ******************************************************/
/**
 * 로그인 모달 표시
 */
function showLoginModal() {
    document.getElementById('loginModal').style.display = 'block';
}

/**
 * 로그인 모달 닫기
 */
function closeLoginModal() {
    document.getElementById('loginModal').style.display = 'none';
}

/**
 * 회원가입 모달 표시
 */
function showSignupModal() {
    document.getElementById('signupModal').style.display = 'block';
}

/**
 * 회원가입 모달 닫기
 */
function closeSignupModal() {
    document.getElementById('signupModal').style.display = 'none';
}

/**
 * 프로필 모달 닫기
 */
function closeProfileModal() {
    document.getElementById('profileModal').style.display = 'none';
}

/**
 * 회원가입 처리
 */
function signupUser() {
    const name = document.getElementById('signupName').value.trim();
    const password = document.getElementById('signupPassword').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const sex = document.querySelector('#signupModal input[name="sex"]:checked')?.value;

    // 유효성 검사 강화
    if (!name || !password || !email || !sex) {
        alert('모든 정보를 입력해주세요!');
        return;
    }

    if (password.length < 4) {
        alert('비밀번호는 4자 이상이어야 합니다.');
        return;
    }

    if (!email.includes('@')) {
        alert('올바른 이메일 형식을 입력해주세요.');
        return;
    }

    console.log('회원가입 시도:', { name, email, sex });

    fetch('/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password, sex })
    })
        .then(response => {
            console.log('회원가입 응답 상태:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('회원가입 응답 데이터:', data);
            if (data.status === 'success') {
                alert('회원가입 성공!');
                closeSignupModal();
                // 입력 필드 초기화
                document.getElementById('signupName').value = '';
                document.getElementById('signupPassword').value = '';
                document.getElementById('signupEmail').value = '';
                document.querySelector('#signupModal input[name="sex"]:checked').checked = false;
            } else {
                alert(data.message || '회원가입 실패!');
            }
        })
        .catch(error => {
            console.error('회원가입 오류:', error);
            alert('서버 연결 오류가 발생했습니다. 나중에 다시 시도해주세요.');
        });
}



/**
 * 로그인 처리
 */
function loginUser() {
    console.log('✅ loginUser 함수가 성공적으로 호출되었습니다!'); // 이 라인을 추가!
    const name = document.getElementById('loginName').value.trim();
    const password = document.getElementById('loginPassword').value.trim();

    if (!name || !password) {
        alert("아이디와 비밀번호를 입력해주세요.");
        return;
    }

    console.log('로그인 시도:', { name });

    fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name, password })
    })
        .then(response => {
            console.log('로그인 응답 상태:', response.status);
            if (!response.ok) {
                throw new Error("아이디 또는 비밀번호가 일치하지 않습니다.");
            }
            return response.json();
        })
        .then(data => {
            console.log('로그인 응답 데이터:', data);
            if (data.status === 'success' && data.user) {
                alert('로그인 성공!');
                location.reload();
            } else {
                throw new Error(data.message || '로그인에 실패했습니다.');
            }
        })
        .catch(error => {
            console.error('로그인 오류:', error);
            alert(error.message);
        });
}

/**
 * 로그아웃 처리
 */
function logoutUser() {
    fetch('/logout', {
        method: 'POST',
        credentials: 'include'
    })
        .then(response => {
            if (response.ok) {
                alert('로그아웃 되었습니다.');
                location.reload();
            } else {
                alert('로그아웃에 실패했습니다.');
            }
        })
        .catch(error => {
            console.error('Logout error:', error);
            alert('로그아웃 중 오류가 발생했습니다.');
        });
}



/**
 * 사용자 프로필 표시
 */
function showProfile() {
    const user = window.loggedInUser;
    if (!user) {
        alert("로그인된 사용자가 없습니다.");
        return;
    }

    document.getElementById('profileContent').innerHTML = `
        <p><strong>이름:</strong> ${user.name}</p>
        <p><strong>이메일:</strong> ${user.email}</p>
        <p><strong>성별:</strong> ${user.sex}</p>
        ${user.image ? `<img src="${user.image}" style="width:100px; border-radius:10px;">` : '<p>이미지 없음</p>'}
    `;
    document.getElementById('profileModal').style.display = 'block';
}
function closeProfile() {
    document.getElementById('profileModal').style.display = 'none';
}

/******************************************************
 * 탭/시뮬레이션/공유 등 UI 유틸
 ******************************************************/
/**
 * 결과 화면 내 탭 전환용
 * - 현재 구현은 event 객체를 직접 사용하고 있어, 함수 시그니처를 switchTab(event, tabName)으로 바꾸는게 안전
 * - 또는 addEventListener 내부에서 화살표 함수로 event를 캡처하는 방식 추천
 */
function switchTab(event, tabName) {
    const buttons = document.querySelectorAll('.tab-button');
    buttons.forEach(btn => btn.classList.remove('active'));

    // 클릭된 버튼을 활성화합니다.
    // HTML의 onclick에서 event 객체를 전달해야 합니다. (예: onclick="switchTab(event, 'cosmetics')")
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active');
    }

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
    if (!container) return; // 컨테이너가 없으면 실행하지 않음

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



// 파일 맨 아래에 새로운 함수 추가
function goToMakeover() {
    if (uploadedFilename && analyzedClusterId !== null) {
        // 분석된 결과를 바탕으로 makeover 페이지로 이동
        window.location.href = `/makeover?filename=${uploadedFilename}&cluster_num=${analyzedClusterId}`;
    } else {
        alert("먼저 이미지를 분석해주세요.");
    }
}