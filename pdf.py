import os
import json
from fpdf import FPDF
from PIL import Image

class PDF(FPDF):
    def header(self):
        # Set full page background color
        self.set_fill_color(255, 221, 238) # A pleasant, not too dark pink
        self.rect(0, 0, self.w, self.h, 'F')

        # Draw a white content area card on top
        margin = 8
        self.set_fill_color(255, 255, 255)
        self.rect(margin, margin, self.w - 2 * margin, self.h - 2 * margin, 'F')

        # Set font for the header title
        try:
            self.add_font('NanumGothic', '', 'static/fonts/NanumGothic-Regular.ttf', uni=True)
            self.add_font('NanumGothic', 'B', 'static/fonts/NanumGothic-ExtraBold.ttf', uni=True)
            self.set_font('NanumGothic', 'B', 18)
        except RuntimeError:
            self.set_font('Arial', 'B', 15)
        
        # Page Title
        self.set_y(15)
        self.set_text_color(224, 82, 123)
        self.cell(0, 10, '🎨 AI Personal Color Report 🌈', 0, 1, 'C')
        self.set_text_color(0, 0, 0)
        self.set_y(30) # Set cursor for content

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(180, 180, 180)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def section_title(self, title):
        self.set_font('NanumGothic', 'B', 14)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, title, 0, 1, 'L')
        self.set_draw_color(255, 221, 230)
        self.set_line_width(0.5)
        self.line(self.get_x(), self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def section_body(self, body):
        self.set_font('NanumGothic', '', 10)
        self.set_text_color(80, 80, 80)
        self.multi_cell(0, 6, body)
        self.ln(5)

    def makeup_description(self, text):
        self.ln(5)
        self.set_font('NanumGothic', 'B', 11)
        self.set_text_color(120, 120, 120)
        self.set_x(self.l_margin + 10)
        self.multi_cell(self.w - (self.l_margin + 10) * 2, 7, text, 0, 'C')
        self.ln(5)

    def color_palette(self, title, palette):
        self.set_font('NanumGothic', 'B', 11)
        self.set_text_color(50, 50, 50)
        self.cell(0, 8, title, 0, 1)
        self.ln(1)

        x_start = self.get_x()
        y_start = self.get_y()
        box_size = 10
        spacing = box_size + 2
        max_colors_per_row = 11
        
        for i, color_hex in enumerate(palette):
            if i > 0 and i % max_colors_per_row == 0:
                self.set_y(self.get_y() + spacing)
                self.set_x(x_start)

            r, g, b = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            self.set_fill_color(r, g, b)
            self.set_draw_color(255, 255, 255)
            self.set_line_width(0.5)
            self.rect(self.get_x(), self.get_y(), box_size, box_size, 'FD')
            self.set_x(self.get_x() + spacing)

        self.set_y(self.get_y() + box_size + 8)

def generate_report_pdf(original_image_path, result_image_path, cluster, CLUSTER_DESCRIPTIONS, output_folder="."):
    if isinstance(cluster, int):
        cluster_info = CLUSTER_DESCRIPTIONS[cluster]
    else:
        cluster_info = cluster

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- PAGE 1: VIRTUAL STYLING ---
    pdf.add_page()
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_y(35) # Start content below header

    pdf.section_title("🖼️ Virtual Styling Results")
    
    max_height = 100
    try:
        img_orig = Image.open(original_image_path)
        img_result = Image.open(result_image_path)
        
        orig_w, orig_h = img_orig.size
        new_orig_h = max_height
        new_orig_w = orig_w * new_orig_h / orig_h

        res_w, res_h = img_result.size
        new_res_h = max_height
        new_res_w = res_w * new_res_h / res_h

        gap = 10
        total_width = new_orig_w + new_res_w + gap
        x_start = (pdf.w - total_width) / 2
        y_start = pdf.get_y() + 5

        pdf.image(original_image_path, x=x_start, y=y_start, h=new_orig_h)
        pdf.image(result_image_path, x=x_start + new_orig_w + gap, y=y_start, h=new_res_h)
        pdf.set_y(y_start + max_height + 10)
    except Exception as e:
        pdf.section_body(f"이미지 로딩 오류: {e}")

    pdf.set_x(15)
    pdf.makeup_description(f"AI가 당신의 퍼스널 컬러인 '{cluster_info['visual_name']}'에 맞춰 메이크업을 적용했습니다. "
                         "추천된 렌즈, 립, 헤어 컬러가 당신의 매력을 어떻게 극대화하는지 확인해보세요.")

    # --- PAGE 2: COLOR PALETTES ---
    pdf.add_page()
    pdf.set_left_margin(15)
    pdf.set_right_margin(15)
    pdf.set_y(35)

    pdf.section_title(f"🎨 Your Perfect Color Palettes: {cluster_info['visual_name']}")
    pdf.section_body(cluster_info.get("description", ""))

    with open('static/data/colors.json', 'r', encoding='utf-8') as f:
        colors_data = json.load(f)

    CLUSTER_KEY_MAP = {
        "골든 타입": "Golden", "웜 베이지 타입": "Warm Beige", "뮤트 클레이 타입": "Muted Clay",
        "웜 애프리콧 타입": "Warm Apricot", "피치 핑크 타입": "Peachy Pink", "허니 버프 타입": "Honey Buff",
        "베이지 로즈 타입": "Beige Rose", "쿨 로즈 타입": "Cool Rose"
    }
    cluster_name = cluster_info.get("visual_name")
    cluster_key = CLUSTER_KEY_MAP.get(cluster_name, cluster_name)

    if cluster_key in colors_data:
        palette_order = ['preview', 'lens', 'lipstick', 'hair', 'clothing']
        title_map = {
            'preview': '✨ Preview Colors',
            'lens': '👀 Lens Colors',
            'lipstick': '💄 Lipstick Colors',
            'hair': '💇‍♀️ Hair Colors',
            'clothing': '👗 Clothing Colors'
        }
        for category in palette_order:
            if category in colors_data[cluster_key]:
                pdf.color_palette(title_map[category], colors_data[cluster_key][category])
    else:
        if 'palette' in cluster_info:
             pdf.color_palette('🌈 Recommended Colors', cluster_info['palette'])
        else:
             pdf.section_body(f"⚠️ {cluster_name}에 대한 팔레트 데이터를 찾을 수 없습니다.")
    
    pdf.ln(10)
    pdf.section_title("💡 Styling Tip")
    styling_tips = {
        "Golden": "골드 주얼리와 따뜻한 색감의 의상으로 화사함을 더해보세요. 오렌지 레드 립은 당신의 생기를 극대화할 것입니다.",
        "Warm Beige": "차분한 뉴트럴 톤의 의상과 음영 메이크업이 잘 어울립니다. 매트한 립 표현으로 고급스러움을 연출해보세요.",
        "Muted Clay": "톤 다운된 얼씨(Earthy) 컬러와 자연스러운 메이크업이 베스트입니다. 과한 광택보다는 세미매트한 피부 표현이 좋습니다.",
        "Warm Apricot": "코랄, 살구 등 과즙미 넘치는 색상을 활용해 보세요. 쉬머한 펄이 있는 아이섀도우로 사랑스러움을 강조할 수 있습니다.",
        "Peachy Pink": "밝은 핑크와 피치 컬러로 로맨틱한 분위기를 연출하세요. 글로시한 립과 촉촉한 피부 표현이 잘 어울립니다.",
        "Honey Buff": "깊이감 있는 브라운, 카키, 버건디 컬러로 세련미를 더하세요. 골드 브라운 스모키 메이크업도 멋지게 소화할 수 있습니다.",
        "Beige Rose": "부드러운 로즈, 라벤더, 그레이시 톤으로 우아함을 표현하세요. 은은한 펄감과 MLBB 립 컬러를 추천합니다.",
        "Cool Rose": "푸른 기가 도는 핑크, 버건디, 플럼 컬러가 당신의 피부를 더욱 맑아 보이게 합니다. 실버 주얼리로 포인트를 주세요."
    }
    pdf.section_body(styling_tips.get(cluster_key, "자신에게 가장 잘 어울리는 스타일을 찾아보세요!"))

    pdf_file_path = os.path.join(output_folder, f"report_{os.path.basename(original_image_path)}.pdf")
    pdf.output(pdf_file_path)
    return pdf_file_path