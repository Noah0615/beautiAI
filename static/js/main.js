/******************************************************
 * 전역 상태
 ******************************************************/
let fileForAnalysis = null;
let analyzedClusterId = null;
let uploadedFilename = null;
window.loggedInUser = null;

/******************************************************
 * UI 유틸리티
 ******************************************************/

function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container');
    if (!container) return;
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    container.appendChild(notification);

    setTimeout(() => {
        notification.style.opacity = '0';
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => notification.remove(), 500);
    }, 3000);
}

function controlModal(modalId, show) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = show ? 'block' : 'none';
    }
}

/******************************************************
 * 페이지 전환 관련
 ******************************************************/
function showPage(pageId) {
    document.querySelectorAll('.page-section').forEach(page => page.classList.remove('active'));
    const newPage = document.getElementById(pageId);
    if (newPage) {
        newPage.classList.add('active');
    } else {
        console.warn(`Page with id '${pageId}' not found. Returning to home.`);
        document.getElementById('home').classList.add('active');
    }

    if (document.getElementById('webcamModal').style.display === 'block') {
        closeWebcam();
    }
}

/******************************************************
 * 파일 업로드 처리
 ******************************************************/
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        displayAndSetFile(file);
    }
}

function displayAndSetFile(file) {
    fileForAnalysis = file;
    const reader = new FileReader();
    reader.onload = function (e) {
        const imgPreview = `<img src="${e.target.result}" class="user-image-display">`;
        document.getElementById('uploadPreview').innerHTML = imgPreview;
        document.getElementById('uploadedPhoto').innerHTML = `<img src="${e.target.result}" class="user-image-display">`;
    };
    reader.readAsDataURL(file);
    document.getElementById('analyzeBtn').style.display = 'inline-block';
}

/******************************************************
 * 분석 시작 (백엔드와 통신)
 ******************************************************/
async function startAnalysis() {
    if (!fileForAnalysis) {
        return showNotification("먼저 사진을 선택하거나 촬영해주세요.", "error");
    }
    showPage('loading');

    // 로딩 단계 애니메이션 (step1~step4 순차 활성화)
    const steps = ['step1', 'step2', 'step3', 'step4'];
    let currentStep = 0;
    const progressInterval = setInterval(() => {
        if (currentStep < steps.length) {
            const stepEl = document.getElementById(steps[currentStep]);
            if(stepEl) stepEl.classList.add('active');
            currentStep++;
        } else {
            clearInterval(progressInterval);
        }
    }, 800);

    const formData = new FormData();
    formData.append('file', fileForAnalysis);

    try {
        const response = await fetch('/analyze', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        document.querySelector('#result .result-info h2').textContent = `${data.visual_name} ✨`;
        document.querySelector('#result .result-info p').textContent = data.type_description;

        const paletteContainer = document.querySelector('#result .color-palette');
        paletteContainer.innerHTML = '';
        data.palette.forEach(color => {
            const swatch = document.createElement('div');
            swatch.className = 'color-swatch';
            swatch.style.background = color;
            paletteContainer.appendChild(swatch);
        });

        document.getElementById('uploadedPhoto').innerHTML = `<img src="${data.uploaded_image_url}" class="user-image-display">`;
        analyzedClusterId = data.cluster_id;
        uploadedFilename = data.uploaded_image_url.split('/').pop();
        
        clearInterval(progressInterval); // Clear interval on success
        showPage('result');

    } catch (error) {
        clearInterval(progressInterval); // Clear interval on error
        console.error('Analysis failed:', error);
        showNotification(error.message || '분석에 실패했습니다. 다시 시도해주세요.', 'error');
        showPage('upload');
    }
}

/******************************************************
 * 웹캠 관련
 ******************************************************/
let stream = null;
const video = document.getElementById('webcamVideo');

async function openWebcam() {
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('카메라 API를 사용할 수 없는 브라우저입니다.');
        }
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
        video.srcObject = stream;
        controlModal('webcamModal', true);
    } catch (err) {
        console.error("Error accessing webcam: ", err);
        showNotification(err.message || "카메라에 접근할 수 없습니다. 브라우저 설정을 확인해주세요.", "error");
    }
}

