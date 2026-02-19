"""
신고서 생성 모듈 (PDF 출력)
- 공정거래위원회 별지 제6호 서식 기반 PDF 생성
- HWP 양식과 일치하는 테이블 레이아웃
"""
from fpdf import FPDF
import os
from datetime import datetime
import tempfile
from typing import Dict, List, Optional


class KoreanPDF(FPDF):
    """한국어 지원 PDF 클래스"""
    
    def __init__(self):
        super().__init__()
        self.font_path = self._find_korean_font()
        if self.font_path:
            self.add_font('Korean', '', self.font_path)
        self.set_auto_page_break(auto=False)  # 수동 페이지 제어
    
    def _find_korean_font(self) -> Optional[str]:
        """시스템에서 한국어 폰트 찾기"""
        # Streamlit Cloud 경로
        noto_paths = [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttf',
        ]
        
        # macOS 경로
        macos_paths = [
            '/System/Library/Fonts/Supplemental/AppleGothic.ttf',
            '/Library/Fonts/NanumGothic.ttf',
        ]
        
        for path in noto_paths + macos_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def set_korean_font(self, size=10):
        """한국어 폰트 설정"""
        if self.font_path:
            self.set_font('Korean', size=size)
        else:
            self.set_font('Arial', size=size)  # Fallback
    
    def korean_text(self, x, y, text, size=10, align='L'):
        """한국어 텍스트 출력"""
        self.set_xy(x, y)
        self.set_korean_font(size)
        if align == 'C':
            self.cell(0, 5, text, align='C')
        else:
            self.cell(0, 5, text)
    
    def draw_table_border(self, x, y, w, h):
        """테이블 테두리 그리기"""
        self.rect(x, y, w, h)
    
    def draw_cell(self, x, y, w, h, text='', size=9, align='L', border=True):
        """셀 그리기"""
        if border:
            self.rect(x, y, w, h)
        if text:
            # 텍스트 위치 조정 (셀 중앙에 배치)
            text_y = y + (h / 2) - 1
            self.set_xy(x + 1, text_y)
            self.set_korean_font(size)
            self.cell(w - 2, 4, text, align=align)


def generate_report(data: dict, save_path: str) -> str:
    """
    HWP 별지 제6호 서식 기반 PDF 신고서 생성
    
    data 구조:
    {
        'reporter': {
            'name': '홍길동',
            'birth_date': '1990-01-01', 
            'address': '서울시 강남구...',
            'phone': '010-1234-5678',
            'mobile': '010-1234-5678',
            'fax': '',
            'email': 'hong@email.com',
            'relationship': '소비자'  # 소비자/행정기관/사회단체/경쟁사업자/구성사업자/기타
        },
        'respondent': {
            'business_name': '○○컴퍼니',
            'representative': '김○○',
            'address_phone': '서울시 서초구... (또는 전화번호)',
            'department': '마케팅팀 홍길동'
        },
        'report_content': {
            'media': '인스타그램',
            'date': '2024-02-19',
            'content': '광고 내용 설명...',
            'violation_reason': '경제적 이해관계 미표시로...'
        },
        'checklist': {
            'false_exaggerated': False,  # 1-① 거짓·과장
            'deceptive': False,         # 1-② 기만적  
            'unfair_comparison': False, # 1-③ 부당비교
            'defamatory': False,        # 1-④ 비방적
            'missing_info': True,       # 2 중요정보미고시
            'association_restriction': False,  # 3 사업자단체제한
            'other': False              # 4 기타
        },
        'attachment_desc': '스크린샷 등',
        'identity_disclosure': '비공개',  # 공개/비공개/사건 조치 후 공개
        'evidence': {
            'screenshot_path': '/path/to/screenshot.png',
            'extra_screenshots': ['/path/to/extra1.png'],
            'additional_notes': '추가 설명...'
        }
    }
    """
    pdf = KoreanPDF()
    
    # 페이지 1: 메인 신고서
    _generate_main_report_page(pdf, data)
    
    # 페이지 2: 첨부1 - 사전점검표
    _generate_checklist_page(pdf, data)
    
    # 페이지 3: 첨부2 - 추가 작성 양식
    _generate_additional_page(pdf, data)
    
    # 페이지 4+: 증거 스크린샷
    _add_evidence_pages(pdf, data)
    
    # PDF 저장
    pdf.output(save_path)
    return save_path


