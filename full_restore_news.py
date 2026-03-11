import subprocess
import json
import toml
import pandas as pd
from db_utils import load_news_from_sheet, save_news_to_sheet

def extract_all_git_news():
    print("⏳ Git 히스토리에서 모든 뉴스 데이터를 추출하는 중...")
    commits = subprocess.check_output("git log --pretty=format:%h data/news.json", shell=True).decode().split('\n')
    all_news = {}
    
    total = len(commits)
    for i, commit in enumerate(commits):
        if i % 50 == 0:
            print(f"  - 진행률: {i}/{total} 커밋 처리 중...")
        try:
            out = subprocess.check_output(f"git show {commit}:data/news.json", shell=True, stderr=subprocess.DEVNULL)
            d = json.loads(out.decode('utf-8'))
            for date_str, items in d.items():
                if date_str not in all_news:
                    all_news[date_str] = {}
                for item in items:
                    # 중복 방지를 위해 링크 또는 제목을 키로 사용
                    sig = item.get('link') or item.get('title')
                    if sig and sig not in all_news[date_str]:
                        all_news[date_str][sig] = item
        except:
            pass
    
    # 다시 리스트 형태로 변환
    final_news = {}
    for d, items_dict in all_news.items():
        final_news[d] = list(items_dict.values())
    
    return final_news

def main():
    # 1. Git에서 전체 데이터 복구
    git_news = extract_all_git_news()
    
    # 2. 현재 시트의 데이터 로드 (혹시 모를 최신 데이터 보존)
    print("⏳ 현재 구글 시트의 최신 데이터를 로드하는 중...")
    sheet_news = load_news_from_sheet()
    if not sheet_news:
        sheet_news = {}
        
    # 3. 데이터 병합 (Git 데이터 기반으로 시트 데이터 덮어쓰기/추가)
    print("⏳ Git 데이터와 시트 데이터를 병합하는 중...")
    for date_str, items in sheet_news.items():
        if date_str not in git_news:
            git_news[date_str] = []
        
        # 중복 체크 후 추가
        existing_sigs = set((item.get('link') or item.get('title')) for item in git_news[date_str])
        for item in items:
            sig = item.get('link') or item.get('title')
            if sig not in existing_sigs:
                git_news[date_str].append(item)
                existing_sigs.add(sig)
                
    # 4. 결과 출력 및 업로드
    dates = sorted(list(git_news.keys()))
    print(f"✅ 총 {len(dates)}일치 데이터 복구 완료 ({dates[0]} ~ {dates[-1]})")
    
    # 각 날짜별 아이템 수 요약 출력 (선택사항)
    # for d in dates:
    #     print(f"  - {d}: {len(git_news[d])}건")
        
    print("⏳ 구글 시트에 전체 데이터를 업로드하는 중... 이 작업은 데이터가 많아 시간이 다소 걸릴 수 있습니다.")
    success = save_news_to_sheet(git_news)
    
    if success:
        print("🎉 모든 뉴스 데이터가 성공적으로 복구되어 구글 시트에 반영되었습니다!")
    else:
        print("❌ 업로드 중 오류가 발생했습니다.")

if __name__ == "__main__":
    main()
