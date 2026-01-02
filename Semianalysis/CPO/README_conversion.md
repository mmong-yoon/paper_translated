# 로컬 HTML to LaTeX 변환 가이드

로컬에 다운로드한 HTML 파일을 LaTeX 형식으로 변환하는 도구입니다.

## 필요한 패키지

```bash
pip install beautifulsoup4 pillow pypandoc requests
```

## 파일 구조

```
cpo/
├── Co Packaged Optics (...).html          # 원본 HTML 파일
├── Co Packaged Optics (...)_files/        # 리소스 폴더 (이미지 등)
├── convert.py                              # 기존 변환 로직 (재사용)
├── local_html_to_latex.py                 # 새로운 로컬 파일 변환기
├── run_conversion.py                       # 실행 스크립트
└── latex_output/                           # 출력 디렉토리 (자동 생성)
    ├── cpo_document.tex                    # 생성된 LaTeX 파일
    ├── images/                             # 최적화된 이미지들
    └── processed.html                      # 전처리된 HTML
```

## 사용 방법

### 방법 1: 실행 스크립트 사용 (추천)

가장 간단한 방법입니다:

```bash
python run_conversion.py
```

스크립트가 자동으로:
1. HTML 파일 로드
2. 이미지 처리 및 최적화
3. LaTeX로 변환
4. (선택) PDF 컴파일

### 방법 2: Python 코드에서 직접 사용

```python
from local_html_to_latex import LocalHTMLToLaTeXConverter

# 변환기 생성
converter = LocalHTMLToLaTeXConverter(
    html_file="your_file.html",
    resources_dir="your_file_files",  # 없으면 자동 감지
    output_dir='output'
)

# LaTeX로 변환
tex_file = converter.convert_to_latex(
    output_filename="output_name",
    use_custom=True  # True: 커스텀 변환기 (추천), False: Pandoc
)

print(f"LaTeX 파일 생성됨: {tex_file}")
```

## 주요 기능

### 1. 로컬 파일 처리
- URL 다운로드 없이 로컬 HTML 파일을 직접 처리
- 리소스 폴더 자동 감지 (파일명_files 패턴)

### 2. 이미지 처리
- 다양한 경로 형식 지원 (상대/절대 경로)
- WebP → PNG 자동 변환
- 이미지 크기 최적화 (max: 1200x1600)
- RGBA/CMYK → RGB 변환

### 3. HTML 전처리
- 불필요한 태그 제거 (script, style, meta 등)
- 속성 정리
- 테이블 구조 개선
- 빈 요소 제거

### 4. LaTeX 변환
두 가지 변환 방식 제공:

#### 커스텀 변환기 (추천)
- 더 나은 제목/섹션 처리
- 이미지 캡션 자동 생성
- 테이블 최적화
- 코드 블록 하이라이팅

#### Pandoc 변환기
- 표준 Pandoc 변환
- 더 빠른 처리
- 광범위한 HTML 지원

## PDF 컴파일

LaTeX 파일을 PDF로 컴파일하려면 TeX 배포판이 필요합니다:

### macOS
```bash
brew install mactex
# 또는
brew install basictex
```

### Ubuntu/Debian
```bash
sudo apt-get install texlive-full
```

### Windows
[MiKTeX](https://miktex.org/) 다운로드 및 설치

### 컴파일 명령
```bash
cd latex_output
pdflatex cpo_document.tex
pdflatex cpo_document.tex  # 참조 해결을 위해 2번 실행
```

## 출력 구조

```
latex_output/
├── cpo_document.tex        # 메인 LaTeX 파일
├── cpo_document.pdf        # 컴파일된 PDF (선택)
├── cpo_document.aux        # LaTeX 보조 파일
├── cpo_document.log        # 컴파일 로그
├── cpo_document.toc        # 목차 파일
├── images/                 # 이미지 폴더
│   ├── image_0001.png
│   ├── image_0002.jpg
│   └── ...
└── processed.html          # 전처리된 HTML
```

## LaTeX 문서 구조

생성된 LaTeX 문서는 다음을 포함합니다:

- **커버 페이지**: 제목과 날짜
- **목차**: 자동 생성된 섹션 목록
- **본문**: 
  - 섹션/서브섹션 구조
  - 이미지 (캡션 포함)
  - 테이블
  - 코드 블록
  - 링크 (하이퍼링크)

## 커스터마이징

### 파일명 변경
`run_conversion.py`에서 수정:

```python
html_file = "your_file.html"
resources_dir = "your_file_files"
output_name = "your_output_name"
```

### 출력 디렉토리 변경
```python
converter = LocalHTMLToLaTeXConverter(
    html_file=html_file,
    resources_dir=resources_dir,
    output_dir='custom_output_dir'  # 여기를 변경
)
```

### 이미지 크기 제한 변경
`local_html_to_latex.py`의 `optimize_images()` 메소드에서:

```python
max_width = 1200   # 원하는 값으로 변경
max_height = 1600  # 원하는 값으로 변경
```

## 문제 해결

### 이미지가 표시되지 않음
- 리소스 폴더 경로 확인
- 이미지 파일이 실제로 존재하는지 확인
- 로그에서 "이미지 파일을 찾을 수 없음" 메시지 확인

### PDF 컴파일 오류
- LaTeX 배포판이 설치되어 있는지 확인
- `.log` 파일에서 구체적인 오류 확인
- 온라인 LaTeX 편집기 (Overleaf) 사용 고려

### 한글 깨짐
LaTeX 파일에서 주석 해제:
```latex
% \usepackage{kotex}
```
→
```latex
\usepackage{kotex}
```

## 기존 convert.py와의 차이점

| 기능 | convert.py | local_html_to_latex.py |
|------|-----------|------------------------|
| 입력 | URL (온라인) | 로컬 HTML 파일 |
| 이미지 다운로드 | O | X (로컬 복사) |
| 리소스 폴더 | 자동 생성 | 기존 폴더 사용 |
| 변환 방식 | 동일 | 동일 (재사용) |

## 라이센스 및 주의사항

- 이 도구는 개인적인 용도로 사용하세요
- 저작권이 있는 콘텐츠를 무단으로 배포하지 마세요
- 웹사이트의 이용 약관을 준수하세요
