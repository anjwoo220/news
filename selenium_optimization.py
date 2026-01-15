
"""
[Selenium Memory Optimization Template]
이 파일은 프로젝트 내에서 Selenium을 사용하는 부분이 발견되지 않아
사용자가 직접 참고하여 적용할 수 있도록 만든 템플릿입니다.

만약 크롤링 코드(예: crawling.py 또는 utils.py)가 있다면
아래 설정을 복사하여 적용하세요.
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def get_optimized_driver():
    options = Options()
    
    # 🚨 [중요] 메모리 최적화 필수 옵션
    options.add_argument("--headless")              # 화면 없이 실행
    options.add_argument("--no-sandbox")            # 리눅스/컨테이너 환경 필수
    options.add_argument("--disable-dev-shm-usage") # /dev/shm 파티션 사용 안 함 (OOM 방지)
    options.add_argument("--disable-gpu")           # GPU 가속 비활성화
    options.add_argument("--single-process")        # 프로세스 최소화 (메모리 절약)
    options.add_argument("--disable-extensions")    # 확장 프로그램 비활성화
    
    # 드라이버 생성
    driver = webdriver.Chrome(options=options)
    return driver

if __name__ == "__main__":
    print("이 코드는 템플릿입니다. 실제 크롤링 파일에 붙여넣어 사용하세요.")
    try:
        driver = get_optimized_driver()
        print("Driver initialized successfully with optimized options.")
        driver.quit()
    except Exception as e:
        print(f"Error initializing driver: {e}")
