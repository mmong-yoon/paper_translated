import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from PIL import Image
import pypandoc
import logging
from pathlib import Path
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HTMLToLaTeXConverter:
    """향상된 HTML to LaTeX 변환기"""
    
    def __init__(self, output_dir='training_output'):
        self.output_dir = output_dir
        self.image_dir = os.path.join(output_dir, 'images')
        self.image_map = {}  # 원본 URL과 로컬 파일 매핑
        self.ensure_pandoc_installed()
        
    def ensure_pandoc_installed(self):
        """Pandoc 설치 확인 및 자동 설치"""
        try:
            pypandoc.get_pandoc_version()
            logger.info("Pandoc이 이미 설치되어 있습니다.")
        except OSError:
            logger.info("Pandoc이 없습니다. 자동으로 다운로드합니다...")
            pypandoc.download_pandoc()
            logger.info("Pandoc 다운로드 완료!")
    
    def download_webpage(self, url):
        """웹페이지와 모든 리소스 다운로드"""
        logger.info(f"웹페이지 다운로드 시작: {url}")
        
        # 디렉토리 생성
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        
        # HTML 다운로드
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"웹페이지 다운로드 실패: {e}")
            raise
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # base URL 설정
        base_tag = soup.find('base')
        base_url = base_tag.get('href', url) if base_tag else url
        
        # 이미지 다운로드
        self._download_images(soup, base_url, headers)
        
        # CSS에서 background-image 추출
        self._extract_css_images(soup, base_url, headers)
        
        # 수정된 HTML 저장
        with open(os.path.join(self.output_dir, 'index.html'), 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify()))
        
        logger.info(f"다운로드 완료: {len(self.image_map)}개의 이미지")
        return soup
    
    def _download_images(self, soup, base_url, headers):
        """모든 이미지 태그 처리"""
        img_count = 0
        
        for img in soup.find_all('img'):
            # 다양한 이미지 소스 확인
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            
            if not img_url:
                continue
            
            # 절대 URL로 변환
            img_url = urljoin(base_url, img_url)
            
            # 이미 다운로드한 이미지인지 확인
            if img_url in self.image_map:
                img['src'] = self.image_map[img_url]
                continue
            
            # 파일명 생성
            local_filename = self._generate_filename(img_url, img_count)
            local_path = os.path.join('images', local_filename)
            full_path = os.path.join(self.image_dir, local_filename)
            
            # 이미지 다운로드
            if self._download_image(img_url, full_path, headers):
                img['src'] = local_path
                self.image_map[img_url] = local_path
                img_count += 1
                
                # data-src 등 제거
                for attr in ['data-src', 'data-lazy-src', 'srcset']:
                    if img.has_attr(attr):
                        del img[attr]
    
    def _extract_css_images(self, soup, base_url, headers):
        """CSS에서 background-image 추출 및 다운로드"""
        style_pattern = re.compile(r'url\([\'"]?([^\'"]+)[\'"]?\)')
        
        # 인라인 스타일에서 이미지 추출
        for element in soup.find_all(style=True):
            style = element.get('style', '')
            for match in style_pattern.finditer(style):
                img_url = urljoin(base_url, match.group(1))
                if img_url not in self.image_map:
                    local_filename = self._generate_filename(img_url, len(self.image_map))
                    local_path = os.path.join('images', local_filename)
                    full_path = os.path.join(self.image_dir, local_filename)
                    
                    if self._download_image(img_url, full_path, headers):
                        self.image_map[img_url] = local_path
    
    def _download_image(self, url, filepath, headers):
        """개별 이미지 다운로드"""
        try:
            response = requests.get(url, headers=headers, timeout=10, stream=True)
            response.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"이미지 다운로드 성공: {os.path.basename(filepath)}")
            return True
            
        except Exception as e:
            logger.warning(f"이미지 다운로드 실패: {url} - {str(e)}")
            return False
    
    def _generate_filename(self, url, counter):
        """안전한 파일명 생성"""
        parsed = urlparse(url)
        filename = os.path.basename(parsed.path)
        
        # 파일명이 없거나 너무 긴 경우
        if not filename or len(filename) > 50:
            filename = f"image_{counter:04d}"
        
        # 확장자 확인 및 추가
        name, ext = os.path.splitext(filename)
        if not ext or ext.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']:
            ext = '.png'
        
        # 특수문자 제거
        safe_name = re.sub(r'[^\w\-_]', '_', name)
        return f"{safe_name}{ext}"
    
    def preprocess_html(self, soup):
        """HTML 전처리 및 정리"""
        logger.info("HTML 전처리 시작")
        
        # 불필요한 요소 제거
        remove_tags = ['script', 'style', 'meta', 'link', 'noscript', 'iframe', 'object', 'embed']
        for tag in remove_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # 빈 요소 제거
        for element in soup.find_all():
            if not element.get_text(strip=True) and element.name not in ['img', 'br', 'hr', 'input']:
                element.decompose()
        
        # 속성 정리 (필요한 것만 유지)
        keep_attrs = {
            'img': ['src', 'alt', 'title', 'width', 'height', 'style'],
            'a': ['href', 'title'],
            'table': ['border', 'cellpadding', 'cellspacing'],
            'td': ['colspan', 'rowspan'],
            'th': ['colspan', 'rowspan'],
            'code': ['class'],
            'pre': ['class'],
        }
        
        for tag in soup.find_all(True):
            if tag.name in keep_attrs:
                tag.attrs = {k: v for k, v in tag.attrs.items() if k in keep_attrs[tag.name]}
            else:
                # 기본적으로 style 속성만 유지
                tag.attrs = {k: v for k, v in tag.attrs.items() if k == 'style'}
        
        # 테이블 구조 개선
        for table in soup.find_all('table'):
            table['border'] = '1'
            # 빈 셀에 공백 추가
            for cell in table.find_all(['td', 'th']):
                if not cell.get_text(strip=True):
                    cell.string = ' '
        
        logger.info("HTML 전처리 완료")
        return soup
    
    def optimize_images(self):
        """모든 이미지 최적화 및 WebP 변환"""
        logger.info("이미지 최적화 시작")
        
        if not os.path.exists(self.image_dir):
            return
        
        converted_count = 0
        optimized_count = 0
        
        for filename in os.listdir(self.image_dir):
            filepath = os.path.join(self.image_dir, filename)
            
            if not os.path.isfile(filepath):
                continue
            
            try:
                # 이미지 열기
                img = Image.open(filepath)
                original_format = img.format
                
                # RGBA/P 모드를 RGB로 변환
                if img.mode in ('RGBA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode == 'CMYK':
                    img = img.convert('RGB')
                
                # 크기 조정
                max_width = 1200
                max_height = 1600
                
                if img.width > max_width or img.height > max_height:
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                    optimized_count += 1
                
                # WebP를 PNG로 변환
                if filename.lower().endswith('.webp') or original_format == 'WEBP':
                    new_filename = os.path.splitext(filename)[0] + '.png'
                    new_filepath = os.path.join(self.image_dir, new_filename)
                    img.save(new_filepath, 'PNG', optimize=True)
                    
                    # 원본 WebP 파일 삭제
                    if new_filepath != filepath:
                        os.remove(filepath)
                        converted_count += 1
                        
                        # image_map 업데이트
                        for url, path in self.image_map.items():
                            if path.endswith(filename):
                                self.image_map[url] = path.replace(filename, new_filename)
                else:
                    # 다른 포맷도 최적화하여 저장
                    img.save(filepath, img.format or 'PNG', optimize=True, quality=95)
                
                logger.info(f"이미지 처리 완료: {filename}")
                
            except Exception as e:
                logger.error(f"이미지 처리 실패: {filename} - {str(e)}")
        
        logger.info(f"이미지 최적화 완료: {converted_count}개 변환, {optimized_count}개 크기 조정")
    
    def html_to_latex_pandoc(self, output_filename):
        """Pandoc을 사용한 LaTeX 변환"""
        logger.info("Pandoc을 사용한 LaTeX 변환 시작")
        
        input_file = os.path.join(self.output_dir, 'index.html')
        output_file = os.path.join(self.output_dir, f"{output_filename}_pandoc.tex")
        
        # 사용자 정의 LaTeX 템플릿
        template_content = r'''
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{graphicx}
\usepackage{float}
\usepackage{hyperref}
\usepackage{longtable}
\usepackage{booktabs}
\usepackage{array}
\usepackage{multirow}
\usepackage{xcolor}
\usepackage{listings}
\usepackage{caption}
\usepackage[margin=1in]{geometry}

% 한글 지원 (필요시 주석 해제)
% \usepackage{kotex}

% 이미지 설정
\graphicspath{{./temp_output/}}
\DeclareGraphicsExtensions{.png,.jpg,.jpeg,.pdf}

% 하이퍼링크 설정
\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,
    urlcolor=cyan,
    pdftitle={$title$},
    pdfauthor={$author$},
    bookmarks=true
}

% 코드 하이라이팅 설정
\lstset{
    basicstyle=\small\ttfamily,
    breaklines=true,
    frame=single,
    numbers=left,
    numberstyle=\tiny\color{gray},
    keywordstyle=\color{blue},
    commentstyle=\color{green!60!black},
    stringstyle=\color{red},
    showstringspaces=false,
    tabsize=4
}

% float 설정
\floatplacement{figure}{H}
\floatplacement{table}{H}

\title{$title$}
\author{$author$}
\date{\today}

\begin{document}

\maketitle
\tableofcontents
\newpage

$body$

\end{document}
'''
        
        # 템플릿 파일 생성
        template_file = os.path.join(self.output_dir, 'template.tex')
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        try:
            # Pandoc 변환 옵션
            extra_args = [
                '--standalone',
                f'--template={template_file}',
                '--toc',
                '--toc-depth=3',
                '--highlight-style=pygments',
                '-V', 'title=Converted Document',
                '-V', 'author=HTML to LaTeX Converter',
                '-V', 'documentclass=article',
                '-V', 'fontsize=11pt',
                '-V', 'papersize=a4',
                '--listings',
                '--wrap=preserve',
                '--columns=80'
            ]
            
            # 변환 실행
            pypandoc.convert_file(
                input_file,
                'latex',
                outputfile=output_file,
                extra_args=extra_args
            )
            
            logger.info(f"Pandoc 변환 완료: {output_file}")
            
            # 후처리
            self._post_process_latex(output_file)
            
        finally:
            # 템플릿 파일 삭제
            if os.path.exists(template_file):
                os.remove(template_file)
        
        return output_file
    
    def _post_process_latex(self, latex_file):
        """생성된 LaTeX 파일 후처리"""
        logger.info("LaTeX 파일 후처리 시작")
        
        with open(latex_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # WebP 참조를 PNG로 변경
        content = re.sub(r'\.webp}', '.png}', content, flags=re.IGNORECASE)
        
        # 이미지 크기 조정
        # \includegraphics{...} -> \includegraphics[width=\textwidth,height=\textheight,keepaspectratio]{...}
        def replace_graphics(match):
            options = match.group(1) if match.group(1) else ''
            filename = match.group(2)
            
            # 이미 옵션이 있는 경우
            if options:
                if 'width' not in options and 'height' not in options:
                    options = f'width=\\textwidth,height=\\textheight,keepaspectratio,{options}'
            else:
                options = 'width=\\textwidth,height=\\textheight,keepaspectratio'
            
            return f'\\includegraphics[{options}]{{{filename}}}'
        
        content = re.sub(
            r'\\includegraphics(?:\[([^\]]*)\])?\{([^}]+)\}',
            replace_graphics,
            content
        )
        
        # 긴 URL 줄바꿈 처리
        content = re.sub(
            r'\\url\{([^}]{80,})\}',
            lambda m: r'\url{' + m.group(1)[:77] + '...}',
            content
        )
        
        # 테이블 개선
        content = re.sub(
            r'\\begin\{longtable\}\{@\{\}[lrc]+@\{\}\}',
            lambda m: m.group(0).replace('@{}', '|').replace('}', '|}'),
            content
        )
        
        # 수정된 내용 저장
        with open(latex_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info("LaTeX 파일 후처리 완료")
    
    def html_to_latex_custom(self, soup, output_filename):
        """커스텀 HTML to LaTeX 변환"""
        logger.info("커스텀 LaTeX 변환 시작")
        
        try:
            converter = CustomHTML2LaTeX(self.image_dir)
            latex_content = converter.convert(soup)
            
            output_file = os.path.join(self.output_dir, f"{output_filename}_custom.tex")
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            logger.info(f"커스텀 변환 완료: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"커스텀 변환 중 오류: {str(e)}")
            logger.error(f"오류 타입: {type(e)}")
            import traceback
            logger.error(f"스택 트레이스: {traceback.format_exc()}")
            raise
    
    def convert_webpage_to_latex(self, url, output_name, use_custom=False):
        """웹페이지를 LaTeX로 변환하는 메인 함수"""
        try:
            # 1. 웹페이지 다운로드
            soup = self.download_webpage(url)
            
            # 2. HTML 전처리
            soup = self.preprocess_html(soup)
            
            # 3. 이미지 최적화
            self.optimize_images()
            
            # 4. WebP 참조 업데이트
            self._update_webp_references(soup)
            
            # 업데이트된 HTML 저장
            with open(os.path.join(self.output_dir, 'index.html'), 'w', encoding='utf-8') as f:
                f.write(str(soup.prettify()))
            
            # 5. LaTeX 변환
            if use_custom:
                # 커스텀 변환기 사용
                return self.html_to_latex_custom(soup, output_name)
            else:
                # Pandoc 사용
                return self.html_to_latex_pandoc(output_name)
            
        except Exception as e:
            logger.error(f"변환 중 오류 발생: {str(e)}")
            raise
    
    def _update_webp_references(self, soup):
        """HTML 내의 WebP 참조를 PNG로 업데이트"""
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src.endswith('.webp'):
                img['src'] = src.replace('.webp', '.png')


class CustomHTML2LaTeX:
    """커스텀 HTML to LaTeX 변환기"""
    
    def __init__(self, image_dir):
        self.image_dir = image_dir
        self.image_cache = {}
        
        self.latex_header = r'''
\documentclass[11pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage{graphicx}
\usepackage{float}
\usepackage{hyperref}
\usepackage{longtable}
\usepackage{booktabs}
\usepackage{array}
\usepackage{xcolor}
\usepackage{listings}
\usepackage{caption}
\usepackage{subcaption}
\usepackage[margin=1in]{geometry}
\usepackage{newunicodechar}

% 유니코드 특수 문자 정의
\newunicodechar{∙}{\textbullet}
\newunicodechar{–}{--}
\newunicodechar{—}{---}
\newunicodechar{…}{\ldots}

% 한글 지원
% \usepackage{kotex}

% 이미지 경로
% \graphicspath{{./temp_output/images/}}

% Float 설정
\floatplacement{figure}{H}
\floatplacement{table}{H}

% 커버 페이지 스타일링
\usepackage{titling}
\renewcommand{\maketitlehooka}{\centering}
\renewcommand{\maketitlehookb}{\vfill}
\renewcommand{\maketitlehookc}{\vfill}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,
    urlcolor=cyan,
}

\title{\Huge\textbf{DOCUMENT_TITLE}}
\author{\Large HTML to LaTeX Converter}
\date{\large\today}

\begin{document}

% 커버 페이지
\begin{titlepage}
\centering
\vspace*{7cm}

{\Huge\textbf{DOCUMENT_TITLE}}

\vspace{4cm}

{\Huge\today}

\vfill


\end{titlepage}

% 목차 페이지
\tableofcontents
\newpage

'''
        self.latex_footer = r'\end{document}'
    
    def escape_latex(self, text):
        """LaTeX 특수 문자 이스케이프"""
        if not text:
            return ''
        
        text = str(text)
        
        # 한글 CJK 문자 제거 (LaTeX에서 문제가 되는 경우)
        import re
        # 한글, 한자, 일본어 문자를 공백으로 치환
        text = re.sub(r'[\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\uAC00-\uD7AF]', ' ', text)
        
        # 특수 문자 이스케이프
        replacements = [
            ('\\', '\\textbackslash{}'),
            ('{', '\\{'),
            ('}', '\\}'),
            ('$', '\\$'),
            ('&', '\\&'),
            ('#', '\\#'),
            ('^', '\\textasciicircum{}'),
            ('_', '\\_'),
            ('~', '\\textasciitilde{}'),
            ('%', '\\%'),
        ]
        
        for old, new in replacements:
            text = text.replace(old, new)
        
        # 여러 공백을 하나로
        try:
            text = re.sub(r'\s+', ' ', text)
        except Exception as e:
            print(f"정규식 오류 in escape_latex: {e}, text: {repr(text)}")
            # 정규식 실패 시 단순히 공백만 처리
            text = ' '.join(text.split())
        
        return text.strip()
    
    def convert_element(self, element, depth=0):
        """HTML 요소를 LaTeX로 변환"""
        # 무한 재귀 방지
        if depth > 20:
            return ''
            
        if not hasattr(element, 'name'):
            return self.escape_latex(str(element))
        
        # 제목 요소 - 섹션 번호를 1, 2, 3으로 하기 위해 h2를 section으로 변경
        if element.name == 'h1':
            return f'\n\\section{{{self.escape_latex(element.get_text())}}}\n'
        elif element.name == 'h2':
            return f'\n\\section{{{self.escape_latex(element.get_text())}}}\n'
        elif element.name == 'h3':
            return f'\n\\subsection{{{self.escape_latex(element.get_text())}}}\n'
        elif element.name == 'h4':
            return f'\n\\subsubsection{{{self.escape_latex(element.get_text())}}}\n'
        elif element.name == 'h5':
            return f'\n\\paragraph{{{self.escape_latex(element.get_text())}}}\n'
        
        # 단락
        elif element.name == 'p':
            content = self._process_inline_elements(element, depth + 1)
            return f'{content}\n\n' if content.strip() else ''
        
        # 이미지
        elif element.name == 'img':
            return self._convert_image(element)
        
        # Figure (이미지 + figcaption)
        elif element.name == 'figure':
            return self._convert_figure(element, depth + 1)
        
        # 리스트
        elif element.name == 'ul':
            return self._convert_list(element, 'itemize', depth + 1)
        elif element.name == 'ol':
            return self._convert_list(element, 'enumerate', depth + 1)
        
        # 테이블
        elif element.name == 'table':
            return self._convert_table(element)
        
        # 코드 블록
        elif element.name == 'pre':
            return self._convert_code_block(element)
        elif element.name == 'code':
            return f'\\texttt{{{self.escape_latex(element.get_text())}}}'
        
        # 인용
        elif element.name == 'blockquote':
            content = self._process_children(element, depth + 1)
            return f'\\begin{{quote}}\n{content}\n\\end{{quote}}\n'
        
        # 텍스트 서식
        elif element.name in ['strong', 'b']:
            return f'\\textbf{{{self.escape_latex(element.get_text())}}}'
        elif element.name in ['em', 'i']:
            return f'\\textit{{{self.escape_latex(element.get_text())}}}'
        elif element.name == 'u':
            return f'\\underline{{{self.escape_latex(element.get_text())}}}'
        
        # 링크
        elif element.name == 'a':
            # a 태그 안에 img가 있으면 자식을 처리
            if element.find('img'):
                return self._process_children(element, depth + 1)
            # 텍스트만 있는 경우
            href = element.get('href', '')
            text = element.get_text()
            if href and text:
                return f'\\href{{{href}}}{{{self.escape_latex(text)}}}'
            return self.escape_latex(text)
        
        # 줄바꿈
        elif element.name == 'br':
            return '\n\n'  # LaTeX에서 안전한 문단 구분으로 변경
        elif element.name == 'hr':
            return '\n\\hrule\n'
        
        # 컨테이너 요소
        elif element.name in ['div', 'section', 'article', 'main', 'header', 'footer', 'nav', 'aside', 'picture']:
            return self._process_children(element, depth + 1)
        
        # 정의 리스트
        elif element.name == 'dl':
            return self._convert_definition_list(element, depth + 1)
        
        # 기타
        else:
            # 자식 요소가 있으면 처리, 없으면 텍스트만 추출
            try:
                if element.find_all():
                    return self._process_children(element, depth + 1)
                else:
                    return self.escape_latex(element.get_text())
            except AttributeError:
                # NavigableString 등의 경우
                return self.escape_latex(str(element))
    
    def _process_inline_elements(self, element, depth=0):
        """인라인 요소 처리"""
        # 무한 재귀 방지
        if depth > 20:
            return ''
            
        result = []
        prev_was_element = False
        
        for child in element.children:
            if hasattr(child, 'name'):
                # 이전이 텍스트였고 현재가 요소(링크 등)인 경우 공백 추가
                converted = self.convert_element(child, depth + 1)
                if converted:
                    # 링크나 다른 인라인 요소 앞뒤에 공백이 필요한지 확인
                    if prev_was_element and result and not result[-1].endswith(' '):
                        result.append(' ')
                    result.append(converted)
                    prev_was_element = True
            else:
                # 텍스트 노드 처리
                text = str(child).strip()
                if text:
                    # 이전이 요소였고 현재가 텍스트인데 공백으로 시작하지 않으면 공백 추가
                    if prev_was_element and result and not text.startswith(' '):
                        result.append(' ')
                    result.append(self.escape_latex(text))
                    prev_was_element = False
                elif str(child).isspace():
                    # 공백 문자는 그대로 유지
                    result.append(' ')
                    prev_was_element = False
        
        return ''.join(result)
    
    def _process_children(self, element, depth=0):
        """자식 요소들 처리"""
        # 무한 재귀 방지
        if depth > 20:
            return ''
            
        result = []
        for child in element.children:
            if hasattr(child, 'name'):
                converted = self.convert_element(child, depth + 1)
                if converted:
                    result.append(converted)
        return ''.join(result)
    
    def _convert_figure(self, figure, depth=0):
        """Figure 요소 변환 (이미지 + figcaption)"""
        # 무한 재귀 방지
        if depth > 20:
            return ''
        
        img = figure.find('img')
        if not img:
            # img가 없으면 자식 요소만 처리
            return self._process_children(figure, depth + 1)
        
        src = img.get('src', '')
        if not src:
            return ''
        
        # WebP를 PNG로 변경
        if src.endswith('.webp'):
            src = src.replace('.webp', '.png')
        
        # 이미지 경로 처리
        if not src.startswith('images/') and not src.startswith('./'):
            src = f'images/{src}'
        
        # 크기 옵션
        width = img.get('width')
        height = img.get('height')
        style = img.get('style', '')
        
        # 스타일에서 크기 추출
        style_width = re.search(r'width:\s*(\d+)(?:px)?', style)
        style_height = re.search(r'height:\s*(\d+)(?:px)?', style)
        
        if style_width:
            width = style_width.group(1)
        if style_height:
            height = style_height.group(1)
        
        # LaTeX 옵션 생성
        options = []
        try:
            if width and int(width) > 600:
                options.append('width=\\textwidth')
            elif width and int(width) > 400:
                options.append('width=0.8\\textwidth')
            elif width and int(width) > 200:
                options.append('width=0.6\\textwidth')
            else:
                options.append('width=0.8\\textwidth')
        except (ValueError, TypeError):
            options.append('width=0.8\\textwidth')
        
        options.append('height=\\textheight')
        options.append('keepaspectratio')
        
        option_str = ','.join(options)
        
        # figcaption 처리 (링크 포함)
        figcaption = figure.find('figcaption')
        caption = ''
        if figcaption:
            # figcaption의 내용을 LaTeX로 변환 (링크 포함)
            caption = self._process_inline_elements(figcaption, depth + 1)
        elif img.get('alt'):
            caption = self.escape_latex(img.get('alt'))
        elif img.get('title'):
            caption = self.escape_latex(img.get('title'))
        
        # figure 환경 사용
        latex = f'\\begin{{figure}}[H]\n\\centering\n'
        latex += f'\\includegraphics[{option_str}]{{{src}}}\n'
        if caption:
            latex += f'\\caption{{{caption}}}\n'
        latex += '\\end{figure}\n'
        
        return latex
    
    def _convert_image(self, img):
        """이미지 변환"""
        src = img.get('src', '')
        alt = img.get('alt', '')
        title = img.get('title', '')
        
        if not src:
            return ''
        
        # WebP를 PNG로 변경
        if src.endswith('.webp'):
            src = src.replace('.webp', '.png')
        
        # 이미지 경로를 images/ 형태로 유지
        if not src.startswith('images/') and not src.startswith('./'):
            src = f'images/{src}'
        
        # 크기 옵션 결정
        width = img.get('width')
        height = img.get('height')
        style = img.get('style', '')
        
        # 스타일에서 크기 추출
        style_width = re.search(r'width:\s*(\d+)(?:px)?', style)
        style_height = re.search(r'height:\s*(\d+)(?:px)?', style)
        
        if style_width:
            width = style_width.group(1)
        if style_height:
            height = style_height.group(1)
        
        # LaTeX 옵션 생성
        options = []
        try:
            if width and int(width) > 600:
                options.append('width=\\textwidth')
            elif width and int(width) > 400:
                options.append('width=0.8\\textwidth')
            elif width and int(width) > 200:
                options.append('width=0.6\\textwidth')
            else:
                options.append('width=0.8\\textwidth')  # 기본값
        except (ValueError, TypeError):
            options.append('width=0.8\\textwidth')  # 기본값
        
        options.append('height=\\textheight')
        options.append('keepaspectratio')
        
        option_str = ','.join(options)
        caption = alt or title
        
        # figure 환경 사용
        latex = f'\\begin{{figure}}[H]\n\\centering\n'
        latex += f'\\includegraphics[{option_str}]{{{src}}}\n'
        if caption:
            latex += f'\\caption{{{self.escape_latex(caption)}}}\n'
        latex += '\\end{figure}\n'
        
        return latex
    
    def _convert_list(self, element, list_type, depth=0):
        """리스트 변환"""
        # 무한 재귀 방지
        if depth > 20:
            return ''
            
        items = []
        for li in element.find_all('li', recursive=False):
            item_content = self._process_inline_elements(li, depth + 1)
            items.append(f'  \\item {item_content}')
        
        if items:
            return f'\\begin{{{list_type}}}\n' + '\n'.join(items) + f'\n\\end{{{list_type}}}\n'
        return ''
    
    def _convert_table(self, table):
        """테이블 변환"""
        # 최대 열 수 계산
        max_cols = 0
        all_rows = table.find_all('tr')
        
        for row in all_rows:
            col_count = sum(int(cell.get('colspan', 1)) for cell in row.find_all(['td', 'th']))
            max_cols = max(max_cols, col_count)
        
        if max_cols == 0 or not all_rows:
            return ''
        
        # 테이블 시작
        col_spec = '|' + 'l|' * max_cols
        latex = f'\\begin{{longtable}}{{{col_spec}}}\n\\hline\n'
        
        # 헤더 찾기
        thead = table.find('thead')
        if thead:
            for row in thead.find_all('tr'):
                latex += self._convert_table_row(row, max_cols, is_header=True)
            latex += '\\endhead\n'
        
        # 첫 번째 행이 th를 포함하면 헤더로 처리
        elif all_rows and all_rows[0].find('th'):
            latex += self._convert_table_row(all_rows[0], max_cols, is_header=True)
            latex += '\\endhead\n'
            all_rows = all_rows[1:]
        
        # 본문
        tbody = table.find('tbody')
        rows_to_process = tbody.find_all('tr') if tbody else all_rows
        
        for row in rows_to_process:
            if not (thead and row.parent == thead):
                latex += self._convert_table_row(row, max_cols)
        
        latex += '\\end{longtable}\n'
        return latex
    
    def _convert_table_row(self, row, max_cols, is_header=False):
        """테이블 행 변환"""
        cells = row.find_all(['td', 'th'])
        cell_contents = []
        
        for cell in cells:
            content = self.escape_latex(cell.get_text().strip())
            colspan = int(cell.get('colspan', 1))
            
            if colspan > 1:
                cell_contents.append(f'\\multicolumn{{{colspan}}}{{|c|}}{{{content}}}')
            else:
                cell_contents.append(content)
        
        # 빈 셀 채우기
        while len(cell_contents) < max_cols:
            cell_contents.append('')
        
        # 헤더 처리 수정
        if is_header:
            # 각 셀을 bold로 만들기
            bold_cells = []
            for content in cell_contents[:max_cols]:
                if content and not content.startswith('\\multicolumn'):
                    bold_cells.append(f'\\textbf{{{content}}}')
                elif content.startswith('\\multicolumn'):
                    # multicolumn 내용도 bold로
                    bold_cells.append(content.replace('{{{', '{{\\textbf{').replace('}}}', '}}}'))
                else:
                    bold_cells.append(content)
            row_latex = ' & '.join(bold_cells) + ' \\\\ \\hline\n'
        else:
            row_latex = ' & '.join(cell_contents[:max_cols]) + ' \\\\ \\hline\n'
        
        return row_latex
    
    def _convert_code_block(self, pre):
        """코드 블록 변환"""
        code = pre.find('code')
        if code:
            # 언어 감지
            classes = code.get('class', [])
            language = ''
            if isinstance(classes, list):
                for cls in classes:
                    if isinstance(cls, str) and cls.startswith('language-'):
                        language = cls.replace('language-', '')
                        break
            elif isinstance(classes, str) and classes.startswith('language-'):
                language = classes.replace('language-', '')
            
            content = code.get_text()
        else:
            content = pre.get_text()
            language = ''
        
        if language:
            return f'\\begin{{lstlisting}}[language={language}]\n{content}\n\\end{{lstlisting}}\n'
        else:
            return f'\\begin{{lstlisting}}\n{content}\n\\end{{lstlisting}}\n'
    
    def _convert_definition_list(self, dl, depth=0):
        """정의 리스트 변환"""
        # 무한 재귀 방지
        if depth > 20:
            return ''
            
        latex = '\\begin{description}\n'
        
        current_dt = None
        for child in dl.children:
            if hasattr(child, 'name'):
                if child.name == 'dt':
                    current_dt = self.escape_latex(child.get_text())
                elif child.name == 'dd' and current_dt:
                    dd_content = self._process_inline_elements(child, depth + 1)
                    latex += f'  \\item[{current_dt}] {dd_content}\n'
                    current_dt = None
        
        latex += '\\end{description}\n'
        return latex
    
    def convert(self, soup):
        """전체 변환"""
        body = soup.find('body') or soup
        
        # 제목 추출 - title 태그 우선, 없으면 h1 태그 사용
        title = 'Converted Document'  # 기본값
        
        # HTML title 태그에서 제목 추출
        title_tag = soup.find('title')
        if title_tag and title_tag.get_text().strip():
            title = title_tag.get_text().strip()
        
        # title 태그가 없으면 h1 태그에서 추출
        elif soup.find('h1'):
            h1 = soup.find('h1')
            title = h1.get_text().strip()
        
        # 제목 정리 (불필요한 사이트명 제거 등)
        title = self._clean_title(title)
        
        # LaTeX에서 안전한 제목으로 변환
        safe_title = self.escape_latex(title)
        
        # 헤더에서 제목 교체
        updated_header = self.latex_header.replace('DOCUMENT_TITLE', safe_title)
        
        # 메타 정보 추출
        meta_author = soup.find('meta', {'name': 'author'})
        if meta_author:
            author = meta_author.get('content', '')
            updated_header = updated_header.replace('HTML to LaTeX Converter', self.escape_latex(author))
        
        # 본문 변환
        content = [updated_header]
        
        for element in body.children:
            if hasattr(element, 'name') and element.name:
                converted = self.convert_element(element, 0)
                if converted and converted.strip():
                    content.append(converted)
        
        content.append(self.latex_footer)
        
        # LaTeX 후처리 - 문법 오류 수정
        result = '\n'.join(content)
        result = self._post_process_latex_content(result)
        
        return result
    
    def _clean_title(self, title):
        """제목 정리 - 사이트명, 불필요한 구분자 제거"""
        if not title:
            return 'Converted Document'
        
        # 일반적인 구분자들로 분리해서 첫 번째 부분만 사용
        # 단, 전체 길이가 200자 이하면 구분자로 자르지 않음 (정상적인 제목일 가능성)
        if len(title) <= 200:
            # 길이 제한만 적용 (더 관대하게)
            if len(title) > 150:
                title = title[:150] + '...'
            return title
        
        separators = [' | ', ' - ', ' :: ', ' — ', ' – ', ' • ']
        
        for sep in separators:
            if sep in title:
                # 구분자 앞의 내용이 더 길면 그것을 제목으로 사용
                parts = title.split(sep)
                if len(parts[0].strip()) > 10:  # 첫 번째 부분이 충분히 길면
                    title = parts[0].strip()
                    break
        
        # 길이 제한 (너무 긴 제목은 잘라냄)
        if len(title) > 150:
            title = title[:150] + '...'
        
        return title
    
    def _post_process_latex_content(self, content):
        """LaTeX 내용 후처리 - 문법 오류 수정"""
        try:
            # 1. 잘못된 줄바꿈 패턴 수정
            # 문단 시작에 오는 \\ 제거
            content = re.sub(r'\n\\\\\n\s*', '\n\n', content)
            
            # 2. 여러 연속된 줄바꿈을 두 개로 제한
            content = re.sub(r'\n{3,}', '\n\n', content)
            
            # 3. 섹션 앞의 불필요한 줄바꿈 정리
            content = re.sub(r'\n+\\section', '\n\\section', content)
            content = re.sub(r'\n+\\subsection', '\n\\subsection', content)
            content = re.sub(r'\n+\\subsubsection', '\n\\subsubsection', content)
            
            # 4. 문단 중간의 잘못된 \\ 패턴 수정
            # \\ 뒤에 바로 텍스트가 오는 경우를 문단 구분으로 변경
            content = re.sub(r'\\\\\n\s*([A-Z][a-z])', r'\n\n\1', content)
            
            # 5. 빈 줄로 시작하는 \\ 제거
            content = re.sub(r'^\\\\\n', '\n', content, flags=re.MULTILINE)
            
            # 6. 단독으로 사용된 \\ 제거
            content = re.sub(r'^\\\\\s*$', '', content, flags=re.MULTILINE)
            
        except Exception as e:
            print(f"후처리 정규식 오류: {e}")
            # 오류 발생 시 기본 처리만 수행
            content = content.replace('\n\n\n', '\n\n')
        
        return content


def compile_to_pdf(tex_file):
    """LaTeX 파일을 PDF로 컴파일"""
    import subprocess
    
    try:
        # 작업 디렉토리를 tex 파일이 있는 디렉토리로 변경
        tex_dir = os.path.dirname(os.path.abspath(tex_file))
        tex_filename = os.path.basename(tex_file)
        
        # pdflatex 실행 (두 번 실행하여 참조 해결)
        for _ in range(2):
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', tex_filename],
                cwd=tex_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"컴파일 오류:\n{result.stderr}")
                return False
        
        pdf_file = os.path.join(tex_dir, tex_filename.replace('.tex', '.pdf'))
        print(f"PDF 생성 완료: {pdf_file}")
        return True
        
    except FileNotFoundError:
        print("pdflatex가 설치되지 않았습니다. TeX 배포판을 설치하세요.")
        return False