def _generate_main_report_page(pdf: KoreanPDF, data: dict):
    """페이지 1: 메인 신고서"""
    pdf.add_page()
    
    # 헤더
    pdf.korean_text(20, 20, "■ 공정거래위원회의 회의운영 및 사건절차 등에 관한 규칙 [별지 제6호 서식]", 10)
    
    # 제목
    pdf.korean_text(70, 35, "표시ㆍ광고의 공정화에 관한 법률 위반행위 신고서", 14, 'C')
    
    # 안내문
    pdf.korean_text(20, 50, "※ (*) 표시항목은 필수사항이니 반드시 기재하여 주시고, 나머지 사항은 효율적인 심사를 위하여", 8)
    pdf.korean_text(25, 55, "가능한 한 기재해 주시기 바랍니다.", 8)
    
    # 메인 테이블
    table_start_y = 65
    _draw_main_table(pdf, data, table_start_y)
    
    # 풋터 (법률 조항)
    footer_y = 240
    pdf.korean_text(20, footer_y, "「표시·광고의 공정화에 관한 법률」 제16조제2항 및 「공정거래위원회 회의 운영 및", 9)
    pdf.korean_text(20, footer_y + 4, "사건절차 등에 관한 규칙」 제10조제2항에 의하여 위와 같이 신고합니다.", 9)
    
    # 날짜 및 서명
    today = datetime.now().strftime("%Y년  %m월  %d일")
    pdf.korean_text(150, footer_y + 15, today, 10)
    pdf.korean_text(120, footer_y + 25, "신 고 인 :                  (서명 또는 인)", 10)
    pdf.korean_text(20, footer_y + 35, "공정거래위원회위원장 귀하", 10)


