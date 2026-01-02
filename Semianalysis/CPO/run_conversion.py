#!/usr/bin/env python3
"""
로컬 HTML을 LaTeX로 변환하는 실행 스크립트
"""

from local_html_to_latex import LocalHTMLToLaTeXConverter, compile_to_pdf
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    print("="*70)
    print("HTML to LaTeX 변환기")
    print("="*70)
    
    # 파일 경로 설정
    html_file = "Co Packaged Optics (CPO) – Scaling with Light for the Next Wave of Interconnect.html"
    resources_dir = "Co Packaged Optics (CPO) – Scaling with Light for the Next Wave of Interconnect_files"
    output_name = "cpo_document"
    
    print(f"\n[설정]")
    print(f"HTML 파일: {html_file}")
    print(f"리소스 폴더: {resources_dir}")
    print(f"출력 이름: {output_name}")
    print(f"출력 디렉토리: latex_output/")
    
    # 변환기 생성
    converter = LocalHTMLToLaTeXConverter(
        html_file=html_file,
        resources_dir=resources_dir,
        output_dir='latex_output'
    )
    
    print(f"\n[변환 시작]")
    print("커스텀 변환기를 사용합니다 (더 나은 품질)")
    
    try:
        # LaTeX로 변환
        tex_file = converter.convert_to_latex(
            output_filename=output_name,
            use_custom=True  # 커스텀 변환기 사용
        )
        
        print(f"\n{'='*70}")
        print(f"✓ 변환 완료!")
        print(f"{'='*70}")
        print(f"\nLaTeX 파일: {tex_file}")
        print(f"이미지 폴더: latex_output/images/")
        print(f"처리된 HTML: latex_output/processed.html")
        
        # PDF 컴파일 여부 확인
        print(f"\n{'='*70}")
        
        # 비대화형 모드 지원
        import sys
        if len(sys.argv) > 1 and sys.argv[1] == '--pdf':
            compile_pdf = 'y'
        elif sys.stdin.isatty():
            # 대화형 터미널인 경우에만 입력 요청
            compile_pdf = input("\nPDF로 컴파일하시겠습니까? (y/n) [n]: ").strip().lower()
        else:
            # 비대화형 모드에서는 기본값 사용
            compile_pdf = 'n'
        
        if compile_pdf == 'y':
            print("\n[PDF 컴파일 시작]")
            if compile_to_pdf(tex_file):
                print(f"\n✓ PDF 컴파일 성공!")
                print(f"PDF 파일: {tex_file.replace('.tex', '.pdf')}")
            else:
                print(f"\n✗ PDF 컴파일 실패")
                print("하지만 .tex 파일은 성공적으로 생성되었습니다.")
                print("수동으로 pdflatex를 실행하거나 Overleaf 등에서 컴파일할 수 있습니다.")
        else:
            print("\n.tex 파일이 생성되었습니다.")
            print("나중에 PDF로 컴파일하려면:")
            print(f"  cd latex_output && pdflatex {output_name}.tex")
        
        print(f"\n{'='*70}")
        print("완료!")
        print(f"{'='*70}\n")
        
    except FileNotFoundError as e:
        logger.error(f"\n파일을 찾을 수 없습니다: {str(e)}")
        logger.error("HTML 파일과 리소스 폴더 경로를 확인해주세요.")
        return 1
        
    except Exception as e:
        logger.error(f"\n변환 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