function closeWebcam() {
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
    }
    controlModal('webcamModal', false);
}

function takeSnapshot() {
    if (!video.srcObject) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
    closeWebcam();
    canvas.toBlob(blob => {
        const snapshotFile = new File([blob], `snapshot_${new Date().getTime()}.jpg`, { type: 'image/jpeg' });
        displayAndSetFile(snapshotFile);
    }, 'image/jpeg');
}

/******************************************************
 * 인증 관련 (로그인/회원가입/프로필)
 ******************************************************/
function signupUser() {
    const form = document.getElementById('signupForm');
    const name = form.elements.signupName.value.trim();
    const password = form.elements.signupPassword.value.trim();
    const email = form.elements.signupEmail.value.trim();
    const sex = form.elements.sex.value;

    if (!name || !password || !email || !sex) return showNotification('모든 정보를 입력해주세요!', 'error');
    if (password.length < 4) return showNotification('비밀번호는 4자 이상이어야 합니다.', 'error');
    if (!email.includes('@')) return showNotification('올바른 이메일 형식을 입력해주세요.', 'error');

    fetch('/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password, sex })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            showNotification('회원가입 성공! 이제 로그인해주세요.', 'success');
            controlModal('signupModal', false);
            form.reset();
        } else {
            showNotification(data.message || '회원가입 실패!', 'error');
        }
    })
    .catch(err => {
        console.error('Signup error:', err);
        showNotification('서버 연결 오류가 발생했습니다.', 'error');
    });
}

function loginUser() {
    const form = document.getElementById('loginForm');
    const name = form.elements.loginName.value.trim();
    const password = form.elements.loginPassword.value.trim();

    if (!name || !password) return showNotification("아이디와 비밀번호를 입력해주세요.", "error");

    fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name, password })
    })
    .then(res => {
        if (!res.ok) return res.json().then(err => { throw new Error(err.message || "로그인 실패") });
        return res.json();
    })
    .then(data => {
        if (data.status === 'success' && data.user) {
            showNotification('로그인 성공!', 'success');
            updateNav(data.user);
            controlModal('loginModal', false);
            form.reset();
        } else {
            throw new Error(data.message || '로그인에 실패했습니다.');
        }
    })
    .catch(err => {
        console.error('Login error:', err);
        showNotification(err.message, 'error');
    });
}

function logoutUser() {
    fetch('/logout', { method: 'POST', credentials: 'include' })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            showNotification('로그아웃 되었습니다.', 'info');
            updateNav(null);
            window.location.href = '/';
        } else {
            showNotification('로그아웃에 실패했습니다.', 'error');
        }
    })
    .catch(err => {
        console.error('Logout error:', err);
        showNotification('로그아웃 중 오류가 발생했습니다.', 'error');
    });
}

async function checkLoginStatus() {
    try {
        const response = await fetch('/me', { credentials: 'include' });
        const data = await response.json();
        updateNav(response.ok && data.status === 'success' ? data.user : null);
    } catch (error) {
        console.error('Could not check login status:', error);
        updateNav(null);
    }
}

function updateNav(user) {
    window.loggedInUser = user;
    const navUl = document.querySelector('nav ul');
    navUl.querySelectorAll('.auth-nav').forEach(el => el.remove());

    if (user) {
        navUl.insertAdjacentHTML('beforeend', `
            <li class="auth-nav"><a href="#" data-modal="profileModal">👤 ${user.name}</a></li>
            <li class="auth-nav"><a href="#" id="logoutBtn">로그아웃</a></li>
        `);
        document.getElementById('profileContent').innerHTML = `
            <p><strong>이름:</strong> ${user.name}</p>
            <p><strong>이메일:</strong> ${user.email}</p>
            <p><strong>성별:</strong> ${user.sex === 'male' ? '남성' : '여성'}</p>
            ${user.image ? `<img src="${user.image}" class="profile-image">` : ''}
        `;
    } else {
        navUl.insertAdjacentHTML('beforeend', `
            <li class="auth-nav"><a href="#" data-modal="loginModal">로그인</a></li>
            <li class="auth-nav"><a href="#" data-modal="signupModal">회원가입</a></li>
        `);
    }
}