def _draw_main_table(pdf: KoreanPDF, data: dict, start_y: float):
    """메인 테이블 그리기"""
    x = 20
    y = start_y
    table_width = 170
    
    reporter = data.get('reporter', {})
    respondent = data.get('respondent', {})
    content = data.get('report_content', {})
    
    # 신고인 섹션 (5행)
    row_heights = [8, 8, 8, 8, 8]  # 각 행 높이
    
    # 신고인 라벨 (세로 병합)
    total_reporter_height = sum(row_heights)
    pdf.draw_cell(x, y, 15, total_reporter_height, "신\n고\n인", 10, 'C')
    
    # 1행: 성명 | 생년월일
    curr_y = y
    pdf.draw_cell(x + 15, curr_y, 25, row_heights[0], "성명(*)", 9)
    pdf.draw_cell(x + 40, curr_y, 70, row_heights[0], reporter.get('name', ''), 9)
    pdf.draw_cell(x + 110, curr_y, 25, row_heights[0], "생년월일(*)", 9)
    pdf.draw_cell(x + 135, curr_y, 35, row_heights[0], reporter.get('birth_date', ''), 9)
    
    # 2행: 주소
    curr_y += row_heights[0]
    pdf.draw_cell(x + 15, curr_y, 25, row_heights[1], "주소(*)", 9)
    pdf.draw_cell(x + 40, curr_y, 130, row_heights[1], reporter.get('address', ''), 9)
    
    # 3행: 전화번호 | 휴대폰
    curr_y += row_heights[1]
    pdf.draw_cell(x + 15, curr_y, 25, row_heights[2] + row_heights[3], "연락처", 9, 'C')
    pdf.draw_cell(x + 40, curr_y, 25, row_heights[2], "전화번호(*)", 9)
    pdf.draw_cell(x + 65, curr_y, 45, row_heights[2], reporter.get('phone', ''), 9)
    pdf.draw_cell(x + 110, curr_y, 25, row_heights[2], "휴대폰", 9)
    pdf.draw_cell(x + 135, curr_y, 35, row_heights[2], reporter.get('mobile', ''), 9)
    
    # 4행: 팩스번호 | 이메일
    curr_y += row_heights[2]
    pdf.draw_cell(x + 40, curr_y, 25, row_heights[3], "팩스번호", 9)
    pdf.draw_cell(x + 65, curr_y, 45, row_heights[3], reporter.get('fax', ''), 9)
    pdf.draw_cell(x + 110, curr_y, 25, row_heights[3], "이메일", 9)
    pdf.draw_cell(x + 135, curr_y, 35, row_heights[3], reporter.get('email', ''), 9)
    
    # 5행: 피신고인과의 관계
    curr_y += row_heights[3]
    pdf.draw_cell(x + 15, curr_y, 25, row_heights[4], "피신고인과의 관계", 9)
    relationship_text = _get_relationship_checkboxes(reporter.get('relationship', ''))
    pdf.draw_cell(x + 40, curr_y, 130, row_heights[4], relationship_text, 8)
    
    # 피신고인 섹션 (3행)
    curr_y += row_heights[4] + 2
    respondent_heights = [8, 8, 8]
    total_resp_height = sum(respondent_heights)
    
    pdf.draw_cell(x, curr_y, 15, total_resp_height, "피\n신\n고\n인", 10, 'C')
    
    # 1행: 사업자명 | 대표자 성명
    pdf.draw_cell(x + 15, curr_y, 25, respondent_heights[0], "사업자명(*)", 9)
    pdf.draw_cell(x + 40, curr_y, 70, respondent_heights[0], respondent.get('business_name', ''), 9)
    pdf.draw_cell(x + 110, curr_y, 25, respondent_heights[0], "대표자 성명", 9)
    pdf.draw_cell(x + 135, curr_y, 35, respondent_heights[0], respondent.get('representative', ''), 9)
    
    # 2행: 주소 또는 전화번호
    curr_y += respondent_heights[0]
    pdf.draw_cell(x + 15, curr_y, 25, respondent_heights[1] + respondent_heights[2], "주소 또는\n전화번호(*)", 9)
    pdf.draw_cell(x + 40, curr_y, 130, respondent_heights[1], respondent.get('address_phone', ''), 9)
    
    # 3행: 관련부서 및 담당자
    curr_y += respondent_heights[1]
    pdf.draw_cell(x + 110, curr_y, 25, respondent_heights[2], "관련부서 및 담당자", 8)
    pdf.draw_cell(x + 135, curr_y, 35, respondent_heights[2], respondent.get('department', ''), 9)
    
    # 신고내용 섹션 (3행)
    curr_y += respondent_heights[2] + 2
    content_heights = [10, 35, 50]
    total_content_height = sum(content_heights)
    
    pdf.draw_cell(x, curr_y, 15, total_content_height, "신\n고\n내\n용", 10, 'C')
    
    # 1행: 표시·광고 매체 | 표시·광고 일자
    pdf.draw_cell(x + 15, curr_y, 25, content_heights[0], "표시·광고\n매체(*)", 9)
    pdf.draw_cell(x + 40, curr_y, 70, content_heights[0], content.get('media', ''), 9)
    pdf.draw_cell(x + 110, curr_y, 25, content_heights[0], "표시·광고\n일자(*)", 9)
    pdf.draw_cell(x + 135, curr_y, 35, content_heights[0], content.get('date', ''), 9)
    
    # 2행: 표시·광고의 내용
    curr_y += content_heights[0]
    pdf.draw_cell(x + 15, curr_y, 25, content_heights[1], "표시·광고의\n내용(*)", 9)
    _draw_multiline_text(pdf, x + 40, curr_y, 130, content_heights[1], content.get('content', ''), 9)
    
    # 3행: 위법하다고 주장하는 이유
    curr_y += content_heights[1]
    pdf.draw_cell(x + 15, curr_y, 25, content_heights[2], "표시·광고가\n위법하다고\n주장하는 이유(*)", 9)
    _draw_multiline_text(pdf, x + 40, curr_y, 130, content_heights[2], content.get('violation_reason', ''), 9)
    
    # 첨부자료 및 신분공개
    curr_y += content_heights[2] + 2
    attachment = data.get('attachment_desc', '신고 대상 표시·광고물 또는 그 사본(*)')
    pdf.draw_cell(x, curr_y, 15, 10, "첨부\n자료", 10, 'C')
    pdf.draw_cell(x + 15, curr_y, 155, 10, attachment, 9)
    
    curr_y += 12
    identity_text = _get_identity_checkboxes(data.get('identity_disclosure', '비공개'))
    pdf.draw_cell(x, curr_y, 15, 15, "신고인\n신분공개\n동의여부", 9, 'C')
    pdf.draw_cell(x + 15, curr_y, 155, 15, identity_text, 9)


