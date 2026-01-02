import os
import re
import shutil
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from PIL import Image
import pypandoc
import logging
from pathlib import Path

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LocalHTMLToLaTeXConverter:
    """로컬 HTML 파일을 LaTeX로 변환하는 클래스"""
    
    def __init__(self, html_file, resources_dir=None, output_dir='latex_output'):
        """
        Args:
            html_file: 로컬 HTML 파일 경로
            resources_dir: HTML의 리소스 폴더 경로 (이미지, CSS 등)
            output_dir: 출력 디렉토리
        """
        self.html_file = html_file
        self.resources_dir = resources_dir
        self.output_dir = output_dir
        self.image_dir = os.path.join(output_dir, 'images')
        self.image_map = {}  # 원본 경로와 새 경로 매핑
        
        # resources_dir이 지정되지 않았으면 HTML 파일명_files 폴더를 찾음
        if not self.resources_dir:
            html_base = os.path.splitext(self.html_file)[0]
            potential_dir = f"{html_base}_files"
            if os.path.exists(potential_dir):
                self.resources_dir = potential_dir
                logger.info(f"리소스 폴더 자동 감지: {self.resources_dir}")
        
        self.ensure_pandoc_installed()
    
    def ensure_pandoc_installed(self):
        """Pandoc 설치 확인"""
        try:
            pypandoc.get_pandoc_version()
            logger.info("Pandoc이 이미 설치되어 있습니다.")
        except OSError:
            logger.info("Pandoc이 없습니다. 자동으로 다운로드합니다...")
            pypandoc.download_pandoc()
            logger.info("Pandoc 다운로드 완료!")
    
    def load_local_html(self):
        """로컬 HTML 파일 로드"""
        logger.info(f"HTML 파일 로드 중: {self.html_file}")
        
        # 디렉토리 생성
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)
        
        # HTML 파일 읽기
        with open(self.html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # 이미지 처리
        if self.resources_dir and os.path.exists(self.resources_dir):
            self._process_local_images(soup)
        
        # 수정된 HTML 저장
        with open(os.path.join(self.output_dir, 'processed.html'), 'w', encoding='utf-8') as f:
            f.write(str(soup.prettify()))
        
        logger.info(f"HTML 로드 완료: {len(self.image_map)}개의 이미지 처리됨")
        return soup
    
    def _process_local_images(self, soup):
        """로컬 이미지 파일들을 출력 디렉토리로 복사 및 변환"""
        img_count = 0
        
        for img in soup.find_all('img'):
            # 다양한 이미지 소스 확인
            img_url = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            
            if not img_url:
                continue
            
            # 온라인 URL에서 파일명 추출
            if img_url.startswith('http'):
                # URL에서 실제 파일명 추출 (예: 36b44226-8a2b-48e0-8ae3-333416d66818_5464x2026.png)
                original_path = self._extract_filename_from_url(img_url)
                if not original_path:
                    logger.warning(f"온라인 이미지 URL에서 파일명 추출 실패: {img_url}")
                    continue
            else:
                # 로컬 파일 경로 생성
                original_path = self._resolve_local_path(img_url)
            
            if not original_path or not os.path.exists(original_path):
                logger.warning(f"이미지 파일을 찾을 수 없음: {img_url}")
                continue
            
            # 이미 처리한 이미지인지 확인
            if original_path in self.image_map:
                img['src'] = self.image_map[original_path]
                continue
            
            # 새 파일명 생성
            local_filename = self._generate_filename(img_url, img_count)
            local_path = os.path.join('images', local_filename)
            full_path = os.path.join(self.image_dir, local_filename)
            
            # 이미지 복사 및 변환
            if self._copy_and_convert_image(original_path, full_path):
                img['src'] = local_path
                self.image_map[original_path] = local_path
                img_count += 1
                
                # data-src 등 제거
                for attr in ['data-src', 'data-lazy-src', 'srcset']:
                    if img.has_attr(attr):
                        del img[attr]
    
    def _extract_filename_from_url(self, url):
        """온라인 URL에서 파일명을 추출하고 로컬 파일 경로 찾기"""
        from urllib.parse import unquote
        import re
        
        # URL 디코딩
        url = unquote(url)
        
        # Substack 이미지 URL 패턴에서 파일명 추출
        # 예: https://substackcdn.com/image/fetch/.../36b44226-8a2b-48e0-8ae3-333416d66818_5464x2026.png
        # 또는: https://substack-post-media.s3.amazonaws.com/public/images/36b44226-8a2b-48e0-8ae3-333416d66818_5464x2026.png
        
        # UUID 패턴으로 파일명 찾기 (예: 36b44226-8a2b-48e0-8ae3-333416d66818_5464x2026.png)
        pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_\d+x\d+\.(png|jpg|jpeg|webp|gif))'
        match = re.search(pattern, url, re.IGNORECASE)
        
        if match:
            filename = match.group(1)
            # 리소스 폴더에서 파일 찾기
            if self.resources_dir:
                filepath = os.path.join(self.resources_dir, filename)
                if os.path.exists(filepath):
                    return filepath
                # .webp를 다른 확장자로 시도
                for ext in ['.png', '.jpg', '.jpeg']:
                    alt_filename = os.path.splitext(filename)[0] + ext
                    alt_filepath = os.path.join(self.resources_dir, alt_filename)
                    if os.path.exists(alt_filepath):
                        return alt_filepath
        
        # URL 끝부분에서 직접 파일명 추출 시도
        filename = os.path.basename(url.split('?')[0])
        if filename and self.resources_dir:
            filepath = os.path.join(self.resources_dir, filename)
            if os.path.exists(filepath):
                return filepath
        
        return None
    
    def _resolve_local_path(self, img_url):
        """이미지 URL을 로컬 파일 시스템 경로로 변환"""
        # URL 디코딩
        from urllib.parse import unquote
        img_url = unquote(img_url)
        
        # 절대 경로인 경우
        if os.path.isabs(img_url):
            return img_url
        
        # 상대 경로인 경우
        html_dir = os.path.dirname(os.path.abspath(self.html_file))
        
        # 1. HTML 파일과 같은 디렉토리 기준
        path1 = os.path.join(html_dir, img_url)
        if os.path.exists(path1):
            return path1
        
        # 2. resources_dir 기준
        if self.resources_dir:
            # img_url에서 폴더명 제거 (예: "files/image.jpg" -> "image.jpg")
            img_basename = os.path.basename(img_url)
            path2 = os.path.join(self.resources_dir, img_basename)
            if os.path.exists(path2):
                return path2
            
            # 3. resources_dir + 전체 경로
            path3 = os.path.join(self.resources_dir, img_url)
            if os.path.exists(path3):
                return path3
        
        return None
    
    def _copy_and_convert_image(self, src_path, dst_path):
        """이미지 파일 복사 및 필요시 변환"""
        try:
            # 이미지 열기
            img = Image.open(src_path)
            
            # RGBA/P 모드를 RGB로 변환
            if img.mode in ('RGBA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode == 'CMYK':
                img = img.convert('RGB')
            
            # WebP를 PNG로 변환
            if src_path.lower().endswith('.webp') or img.format == 'WEBP':
                dst_path = os.path.splitext(dst_path)[0] + '.png'
                img.save(dst_path, 'PNG', optimize=True)
            else:
                # 기존 포맷 유지하면서 최적화
                img.save(dst_path, img.format or 'PNG', optimize=True, quality=95)
            
            logger.info(f"이미지 처리 성공: {os.path.basename(dst_path)}")
            return True
            
        except Exception as e:
            logger.warning(f"이미지 처리 실패: {src_path} - {str(e)}")
            # 변환 실패 시 단순 복사 시도
            try:
                shutil.copy2(src_path, dst_path)
                logger.info(f"이미지 복사 성공: {os.path.basename(dst_path)}")
                return True
            except Exception as e2:
                logger.error(f"이미지 복사도 실패: {src_path} - {str(e2)}")
                return False
    
    def _generate_filename(self, url, counter):
        """안전한 파일명 생성"""
        filename = os.path.basename(url)
        
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
    
    def _move_figcaption_to_alt(self, soup):
        """figcaption의 텍스트를 img의 alt/title로 이동 (백업용)"""
        for figure in soup.find_all('figure'):
            img = figure.find('img')
            figcaption = figure.find('figcaption')
            
            if img and figcaption:
                caption_text = figcaption.get_text(strip=True)
                if caption_text:
                    # img에 alt나 title이 없으면 백업으로 추가 (figcaption은 유지)
                    if not img.get('alt'):
                        img['alt'] = caption_text
                    if not img.get('title'):
                        img['title'] = caption_text
                    # figcaption은 제거하지 않음 (convert.py에서 처리)
    
    def _remove_related_articles(self, soup):
        """관련 기사 링크 및 썸네일 제거"""
        import re
        
        # "Read full story" 텍스트를 포함한 요소 찾기
        for element in soup.find_all(text=re.compile(r'Read full story|read full story', re.IGNORECASE)):
            # 부모 요소들을 거슬러 올라가서 제거
            parent = element.parent
            while parent:
                # a 태그나 div를 포함한 상위 컨테이너를 찾음
                if parent.name in ['div', 'section', 'article', 'aside']:
                    # 이 컨테이너가 관련 기사 블록인지 확인 (썸네일 이미지 포함)
                    if parent.find('img') and parent.find('a'):
                        parent.decompose()
                        logger.info(f"관련 기사 링크 제거: {element.strip()[:50]}")
                        break
                parent = parent.parent
    
    def preprocess_html(self, soup):
        """HTML 전처리 및 정리"""
        logger.info("HTML 전처리 시작")
        
        # figcaption을 img의 alt로 이동
        self._move_figcaption_to_alt(soup)
        
        # "Read full story" 같은 관련 기사 링크 제거
        self._remove_related_articles(soup)
        
        # 불필요한 요소 제거
        remove_tags = ['script', 'style', 'meta', 'link', 'noscript', 'iframe', 'object', 'embed']
        for tag in remove_tags:
            for element in soup.find_all(tag):
                element.decompose()
        
        # 빈 요소 제거 (하지만 img, figure, picture를 포함한 요소는 보존)
        for element in soup.find_all():
            # img를 보호할 요소들
            if element.name in ['img', 'br', 'hr', 'input']:
                continue
            # img, figure, picture를 자손으로 가진 요소는 보존
            if element.find(['img', 'figure', 'picture']):
                continue
            # 텍스트가 없으면 제거
            if not element.get_text(strip=True):
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
        """모든 이미지 최적화"""
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
                img = Image.open(filepath)
                
                # 크기 조정
                max_width = 1200
                max_height = 1600
                
                if img.width > max_width or img.height > max_height:
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                    img.save(filepath, img.format or 'PNG', optimize=True, quality=95)
                    optimized_count += 1
                    logger.info(f"이미지 크기 조정: {filename}")
                
            except Exception as e:
                logger.error(f"이미지 최적화 실패: {filename} - {str(e)}")
        
        logger.info(f"이미지 최적화 완료: {optimized_count}개 크기 조정")
    
    def convert_to_latex(self, output_filename, use_custom=True):
        """LaTeX로 변환하는 메인 함수"""
        try:
            # 1. 로컬 HTML 로드
            soup = self.load_local_html()
            
            # 2. HTML 전처리
            soup = self.preprocess_html(soup)
            
            # 3. 이미지 최적화
            self.optimize_images()
            
            # 4. WebP 참조 업데이트
            self._update_webp_references(soup)
            
            # 업데이트된 HTML 저장
            with open(os.path.join(self.output_dir, 'processed.html'), 'w', encoding='utf-8') as f:
                f.write(str(soup.prettify()))
            
            # 5. LaTeX 변환
            if use_custom:
                # 커스텀 변환기 사용 (더 나은 결과)
                return self._custom_latex_convert(soup, output_filename)
            else:
                # Pandoc 사용
                return self._pandoc_latex_convert(output_filename)
            
        except Exception as e:
            logger.error(f"변환 중 오류 발생: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def _update_webp_references(self, soup):
        """HTML 내의 WebP 참조를 PNG로 업데이트"""
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src.endswith('.webp'):
                img['src'] = src.replace('.webp', '.png')
    
    def _custom_latex_convert(self, soup, output_filename):
        """커스텀 LaTeX 변환"""
        logger.info("커스텀 LaTeX 변환 시작")
        
        from convert import CustomHTML2LaTeX
        from bs4 import BeautifulSoup
        
        # article 태그가 있으면 그것만 추출해서 변환
        article = soup.find('article')
        if article:
            logger.info("article 태그를 찾았습니다. article 내용만 변환합니다.")
            
            # 첫 번째 h1을 찾아서 문서 제목으로 사용
            first_h1 = article.find('h1')
            doc_title = 'Document'
            
            if first_h1:
                doc_title = first_h1.get_text(strip=True)
                logger.info(f"첫 번째 h1을 문서 제목으로 사용: {doc_title[:80]}")
                # 첫 번째 h1을 제거 (section으로 변환되지 않도록)
                first_h1.decompose()
            elif soup.find('title'):
                doc_title = soup.find('title').get_text()
            
            # article을 새로운 soup으로 감싸기
            new_html = f"<html><head><title>{doc_title}</title></head><body>{str(article)}</body></html>"
            soup = BeautifulSoup(new_html, 'html.parser')
        else:
            logger.warning("article 태그를 찾을 수 없습니다. 전체 body를 변환합니다.")
        
        converter = CustomHTML2LaTeX(self.image_dir)
        latex_content = converter.convert(soup)
        
        output_file = os.path.join(self.output_dir, f"{output_filename}.tex")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(latex_content)
        
        logger.info(f"커스텀 변환 완료: {output_file}")
        return output_file
    
    def _pandoc_latex_convert(self, output_filename):
        """Pandoc을 사용한 LaTeX 변환"""
        logger.info("Pandoc을 사용한 LaTeX 변환 시작")
        
        input_file = os.path.join(self.output_dir, 'processed.html')
        output_file = os.path.join(self.output_dir, f"{output_filename}.tex")
        
        # LaTeX 템플릿
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

\graphicspath{{./images/}}
\DeclareGraphicsExtensions{.png,.jpg,.jpeg,.pdf}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    filecolor=magenta,
    urlcolor=cyan,
}

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
                '-V', 'author=LaTeX Converter',
                '--listings',
                '--wrap=preserve',
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
        def replace_graphics(match):
            options = match.group(1) if match.group(1) else ''
            filename = match.group(2)
            
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
        
        # 수정된 내용 저장
        with open(latex_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info("LaTeX 파일 후처리 완료")


def compile_to_pdf(tex_file):
    """LaTeX 파일을 PDF로 컴파일"""
    import subprocess
    
    try:
        # 작업 디렉토리를 tex 파일이 있는 디렉토리로 변경
        tex_dir = os.path.dirname(os.path.abspath(tex_file))
        tex_filename = os.path.basename(tex_file)
        
        logger.info(f"PDF 컴파일 시작: {tex_filename}")
        
        # pdflatex 실행 (두 번 실행하여 참조 해결)
        for i in range(2):
            logger.info(f"pdflatex 실행 {i+1}/2")
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', tex_filename],
                cwd=tex_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"컴파일 오류:\n{result.stderr}")
                return False
        
        pdf_file = os.path.join(tex_dir, tex_filename.replace('.tex', '.pdf'))
        logger.info(f"PDF 생성 완료: {pdf_file}")
        return True
        
    except FileNotFoundError:
        logger.error("pdflatex가 설치되지 않았습니다. TeX 배포판을 설치하세요.")
        logger.info("macOS: brew install mactex")
        logger.info("Ubuntu: sudo apt-get install texlive-full")
        return False


# 사용 예시
if __name__ == "__main__":
    # 설정
    html_file = "Co Packaged Optics (CPO) – Scaling with Light for the Next Wave of Interconnect.html"
    resources_dir = "Co Packaged Optics (CPO) – Scaling with Light for the Next Wave of Interconnect_files"
    output_name = "cpo_document"
    
    # 변환기 생성
    converter = LocalHTMLToLaTeXConverter(
        html_file=html_file,
        resources_dir=resources_dir,
        output_dir='latex_output'
    )
    
    # LaTeX로 변환
    try:
        tex_file = converter.convert_to_latex(
            output_filename=output_name,
            use_custom=True  # True: 커스텀 변환기, False: Pandoc
        )
        
        logger.info(f"\n{'='*60}")
        logger.info(f"변환 완료!")
        logger.info(f"LaTeX 파일: {tex_file}")
        logger.info(f"{'='*60}\n")
        
        # PDF 컴파일 (선택사항)
        compile_pdf = input("PDF로 컴파일하시겠습니까? (y/n): ").strip().lower()
        if compile_pdf == 'y':
            if compile_to_pdf(tex_file):
                logger.info("PDF 컴파일 성공!")
            else:
                logger.error("PDF 컴파일 실패. .tex 파일은 생성되었습니다.")
        
    except Exception as e:
        logger.error(f"변환 실패: {str(e)}")
        import traceback
        traceback.print_exc()