/******************************************************
 * 기타 UI 및 초기화
 ******************************************************/
function goToMakeover() {
    if (uploadedFilename && analyzedClusterId !== null) {
        window.location.href = `/makeover?filename=${uploadedFilename}&cluster_num=${analyzedClusterId}`;
    } else {
        showNotification("먼저 이미지를 분석해주세요.", "error");
    }
}

function createParticles() {
    const container = document.querySelector('.animated-bg');
    if (!container) return;
    for (let i = 0; i < 20; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = `${Math.random() * 100}%`;
        particle.style.top = `${Math.random() * 100}%`;
        const size = Math.random() * 10 + 5;
        particle.style.width = `${size}px`;
        particle.style.height = `${size}px`;
        particle.style.animationDelay = `${Math.random() * 6}s`;
        particle.style.animationDuration = `${Math.random() * 3 + 3}s`;
        container.appendChild(particle);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    createParticles();
    checkLoginStatus();

    const isMakeoverPage = !!document.querySelector('.makeover-container');

    if (isMakeoverPage) {
        // makeover.html: 네비게이션 링크를 절대 경로로 수정
        document.querySelectorAll('nav a[data-page]').forEach(link => {
            link.href = `/?page=${link.dataset.page}`;
        });
    } else {
        // index.html: 초기 페이지 설정
        const initialPage = document.body.dataset.initialPage || 'home';
        showPage(initialPage);
    }

    // 전역 이벤트 위임 (Event Delegation)
    document.body.addEventListener('click', e => {
        const target = e.target;
        const pageLink = target.closest('[data-page]');
        const modalLink = target.closest('[data-modal]');
        const closeModalBtn = target.closest('.close-button');

        if (pageLink && !isMakeoverPage) { // index.html에서만 SPA처럼 동작
            e.preventDefault();
            const pageId = pageLink.dataset.page;
            if (pageId === 'upload' && !window.loggedInUser) {
                showNotification('로그인이 필요한 서비스입니다.', 'info');
                controlModal('loginModal', true);
            } else {
                showPage(pageId);
            }
        }
        
        if (modalLink) {
            e.preventDefault();
            controlModal(modalLink.dataset.modal, true);
        }
        if (closeModalBtn) {
            controlModal(closeModalBtn.closest('.modal').id, false);
        }
        if (target.closest('#logoutBtn')) {
            e.preventDefault();
            logoutUser();
        }
        if (target.closest('#analyzeBtn')) {
            startAnalysis();
        }
        if (target.closest('#goToMakeoverBtn')) {
            goToMakeover();
        }
        if (target.closest('.upload-area-file')) {
            document.getElementById('fileInput').click();
        }
        if (target.closest('.upload-area-webcam')) {
            openWebcam();
        }
        if (target.closest('#webcamModal .cta-button')) {
            takeSnapshot();
        }
    });

    // 양식 제출
    document.getElementById('loginForm')?.addEventListener('submit', e => { e.preventDefault(); loginUser(); });
    document.getElementById('signupForm')?.addEventListener('submit', e => { e.preventDefault(); signupUser(); });
    
    // 파일 입력
    document.getElementById('fileInput')?.addEventListener('change', handleFileSelect);
    
    // 드래그 앤 드롭
    const uploadSection = document.querySelector('.upload-section');
    if(uploadSection) {
        uploadSection.addEventListener('dragover', e => { e.preventDefault(); e.stopPropagation(); e.currentTarget.classList.add('dragover'); });
        uploadSection.addEventListener('dragleave', e => { e.preventDefault(); e.stopPropagation(); e.currentTarget.classList.remove('dragover'); });
        uploadSection.addEventListener('drop', e => {
            e.preventDefault();
            e.stopPropagation();
            e.currentTarget.classList.remove('dragover');
            if (e.dataTransfer.files.length > 0) {
                displayAndSetFile(e.dataTransfer.files[0]);
            }
        });
    }
});