def _get_relationship_checkboxes(relationship: str) -> str:
    """피신고인과의 관계 체크박스 텍스트 생성"""
    relationships = ['소비자', '행정기관', '사회단체', '경쟁사업자', '구성사업자', '기타']
    result = []
    
    for rel in relationships[:3]:  # 첫 줄
        check = '☑' if rel == relationship else '☐'
        result.append(f"{check} {rel}")
    
    result.append('\n')
    
    for rel in relationships[3:]:  # 둘째 줄
        check = '☑' if rel == relationship else '☐'
        if rel == '기타':
            other_text = relationship if relationship not in relationships[:-1] else ''
            result.append(f"{check} {rel}({other_text})")
        else:
            result.append(f"{check} {rel}")
    
    return '  '.join(result)


def _get_identity_checkboxes(disclosure: str) -> str:
    """신분공개 동의여부 체크박스 텍스트 생성"""
    options = {'공개': '☑ 공개', '비공개': '☑ 비공개', '사건 조치 후 공개': '☑ 사건 조치 후 공개'}
    default = {'공개': '☐ 공개', '비공개': '☐ 비공개', '사건 조치 후 공개': '☐ 사건 조치 후 공개'}
    
    result = []
    for key in ['공개', '비공개', '사건 조치 후 공개']:
        result.append(options.get(key) if key == disclosure else default[key])
    
    return '\n'.join(result)


def _draw_multiline_text(pdf: KoreanPDF, x: float, y: float, w: float, h: float, text: str, size: int):
    """멀티라인 텍스트를 셀에 그리기"""
    pdf.rect(x, y, w, h)
    if not text:
        return
    
    # 텍스트를 줄바꿈하여 셀 내부에 배치
    pdf.set_xy(x + 1, y + 1)
    pdf.set_korean_font(size)
    
    # 간단한 줄바꿈 (실제로는 더 정교한 처리 필요)
    lines = text.split('\n')
    line_height = 4
    for i, line in enumerate(lines):
        if y + 1 + (i * line_height) + line_height > y + h:
            break  # 셀 높이 초과시 중단
        pdf.set_xy(x + 1, y + 1 + (i * line_height))
        # 긴 줄은 자동 줄바꿈 (간단 구현)
        if pdf.get_string_width(line) > w - 2:
            line = line[:50] + '...'
        pdf.cell(w - 2, line_height, line)


def _generate_checklist_page(pdf: KoreanPDF, data: dict):
    """페이지 2: 첨부1 - 신고서 작성 안내 및 위반행위 사전점검표"""
    pdf.add_page()
    
    # 제목
    pdf.korean_text(70, 20, "<첨부 1 : 신고서 작성 안내 및 위반행위 사전점검표>", 12, 'C')
    
    # 간략한 안내 (실제 HWP에는 더 많은 내용이 있지만 핵심만)
    pdf.korean_text(20, 40, "◆ 위반행위 사전점검표", 11)
    
    # 체크리스트 테이블
    checklist = data.get('checklist', {})
    _draw_checklist_table(pdf, checklist, 55)


def _draw_checklist_table(pdf: KoreanPDF, checklist: dict, start_y: float):
    """위반행위 사전점검표 테이블"""
    x = 20
    y = start_y
    
    # 헤더
    pdf.draw_cell(x, y, 15, 8, "연번", 10, 'C')
    pdf.draw_cell(x + 15, y, 40, 8, "관련 법 조항", 10, 'C')
    pdf.draw_cell(x + 55, y, 80, 8, "위반 사실", 10, 'C')
    pdf.draw_cell(x + 135, y, 25, 8, "해당 여부", 10, 'C')
    
    y += 8
    
    # 1-① 거짓·과장
    check1_1 = '☑' if checklist.get('false_exaggerated') else '☐'
    pdf.draw_cell(x, y, 15, 25, "1", 10, 'C')
    pdf.draw_cell(x + 15, y, 40, 25, "제3조\n(부당한 표시ㆍ광고\n행위의 금지)", 9, 'C')
    pdf.draw_cell(x + 55, y, 80, 25, "사실과 다르게 표시ㆍ광고하거나 사실을 지나치게\n부풀려 거짓ㆍ과장의 표시ㆍ광고 행위", 8)
    pdf.draw_cell(x + 135, y, 25, 25, f"1-① ({check1_1})", 9, 'C')
    
    # 추가 체크리스트 항목들도 비슷하게 구현 (간략화)
    y += 25
    check1_2 = '☑' if checklist.get('deceptive') else '☐'
    pdf.draw_cell(x + 55, y, 80, 15, "기만적인 표시ㆍ광고 행위", 8)
    pdf.draw_cell(x + 135, y, 25, 15, f"1-② ({check1_2})", 9, 'C')
    
    y += 15  
    check2 = '☑' if checklist.get('missing_info') else '☐'
    pdf.draw_cell(x, y, 15, 15, "2", 10, 'C')
    pdf.draw_cell(x + 15, y, 40, 15, "제4조\n(중요정보의 고시)", 9, 'C')
    pdf.draw_cell(x + 55, y, 80, 15, "중요정보를 표시ㆍ광고하지 아니한 경우", 8)
    pdf.draw_cell(x + 135, y, 25, 15, f"2 ({check2})", 9, 'C')


def _generate_additional_page(pdf: KoreanPDF, data: dict):
    """페이지 3: 첨부2 - 신고내용 추가 작성 양식"""
    pdf.add_page()
    
    # 제목
    pdf.korean_text(70, 20, "<첨부 2 : 신고내용 추가 작성 양식>", 12, 'C')
    
    # 테이블
    x = 20
    y = 40
    
    # 위반사실 해당여부
    pdf.draw_cell(x, y, 80, 10, "위반사실 해당여부 (사전점검표에 체크한 번호)", 9)
    pdf.draw_cell(x + 80, y, 80, 10, "예) 1-①", 9)
    
    y += 10
    
    # 신고내용 (대형 영역)
    pdf.draw_cell(x, y, 30, 120, "신고내용", 10, 'C')
    additional_content = data.get('evidence', {}).get('additional_notes', '')
    _draw_multiline_text(pdf, x + 30, y, 130, 120, additional_content, 9)
    
    y += 120
    
    # 증거자료
    pdf.draw_cell(x, y, 30, 30, "증거자료", 10, 'C')
    evidence_list = _get_evidence_list(data)
    _draw_multiline_text(pdf, x + 30, y, 130, 30, evidence_list, 9)


def _get_evidence_list(data: dict) -> str:
    """증거자료 목록 생성"""
    evidence = data.get('evidence', {})
    items = []
    
    if evidence.get('screenshot_path'):
        items.append('자료 1번: 메인 스크린샷')
    
    extra_shots = evidence.get('extra_screenshots', [])
    for i, _ in enumerate(extra_shots):
        items.append(f'자료 {i+2}번: 추가 스크린샷 {i+1}')
    
    if not items:
        items.append('스크린샷 자료 (별도 첨부)')
    
    return '\n'.join(items)


def _add_evidence_pages(pdf: KoreanPDF, data: dict):
    """페이지 4+: 증거 스크린샷 이미지"""
    evidence = data.get('evidence', {})
    all_screenshots = []
    
    # 메인 스크린샷
    if evidence.get('screenshot_path') and os.path.exists(evidence['screenshot_path']):
        all_screenshots.append(evidence['screenshot_path'])
    
    # 추가 스크린샷들
    for extra in evidence.get('extra_screenshots', []):
        if os.path.exists(extra):
            all_screenshots.append(extra)
    
    # 각 스크린샷을 페이지로 추가
    for i, screenshot_path in enumerate(all_screenshots):
        pdf.add_page()
        
        # 페이지 제목
        pdf.korean_text(20, 20, f"증거자료 {i+1}번: 스크린샷", 12)
        
        try:
            # 이미지 추가 (fpdf2의 이미지 지원 활용)
            # 페이지 크기에 맞게 조정
            img_width = 170
            img_height = 200  # 적절한 높이
            pdf.image(screenshot_path, x=20, y=40, w=img_width, h=img_height)
            
            # 캡처 시간 표시
            captured_at = evidence.get('captured_at', '')
            if captured_at:
                pdf.korean_text(20, 245, f"캡처 시각: {captured_at}", 9)
            
        except Exception as e:
            # 이미지 로드 실패시 텍스트로 표시
            pdf.korean_text(20, 100, f"이미지 로드 실패: {str(e)}", 10)
            pdf.korean_text(20, 110, f"파일 경로: {screenshot_path}", 9)